import collections
from entsoe.parsers import parse_generation
from entsoe.mappings import lookup_area
import pandas as pd

# import asyncio
import httpx
import string
import json
import pathlib
import trio
from enum import Enum
from typing import Self, Any
import os
import streamlit as st

from dotenv import load_dotenv
import logging

logger = logging.getLogger("app_logger")
logger.info("test")

cfd = pathlib.Path(__file__).parent

RequestParams = collections.namedtuple("RequestParams", ["key", "url", "params"])

DataKeys = Enum(
    "DataKeys",
    [
        "CURRENT_GENERATION_ENTSOE",
        "CAPACITY_BY_SOURCE_ENTSOE",
        "TOTAL_FORECAST_ENTSOE",
        "RENEWABLES_FORECAST_ENTSOE",
        "ACTUAL_TOTAL_LOAD_ENTSOE",
        "CURRENT_GENERATION_ENERGY_CHARTS",
        "CAPACITY_BY_SOURCE_ENERGY_CHARTS",
        "RENEWABLE_SHARE_ENERGY_CHARTS",
    ],
)


class Data:
    """a class which holds a data dict, and supports key look up by dot notation
    (on the class instance).
    Since __getattr__ points to the .__data dict itself, additionally all
    dict methods will be redirected an can be executed on the class.
    To force dot notation conform keys, the update method is excluded and
    the add method ensures the correct dict syntax.
    Based on an approach in Fluent Python: Dynamic Attributes and Properties
    """

    def __init__(self):
        self.__data = {}
        self.tz = ""

    def __getattr__(self, name) -> Any:
        """supports dot notation to perform key look up on __data dict,
        if key not in __data, getattr lets us perform dict methods
        """

        if name in self.__data.keys():
            return self.__data[name]

        # to make sure that key names can only be set with the add method,
        # which ensures that key is a string and supports dot notation
        if name == "update":
            raise AttributeError
        # access to all dict methods but update
        return getattr(self.__data, name)

    def add(self, key_name, data_record, country_code) -> None:
        if not all([char in string.ascii_letters + "_" for char in key_name]):
            raise ValueError("key name must only contain ascii letters or '_'")

        tz = lookup_area(country_code).tz
        if self.tz and self.tz != tz:
            raise ValueError("tz of new data does not match the current data...")
        self.tz = tz

        self.__data.update({key_name: data_record})

    def clear(self) -> None:
        self.__data.clear()
        self.tz = ""

    def daily_capacity_factor_by_source(self) -> tuple[str, pd.DataFrame]:
        df_installed_capacity_key = DataKeys.CAPACITY_BY_SOURCE_ENTSOE.name
        df_current_generation_key = DataKeys.CURRENT_GENERATION_ENTSOE.name

        if not all(
            [
                df_installed_capacity_key in self.keys(),
                df_current_generation_key in self.keys(),
            ]
        ):
            return "", pd.DataFrame()

        tz = self.CURRENT_GENERATION_ENTSOE.index.tz
        now = pd.Timestamp.now(tz=tz)
        end_time = now.floor("D")
        start_time = end_time - pd.Timedelta(days=1)

        max_len = len(self.CURRENT_GENERATION_ENTSOE)
        condition = (
            self.CURRENT_GENERATION_ENTSOE.stack(level=0)
            .unstack()["Actual Aggregated"]
            .notna()
            .sum()
            >= max_len * 0.9
        )

        annotation = (
            ""
            if all(condition)
            else (
                "Some data excluded because the generation data <br> from the transmission system <br> operator(s) is incomplete."
            )
        )
        return (
            annotation,
            pd.concat(
                [
                    self.CURRENT_GENERATION_ENTSOE.stack(level=0)
                    .unstack()["Actual Aggregated"]
                    .loc[start_time:end_time, condition]
                    .mean()
                    .to_frame()
                    .set_axis(["Daily Mean Aggregated"], axis="columns"),
                    self.CAPACITY_BY_SOURCE_ENTSOE.set_axis(["capacity"]).T,
                ],
                axis=1,
            )
            .sort_values(by=["capacity"], ascending=False)
            .assign(CF_Day=lambda d: d["Daily Mean Aggregated"] / d["capacity"])
            .fillna(0),
        )

    def current_gen_by_source(self):
        if not all(
            [
                DataKeys.CURRENT_GENERATION_ENTSOE.name in self.keys(),
                DataKeys.TOTAL_FORECAST_ENTSOE.name in self.keys(),
                DataKeys.RENEWABLES_FORECAST_ENTSOE.name in self.keys(),
            ]
        ):
            return pd.DataFrame()

        return (
            pd.merge(
                self.CURRENT_GENERATION_ENTSOE.stack(level=0).unstack()[
                    "Actual Aggregated"
                ],
                # .assign(Total_Aggregated=lambda d: d.sum(axis=1)),
                self.TOTAL_FORECAST_ENTSOE.rename(
                    columns={"Actual Aggregated": "Total"}
                )
                .loc[
                    self.TOTAL_FORECAST_ENTSOE.index
                    > self.CURRENT_GENERATION_ENTSOE.index[-1]
                ]
                .join(self.RENEWABLES_FORECAST_ENTSOE, how="left")
                .assign(
                    FC_Other=self.TOTAL_FORECAST_ENTSOE["Actual Aggregated"]
                    - self.RENEWABLES_FORECAST_ENTSOE.sum(axis=1)
                )
                .assign(FC_Solar_Wind=self.RENEWABLES_FORECAST_ENTSOE.sum(axis=1))
                .loc[:, ["FC_Solar_Wind", "FC_Other"]],
                how="outer",
                left_index=True,
                right_index=True,
            )
            .fillna(0)
            .resample("30Min")
            .mean()
        )

    def total_load_distribution(self):
        if DataKeys.ACTUAL_TOTAL_LOAD_ENTSOE.name not in self.keys():
            return pd.DataFrame()

        return self.ACTUAL_TOTAL_LOAD_ENTSOE

    @staticmethod
    def get_last_complete_row_index(df: pd.DataFrame):
        for row in df.index[::-1]:
            if all(df.loc[row].notna()):
                return row
        return df.index[0]

    def current_power_mix(self):
        if DataKeys.CURRENT_GENERATION_ENTSOE.name not in self.keys():
            return pd.DataFrame(), pd.to_datetime("01.01.2000", format="%d.%m.%Y")

        last_complete_row_index = self.get_last_complete_row_index(
            self.CURRENT_GENERATION_ENTSOE.stack(level=0).unstack()["Actual Aggregated"]
        )
        return (
            self.CURRENT_GENERATION_ENTSOE.stack(level=0)
            .unstack()["Actual Aggregated"]
            .loc[last_complete_row_index]
            .T.to_frame()
            .set_axis(["data"], axis=1),
            last_complete_row_index,
        )

    def total_power_aggregated_yesterday(self):
        """Yesterdays total aggregated electricity generation in TWh"""

        if not all(
            [
                "CURRENT_GENERATION_ENTSOE" in self.keys(),
                "CAPACITY_BY_SOURCE_ENTSOE" in self.keys(),
            ]
        ):
            return (0, 0)
        now = pd.Timestamp.now(tz=self.tz)
        end_time = now.floor("D")
        start_time = end_time - pd.Timedelta(days=1)
        total_capacity = self.CAPACITY_BY_SOURCE_ENTSOE.sum(axis=1)

        hourly_mean_aggregated = (
            (
                self.CURRENT_GENERATION_ENTSOE.stack(level=0)
                .unstack()["Actual Aggregated"]
                .loc[start_time:end_time]
                .assign(Total=self.CURRENT_GENERATION_ENTSOE.sum(axis=1))
            )
            .resample("1H")
            .mean()
        )

        # if entsoe data is missing for any source:
        if len(hourly_mean_aggregated) != hourly_mean_aggregated.notna().T.all().sum():
            warning = (
                "Data obtained from the entsoe transparency platform is incomplete, "
                + "visualized data should be used with caution ..."
            )
            if warning not in st.session_state.warning_text:
                st.session_state.warning_text.append(warning)
        # return 0, 0

        # approach with hourly averaged values ... maybe better to change to given timestep size averaged values
        total_aggregated_yesterday = (
            hourly_mean_aggregated.resample("1D").sum().iloc[0].Total / 10**6
        )
        return (total_aggregated_yesterday, total_capacity.iat[0] * 24 / 10**6)

    def total_load_yesterday(self):
        """Yesterdays total load in TWh"""

        if "ACTUAL_TOTAL_LOAD_ENTSOE" not in self.keys():
            return 0

        now = pd.Timestamp.now(tz=self.tz)
        end_time = now.floor("D")
        start_time = end_time - pd.Timedelta(days=1)

        hourly_mean_aggregated = (
            (self.ACTUAL_TOTAL_LOAD_ENTSOE.loc[start_time:end_time])
            .resample("1H")
            .mean()
        )

        # approach with hourly averaged values ... maybe better to change to given timestep size averaged values
        return (
            hourly_mean_aggregated.resample("1D").sum().iloc[0]["Actual Consumption"]
            / 10**6
        )

    def renewable_share_yesterday(self):
        if "RENEWABLE_SHARE_ENERGY_CHARTS" not in self.keys():
            return 0

        today = pd.Timestamp.today(tz=self.tz).floor("D")
        total_load = self.total_load_yesterday()
        total_power_aggregated, _ = self.total_power_aggregated_yesterday()

        return (
            self.RENEWABLE_SHARE_ENERGY_CHARTS.loc[today - pd.Timedelta(days=1), "data"]
            * max([total_load, 1])
            / max([total_power_aggregated, 1])
        )

    def renewable_share(self):
        if "RENEWABLE_SHARE_ENERGY_CHARTS" not in self.keys():
            return None
        self.RENEWABLE_SHARE_ENERGY_CHARTS[
            "year"
        ] = self.RENEWABLE_SHARE_ENERGY_CHARTS.index.year
        return pd.pivot_table(
            self.RENEWABLE_SHARE_ENERGY_CHARTS,
            values="data",
            index=self.RENEWABLE_SHARE_ENERGY_CHARTS.index.day_of_year,
            columns="year",
        )


