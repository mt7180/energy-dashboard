from enum import Enum
from entsoe.mappings import lookup_area
import pandas as pd
import string
from typing import NamedTuple, Any


class Country(NamedTuple):
    name: str = ""
    code: str = ""
    long_code: str = ""
    tz: str = ""


class Data:
    """a class which holds a data dict, and supports key look up by dot notation
    (on the class instance).
    Since __getattr__ points to the .__data dict itself, additionally all
    dict methods will be redirected an can be executed on the class.
    To force dot notation conform keys, the update method is excluded and
    the add method ensures the correct dict syntax.
    Based on an approach in Fluent Python: Dynamic Attributes and Properties
    """

    def __init__(self, country_code):
        self.__data = {}  # key: None for key in Data.name_keys()}
        self.country = country_code
        self.warning = []

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

    @staticmethod
    def name_keys():
        return Enum(
            "DataKeys",
            [
                "CURRENT_GENERATION_ENTSOE",
                "CAPACITY_BY_SOURCE_ENTSOE",
                "TOTAL_FORECAST_ENTSOE",
                "RENEWABLES_FORECAST_ENTSOE",
                "ACTUAL_TOTAL_LOAD_ENTSOE",
                "RENEWABLE_SHARE_ENERGY_CHARTS",
            ],
        )

    @property
    def country(self):
        return self._country

    @country.setter
    def country(self, new_code):
        self._country = Country(
            code=new_code.upper(),
            long_code=lookup_area(new_code).value,
            name=lookup_area(new_code).meaning,
            tz=lookup_area(new_code).tz,
        )

    def add(self, key_name, data_record, country_code) -> None:
        if not all([char in string.ascii_letters + "_" for char in key_name]):
            raise ValueError("key name must only contain ascii letters or '_'")

        tz = lookup_area(country_code).tz
        if self.country.tz and self.country.tz != tz:
            raise ValueError("tz of new data does not match the current data...")
        # self.country.tz = tz

        self.__data.update({key_name: data_record})

    def clear(self, new_country_code) -> None:
        self.__data.clear()
        self.country = new_country_code

    @staticmethod
    def custom_unstack(df):
        try:
            return df.unstack()["Actual Aggregated"]
        except KeyError:
            return df.unstack()

    def daily_capacity_factor_by_source(self) -> tuple[str, pd.DataFrame]:
        df_installed_capacity_key = Data.name_keys().CAPACITY_BY_SOURCE_ENTSOE.name
        df_current_generation_key = Data.name_keys().CURRENT_GENERATION_ENTSOE.name

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
            .pipe(Data.custom_unstack)  # unstack()["Actual Aggregated"]
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
                    # .unstack()["Actual Aggregated"]
                    .pipe(Data.custom_unstack)
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
                Data.name_keys().CURRENT_GENERATION_ENTSOE.name in self.keys(),
                Data.name_keys().TOTAL_FORECAST_ENTSOE.name in self.keys(),
                Data.name_keys().RENEWABLES_FORECAST_ENTSOE.name in self.keys(),
            ]
        ):
            return pd.DataFrame()

        return (
            pd.merge(
                self.CURRENT_GENERATION_ENTSOE.stack(level=0).pipe(Data.custom_unstack),
                # .unstack()["Actual Aggregated"],
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
        if Data.name_keys().ACTUAL_TOTAL_LOAD_ENTSOE.name not in self.keys():
            return pd.DataFrame()

        return (
            self.ACTUAL_TOTAL_LOAD_ENTSOE
        )  # + self.CURRENT_GENERATION_ENTSOE.stack(level=0).unstack()[
        #  "Actual Aggregated"
        # ]

    @staticmethod
    def get_last_complete_row_index(df: pd.DataFrame):
        for row in df.index[::-1]:
            total = df.loc[row].sum()
            timestep_before = df.index[df.index.get_loc(row) - 1]
            total_before = df.loc[timestep_before].sum()

            if all(df.loc[row].notna()) and abs(1 - total_before / total) < 0.25:
                return row

        return df.index[0]

    def current_power_mix(self):
        if Data.name_keys().CURRENT_GENERATION_ENTSOE.name not in self.keys():
            return pd.DataFrame(), pd.to_datetime("01.01.2000", format="%d.%m.%Y")

        last_complete_row_index = self.get_last_complete_row_index(
            self.CURRENT_GENERATION_ENTSOE.stack(level=0)
            # .unstack()["Actual Aggregated"]
            .pipe(Data.custom_unstack)
        )
        return (
            self.CURRENT_GENERATION_ENTSOE.stack(level=0)
            # .unstack()["Actual Aggregated"]
            .pipe(Data.custom_unstack)
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
        now = pd.Timestamp.now(tz=self.country.tz)
        end_time = now.floor("D")
        start_time = end_time - pd.Timedelta(days=1)
        total_capacity = self.CAPACITY_BY_SOURCE_ENTSOE.sum(axis=1)

        hourly_mean_aggregated = (
            (
                self.CURRENT_GENERATION_ENTSOE.stack(level=0)
                # .unstack()["Actual Aggregated"]
                .pipe(Data.custom_unstack)
                .loc[start_time:end_time]
                .assign(Total=self.CURRENT_GENERATION_ENTSOE.sum(axis=1))
            )
            .resample("1H")
            .mean()
        )

        # if entsoe data is missing for any source:
        if len(hourly_mean_aggregated) != hourly_mean_aggregated.notna().T.all().sum():
            warning = (
                "Current Generation Data obtained from the entsoe transparency platform is incomplete, "
                + "use visualized data with caution ..."
            )
            if warning not in self.warning:
                self.warning.append(warning)

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

    def renewable_share_yesterday2(self):
        if not all(
            [
                "CURRENT_GENERATION_ENTSOE" in self.keys(),
                "CAPACITY_BY_SOURCE_ENTSOE" in self.keys(),
            ]
        ):
            return 0

        now = pd.Timestamp.now(tz=self.country.tz)
        end_time = now.floor("D")
        start_time = end_time - pd.Timedelta(days=1)

        total_power_aggregated, _ = self.total_power_aggregated_yesterday()

        columns = (
            self.CURRENT_GENERATION_ENTSOE.head()
            .stack(level=0)
            .pipe(Data.custom_unstack)
            # .unstack()["Actual Aggregated"]
            .columns
        )
        keys = ["wind", "solar", "biomass", "hydro", "geothermal"]

        columns_to_sum = [
            column for column in columns for key in keys if key in column.lower()
        ]

        return (
            self.CURRENT_GENERATION_ENTSOE.stack(level=0)
            # .unstack()["Actual Aggregated"]
            .pipe(Data.custom_unstack)
            .loc[start_time:end_time][columns_to_sum]
            .resample("1H")
            .mean()
            .sum()
            .sum()
            / 10**6
            / total_power_aggregated
            * 100
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


# if __name__ == "__main__":
#     data = Data("DE")
