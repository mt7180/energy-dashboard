import collections
from entsoe.parsers import parse_generation
from entsoe.mappings import lookup_area
import pandas as pd

# import asyncio
import httpx
import json
import pathlib
import trio

import os
# import streamlit as st

from dotenv import load_dotenv
import logging
from etl.data import Data, Country

logger = logging.getLogger("app_logger")

cfd = pathlib.Path(__file__).parent

RequestParams = collections.namedtuple("RequestParams", ["key", "url", "params"])


class DataPipeline:
    def __init__(
        self,
        processor,
        request_params=None,
    ):
        self.processor: DataProcessor = processor
        self.api_params: RequestParams = request_params
        self.id: str = self.api_params.key.name if request_params else "read_instant"
        self.country: Country = self.processor.data.country
        self.warnings: list[str] = []

    @staticmethod
    def create_empty_response():
        """Create an empty httpx.Response object."""
        return httpx.Response(
            status_code=0,
            request=httpx.Request(
                "GET", "placeholder_url"
            ),  # Dummy request for context
        )

    async def extract(self, client: httpx.AsyncClient, retries: int) -> httpx.Response:
        if not self.api_params:
            logger.debug("no request params")
            raise ValueError("no request parameters provided for extraction")

        logger.debug(f"{self.api_params.key.name} starts")

        for attempt in range(1, retries + 1):
            try:
                response = await client.get(
                    url=self.api_params.url, params=self.api_params.params
                )

            except httpx.RequestError as e:
                warning = (
                    f"{self.api_params.key.name}: API request returned exception: {e!r}"
                )
                logger.debug(warning)
                logger.debug(
                    f"{self.api_params.key.name}: attempt: {attempt} raised error {e}, retrying ..."
                )

                if attempt < retries:
                    continue
                else:
                    logger.debug(f"{self.api_params.key.name}: all attempts failed")
                    self.warnings.append(warning)
                    response = self.create_empty_response()

            else:
                # when attempt was successful
                break

        return response

    def transform(self, raw_data) -> pd.DataFrame:
        if not raw_data or not raw_data.is_success:
            return pd.DataFrame()
        key_name = self.id

        try:
            if "ENTSOE" in self.api_params.key.name:
                try:
                    data = parse_generation(raw_data.text, nett=False)
                    if data.empty:
                        warning = f"no entsoe data available: {self.api_params.url}: {key_name} ({self.country.code}) ... "
                        logger.debug(warning)
                        # self.warnings.append(warning)
                        raise ValueError(warning)
                    data = data.tz_convert(self.country.tz)
                    df = data.to_frame() if isinstance(data, pd.Series) else data

                except KeyError as e:
                    logger.info(f"parsing entsoe data was not possible: {e}")
                    df = pd.DataFrame()
            else:
                data = json.loads(raw_data.text)
                index = data.pop(list(data.keys())[0])  # rely on dict order
                df = pd.DataFrame(
                    data,
                    index=pd.DatetimeIndex(
                        pd.to_datetime(index, format="%d.%m.%Y")
                    ).tz_localize(self.country.tz),
                )

        except (ValueError, AttributeError):
            warning = f"no {key_name} data available"
            logger.debug(warning)
            self.warnings.append(warning)
            # logger.debug(f"{key_name}: {raw_data}")
            df = pd.DataFrame()

        return df

    async def load(self, df: pd.DataFrame) -> None:
        key_name = self.api_params.key.name
        country_code = self.country.code.upper()

        await self.processor.add_data(key_name, df, country_code, self.warnings)

        # save as instant data
        key_name = self.api_params.key.name
        if not df.empty:
            df.to_pickle(f"{cfd / 'tmp'}/{key_name}_{country_code}.pkl")

    async def run(self, client: httpx.AsyncClient) -> None:
        extracted_data = await self.extract(client, retries=3)
        transformed_data = self.transform(extracted_data)
        await self.load(transformed_data)

    def read_instant_data(self, path=cfd / "tmp"):
        country_code = self.processor.data.country.code
        logger.debug(f"load instant data {country_code}")
        files = os.listdir(path)
        pickle_files = [file for file in files if file.endswith(".pkl")]

        for file_name in pickle_files:
            if country_code.upper() not in file_name:
                continue
            if file_name.split("_" + country_code.upper())[0] not in [
                key.name for key in Data.name_keys()
            ]:
                continue
            file_path = os.path.join(path, file_name)
            name = file_name.split("_" + country_code.upper())[0]
            logger.debug(f"... loading {name}")

            data = pd.read_pickle(file_path)
            if not isinstance(data, pd.DataFrame):
                data = data.to_frame()

            self.processor.data.add(name, data, country_code)
        logger.debug("finished loading instant data")