class DataPipeline:
    def __init__(
        self,
        data: Data,
        request_params=None,
        country_code: str = "de",
    ):
        self.data = data
        self.api_params: RequestParams = request_params
        self.country_code = country_code

    async def extract(self, client: httpx.AsyncClient, retries: int) -> Self:
        if not self.api_params:
            raise ValueError("no request parameters provided for extraction")

        logger.debug(f"{self.api_params.key.name} starts")

        for attempt in range(retries):
            try:
                response = await client.get(
                    url=self.api_params.url, params=self.api_params.params
                )

            except httpx.RequestError as e:
                warning = f"API request returned exception: {self.api_params.url}: {self.api_params.key.name} ({self.country_code}) ... {e!r}"
                logger.debug(warning)
                logger.debug(
                    f"{self.api_params.key.name}: attempt: {attempt} raised error {e}, retrying ..."
                )

                if attempt < retries - 1:
                    continue
                if warning not in st.session_state.warning_text:
                    st.session_state.warning_text.append(warning)
                return self

            else:
                # when attempt was successful
                break

        # response.raise_for_status()
        key_name = self.api_params.key.name

        if response.is_success:
            if "ENTSOE" in self.api_params.key.name:
                try:
                    data = parse_generation(response.text, nett=False)
                    if data.empty:
                        raise ValueError("no entsoe data available...")
                    data = data.tz_convert(lookup_area(self.country_code).tz)
                    self.data.add(
                        key_name,
                        data.to_frame() if isinstance(data, pd.Series) else data,
                        self.country_code,
                    )

                except KeyError as e:
                    logger.info(f"parsing entsoe data was not possible: {e}")
                else:
                    # save as instant data
                    self.data.get(key_name).to_pickle(
                        f"{cfd / 'tmp'}/{key_name}_{self.country_code.upper()}.pkl"
                    )

            else:
                data = json.loads(response.text)
                index = data.pop(list(data.keys())[0])  # rely on dict order

                self.data.add(
                    key_name,
                    pd.DataFrame(
                        #     #{item['name']:item['data'] for item in data['production_types']},
                        #    [{item['name']:item['data'] for item in data[column]} for column in data],
                        data,
                        index=pd.DatetimeIndex(
                            pd.to_datetime(index, format="%d.%m.%Y")
                        ).tz_localize(
                            lookup_area(self.country_code).tz
                        ),  # tz=lookup_area(self.country_code).tz), #[datetime.fromtimestamp(date) for date in index]
                    ),
                    self.country_code,
                )
        else:
            logger.debug(f"{key_name}: {response}, {response.text}")
            # st.session_state['data'][request.key] = None
        logger.debug(f"{key_name} loaded")
        return self

    def transform(self) -> Self:
        return self

    def load(self) -> Self:
        return self

    def visualize(self) -> Self:
        from charts.create_figures import (
            create_horizontal_bar_chart,
            create_gauge,
            create_metrics,
            create_bar_chart,
            create_pie_chart,
            create_map,
        )

        if text := st.session_state.warning_text:
            with st.session_state.warning:
                st.warning(", ".join(text))

        with st.session_state.charts["daily_capacity_factor_by_source"]:
            annotation, data = self.data.daily_capacity_factor_by_source()
            fig = create_horizontal_bar_chart(annotation, data)
            st.plotly_chart(fig, theme="streamlit", use_container_width=True)

        with st.session_state.charts["current_generation_by_source"]:
            fig = create_bar_chart(
                self.data.current_gen_by_source(),
                tz=lookup_area(self.country_code).tz,
                df_load=self.data.total_load_distribution(),
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=True)

        with st.session_state.charts["total_generation"].container():
            (
                total_aggregated_yesterday,
                total_max_installed,
            ) = self.data.total_power_aggregated_yesterday()

            sub_text = "Yesterday"
            fig = create_gauge(
                total_aggregated_yesterday,
                "TWh",
                "Total Power Generation",
                total_max_installed,
                sub_text,
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=False)
            fig_top = create_metrics(
                "label",
                total_aggregated_yesterday,
                tz=lookup_area(self.country_code).tz,
                suffix="TWh",
            )
            st.plotly_chart(fig_top, theme="streamlit", use_container_width=False)

        with st.session_state.charts["renewables_generation"].container():
            sub_text = "Yesterday"
            renewable_share_yesterday = round(self.data.renewable_share_yesterday())
            fig = create_gauge(
                renewable_share_yesterday, "%", "Renewable Share", 100, sub_text
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=False)
            fig_metrics = create_metrics(
                "",
                renewable_share_yesterday,
                tz=lookup_area(self.country_code).tz,
                data_df=self.data.renewable_share(),
                suffix="%",
            )
            st.plotly_chart(fig_metrics, theme="streamlit", use_container_width=False)

        with st.session_state.charts["current_electricity_mix"]:
            fig = create_pie_chart(
                *self.data.current_power_mix(),
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=True)

        with st.session_state.charts["location"]:
            fig = create_map(
                pd.DataFrame, self.country_code, lookup_area(self.country_code).meaning
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=True)

        return self

    async def run(self, client: httpx.AsyncClient) -> None:
        ((await self.extract(client, retries=3)).transform().load().visualize())

    def read_instant_data(self, path=cfd / "tmp"):
        logger.debug("load instant data")
        files = os.listdir(path)
        pickle_files = [file for file in files if file.endswith(".pkl")]

        for file_name in pickle_files:
            if self.country_code.upper() not in file_name:
                continue
            if file_name.split("_" + self.country_code.upper())[0] not in [
                key.name for key in DataKeys
            ]:
                continue
            file_path = os.path.join(path, file_name)
            name = file_name.split("_" + self.country_code.upper())[0]
            logger.debug(f"... loading {name}")

            data = pd.read_pickle(file_path)
            if not isinstance(data, pd.DataFrame):
                data = data.to_frame()

            self.data.add(name, data, self.country_code)
            self.visualize()
        logger.debug("finished loading instant data")


class Orchestrator:
    def __init__(self, country_code):
        self.data = Data()
        self.set_country_code(country_code)

    @staticmethod
    def format_date_for_entsoe(date: pd.Timestamp):
        return date.tz_convert("UTC").round(freq="h").strftime("%Y%m%d%H00")

    @staticmethod
    def format_date_for_energy_charts(date: pd.Timestamp):
        date_str = date.strftime("%Y-%m-%dT%H:%M%z")
        return date_str[:-2] + ":" + date_str[-2:]

    @property
    def country_code(self):
        return self._country_code

    @country_code.setter
    def country_code(self, value):
        self._country_code = value.upper()
        # DataPipeline(country_code=self.country_code).read_instant_data()

    def set_country_code(self, country_code):
        self.country_code = country_code
        self.data.clear()
        DataPipeline(data=self.data, country_code=self.country_code).read_instant_data()

    async def run_orchestration(self) -> None:
        entsoe_api = "https://web-api.tp.entsoe.eu/api"
        energy_charts_api = "https://api.energy-charts.info"

        end = pd.Timestamp.today(tz=lookup_area(self.country_code).tz)  # now
        start = end.floor("D") - pd.Timedelta(days=1)  # begin of yesterday(00:00)

        requests = [
            # RequestParams(
            #     DataKeys.CURRENT_GENERATION_ENERGY_CHARTS,
            #     energy_charts_api + "/total_power",
            #     {"country": self.country_code.lower() ,"start": self.format_date_for_energy_charts(start), "end":self.format_date_for_energy_charts(end)}
            # ),
            # RequestParams(
            #     DataKeys.CAPACITY_BY_SOURCE_ENERGY_CHARTS,
            #     energy_charts_api + "/installed_power",
            #     {"country": self.country_code.lower(), "time_step": "yearly", "installation_commission":False}
            # ),
            RequestParams(
                DataKeys.ACTUAL_TOTAL_LOAD_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(start),
                    "periodEnd": self.format_date_for_entsoe(end),
                    "documentType": "A65",
                    "ProcessType": "A16",
                    "outBiddingZone_Domain": lookup_area(self.country_code).value,
                },
            ),
            RequestParams(
                DataKeys.RENEWABLE_SHARE_ENERGY_CHARTS,
                energy_charts_api + "/ren_share_daily_avg",
                {"country": self.country_code.lower()},
            ),
            RequestParams(
                DataKeys.CURRENT_GENERATION_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(start),
                    "periodEnd": self.format_date_for_entsoe(end),
                    "documentType": "A75",  # 'A75': 'Actual generation per type',
                    "ProcessType": "A16",
                    "in_Domain": lookup_area(
                        self.country_code
                    ).value,  # default is Germany: '10Y1001A1001A83F'
                },
            ),
            RequestParams(
                DataKeys.CAPACITY_BY_SOURCE_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(start),
                    "periodEnd": self.format_date_for_entsoe(end),
                    "documentType": "A68",  # 'A75': 'Actual generation per type',
                    "ProcessType": "A33",
                    "in_Domain": lookup_area(
                        self.country_code
                    ).value,  # default is Germany: '10Y1001A1001A83F'
                },
            ),
            RequestParams(
                DataKeys.TOTAL_FORECAST_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(end),
                    "periodEnd": self.format_date_for_entsoe(
                        end + pd.Timedelta(hours=24)
                    ),
                    "documentType": "A71",  # 'A75': 'Actual generation per type',
                    "ProcessType": "A01",
                    "in_Domain": lookup_area(
                        self.country_code
                    ).value,  # default is Germany: '10Y1001A1001A83F'
                },
            ),
            RequestParams(
                DataKeys.RENEWABLES_FORECAST_ENTSOE,
                entsoe_api,
                {
                    "securityToken": os.getenv("ENTSOE_API_KEY", ""),
                    "periodStart": self.format_date_for_entsoe(end),
                    "periodEnd": self.format_date_for_entsoe(
                        end + pd.Timedelta(hours=24)
                    ),
                    "documentType": "A69",  # 'A75': 'Actual generation per type',
                    "ProcessType": "A01",  # Forecast
                    "in_Domain": lookup_area(
                        self.country_code
                    ).value,  # default is Germany: '10Y1001A1001A83F'
                },
            ),
        ]

        async with httpx.AsyncClient() as httpx_client:
            # with trio slightly faster than with asyncio

            async with trio.open_nursery() as nursery:
                data_pipelines = [
                    (
                        DataPipeline(self.data, request, self.country_code).run,
                        httpx_client,
                    )
                    for request in requests
                ]
                for data_pipeline in data_pipelines:
                    nursery.start_soon(*data_pipeline)


if __name__ == "__main__":
    load_dotenv("../.env")
    orchestrator = Orchestrator("de")
    trio.run(orchestrator.run_orchestration)