class DataProcessor:
    """Handles the ETL process: Extract, Transform, and Load data"""

    def __init__(self, country_code="DE"):
        logging.debug("a new data processor is alive...")
        self.data = Data(country_code.upper())
        self.data_lock = trio.Lock()
        # self.set_country_code(country_code)
        self.completed = False
        DataPipeline(self).read_instant_data()

    async def add_data(self, key_name, df, country_code, warnings=[]) -> None:
        async with self.data_lock:
            if not df.empty:
                self.data.add(
                    key_name,
                    df,
                    country_code,
                )
            self.data.warning.extend(warnings)

    @staticmethod
    def format_date_for_entsoe(date: pd.Timestamp):
        return date.tz_convert("UTC").round(freq="h").strftime("%Y%m%d%H00")

    @staticmethod
    def format_date_for_energy_charts(date: pd.Timestamp):
        date_str = date.strftime("%Y-%m-%dT%H:%M%z")
        return date_str[:-2] + ":" + date_str[-2:]

    def set_country_code(self, country_code):
        self.data.set_country(country_code.upper())
        DataPipeline(self).read_instant_data()
        self.completed = False

    async def run_etl(self) -> None:
        entsoe_api = "https://web-api.tp.entsoe.eu/api"
        energy_charts_api = "https://api.energy-charts.info"

        end = pd.Timestamp.today(tz=lookup_area(self.data.country.code).tz)  # now
        start = end.floor("D") - pd.Timedelta(days=1)  # begin of yesterday(00:00)

        requests = [
            # RequestParams(
            #     Data.name_keys().CURRENT_GENERATION_ENERGY_CHARTS,
            #     energy_charts_api + "/total_power",
            #     {"country": self.data.country.code.lower() ,"start": self.format_date_for_energy_charts(start), "end":self.format_date_for_energy_charts(end)}
            # ),
            # RequestParams(
            #     Data.name_keys().CAPACITY_BY_SOURCE_ENERGY_CHARTS,
            #     energy_charts_api + "/installed_power",
            #     {"country": self.data.country.code.lower(), "time_step": "yearly", "installation_commission":False}
            # ),
            RequestParams(
                Data.name_keys().ACTUAL_TOTAL_LOAD_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(start),
                    "periodEnd": self.format_date_for_entsoe(end),
                    "documentType": "A65",  # System total load
                    "ProcessType": "A16",  # Realised
                    "outBiddingZone_Domain": self.data.country.long_code,
                },
            ),
            RequestParams(
                Data.name_keys().RENEWABLE_SHARE_ENERGY_CHARTS,
                energy_charts_api + "/ren_share_daily_avg",
                {"country": self.data.country.code.lower()},
            ),
            RequestParams(
                Data.name_keys().CURRENT_GENERATION_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(start),
                    "periodEnd": self.format_date_for_entsoe(end),
                    "documentType": "A75",  # 'A75': 'Actual generation per type',
                    "ProcessType": "A16",
                    "in_Domain": self.data.country.long_code,  # default is Germany: '10Y1001A1001A83F'
                },
            ),
            RequestParams(
                Data.name_keys().CAPACITY_BY_SOURCE_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(start),
                    "periodEnd": self.format_date_for_entsoe(end),
                    "documentType": "A68",  # Installed generation per type
                    "ProcessType": "A33",
                    "in_Domain": self.data.country.long_code,  # default is Germany: '10Y1001A1001A83F'
                },
            ),
            RequestParams(
                Data.name_keys().TOTAL_FORECAST_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(end),
                    "periodEnd": self.format_date_for_entsoe(
                        end + pd.Timedelta(hours=24)
                    ),
                    "documentType": "A71",  # Generation forecast,
                    "ProcessType": "A01",  # Day ahead
                    "in_Domain": self.data.country.long_code,  # default is Germany: '10Y1001A1001A83F'
                },
            ),
            RequestParams(
                Data.name_keys().RENEWABLES_FORECAST_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(end),
                    "periodEnd": self.format_date_for_entsoe(
                        end + pd.Timedelta(hours=24)
                    ),
                    "documentType": "A69",  # 'A75': 'Actual generation per type',
                    "ProcessType": "A01",  # Forecast
                    "in_Domain": self.data.country.long_code,
                },
            ),
        ]

        async with httpx.AsyncClient() as httpx_client:
            # with trio slightly faster than with asyncio
            async with trio.open_nursery() as nursery:
                data_pipelines = [
                    (
                        DataPipeline(self, request).run,
                        httpx_client,
                        request.key.name,
                    )
                    for request in requests
                ]
                for func, client, task_name in data_pipelines:
                    nursery.start_soon(func, client, name=task_name)

        self.completed = True


if __name__ == "__main__":
    load_dotenv("../.env")

    async def main():
        async with trio.open_nursery() as nursery:
            nursery.start_soon(data_processor.run_etl)

    data_processor = DataProcessor()
    trio.run(main)
