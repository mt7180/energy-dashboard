import streamlit as st
from streamlit_extras.stylable_container import stylable_container

from entsoe import Area as entsoe_areas
# from entsoe.mappings import lookup_area

import trio
import pathlib
import logging

from charts.create_figures import (
    create_bar_chart,
    create_gauge,
    create_horizontal_bar_chart,
    create_map,
    create_metrics,
    create_pie_chart,
)
from etl.etl import DataProcessor

# from charts.create_figures import visualize


app_logger = logging.getLogger("app_logger")
app_logger.addHandler(logging.StreamHandler())
app_logger.setLevel(logging.DEBUG)


API_URL = ""
APP_TITLE = "Energy Dashboard"
cfd = pathlib.Path(__file__).parent
COUNTRY_CODES = entsoe_areas.__members__.keys()


container_style = """
{
background-color: white;
border-radius: 8px;
margin: 0px 0px;  
}
"""


class DashBoard:
    """streamlit dashboard for power generation and consumption data"""

    def __init__(self, data_processor):
        """put the streamlit app together"""
        self.data_processor = data_processor
        self.set_page_settings()
        self.initialize_session_state()
        self.display_header()
        self.main_page()

    def set_page_settings(self):
        st.set_page_config(
            page_title=APP_TITLE,
            page_icon="⚡",
            layout="wide",
        )
        with open(cfd / "static" / "style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    def initialize_session_state(self):
        if "container_counter" not in st.session_state:
            st.session_state.container_counter = 0
        if "country_code" not in st.session_state:
            st.session_state.country_code = "de"  # default value
        if "charts" not in st.session_state:
            st.session_state.charts = {}
        if "warning" not in st.session_state:
            st.session_state.warning = None
        if "grid_created" not in st.session_state:
            st.session_state.grid_created = False
        if "data_orchestrator" not in st.session_state:
            st.session_state.data_orchestrator = None
        if "warning_text" not in st.session_state:
            st.session_state.warning_text = []

    def display_header(self):
        with stylable_container(
            key="header_container",
            css_styles=[
                """
                {
                background-color: #1B8A85;
                color: white;
                text-align: center;
                [data-testid="stHorizontalBlock"] {
                    align-items: center;
                    column-gap: 0; 
                }
                
                [data-testid="stSelectbox"] {
                    padding-top: 32px;
                    padding-bottom: 20px;
                }
                [data-testid="stVerticalBlockBorderWrapper"] {
                    margin: 0rem 2rem 0rem 2rem; 
                }
                #energy-dashboard {
                    padding-bottom:0rem;
                }
            }
            """,
            ],
        ):
            left, mid, right = st.columns((0.1, 0.5, 0.4))
            with left:
                with st.container():
                    st.markdown("")
                    st.image("./static/icon.png", width=40)
            with mid:
                with st.container():
                    st.title(APP_TITLE)  # , help="data from ENTSO-E and Energy Charts")
                    st.markdown("""powered with data from ENTSO-E and Energy Charts""")

            with right:
                with st.container():
                    st.selectbox(
                        "country_code",
                        COUNTRY_CODES,
                        24,
                        format_func=lambda x: ": ".join((x, entsoe_areas[x].meaning)),
                        label_visibility="collapsed",
                        on_change=self.set_country_code,
                        key="select_box",
                    )

    def set_country_code(self):
        st.session_state.country_code = st.session_state.select_box.lower()
        logging.debug(
            f"st.session_state.country_code now: {st.session_state.country_code}"
        )
        data_processor.set_country_code(st.session_state.country_code)
        #        st.session_state.data_processor.data.clear(st.session_state.country_code)
        st.session_state.warning_text.clear()
        st.session_state.grid_created = False

    def main_page(self):
        if not st.session_state.grid_created:
            st.session_state.warning = st.empty()

            # generate chart grid and store in session_state (only once)
            top_left, top_right = st.columns(2)
            bottom_left, bottom_right = st.columns(2)

            with top_left:
                col1, col2, col3 = st.columns([3, 3, 4])
                with col1:
                    st.session_state.charts["metric1"] = st.empty()
                    st.session_state.charts["total_generation"] = st.empty()
                with col2:
                    st.session_state.charts["metric2"] = st.empty()
                    st.session_state.charts["renewables_generation"] = st.empty()
                with col3:
                    st.session_state.charts["location"] = st.empty()
            with top_right:
                st.session_state.charts["current_generation_by_source"] = st.empty()
            with bottom_right:
                st.session_state.charts["current_electricity_mix"] = st.empty()
            with bottom_left:
                st.session_state.charts["daily_capacity_factor_by_source"] = st.empty()
            st.session_state.grid_created = True

    def render(self):
        data = self.data_processor.data
        st.session_state.warning_text = self.data_processor.data.warning
        if text := st.session_state.warning_text:
            with st.session_state.warning:
                st.warning("; ".join(text))

        with st.session_state.charts["daily_capacity_factor_by_source"]:
            (
                annotation,
                capacity_factor_by_source,
            ) = data.daily_capacity_factor_by_source()
            fig = create_horizontal_bar_chart(annotation, capacity_factor_by_source)
            st.plotly_chart(fig, theme="streamlit", use_container_width=True)

        with st.session_state.charts["current_generation_by_source"]:
            fig = create_bar_chart(
                data.current_gen_by_source(),
                tz=data.country.tz,
                df_load=data.total_load_distribution(),
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=True)

        with st.session_state.charts["total_generation"].container():
            (
                total_aggregated_yesterday,
                total_max_installed,
            ) = data.total_power_aggregated_yesterday()

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
                tz=data.country.tz,
                suffix="TWh",
            )
            st.plotly_chart(fig_top, theme="streamlit", use_container_width=False)

        with st.session_state.charts["renewables_generation"].container():
            sub_text = "Yesterday"
            renewable_share_yesterday = round(data.renewable_share_yesterday2())
            fig = create_gauge(
                renewable_share_yesterday, "%", "Renewable Share", 100, sub_text
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=False)
            fig_metrics = create_metrics(
                "",
                renewable_share_yesterday,
                tz=data.country.tz,
                data_df=data.renewable_share(),
                suffix="%",
            )
            st.plotly_chart(fig_metrics, theme="streamlit", use_container_width=False)

        with st.session_state.charts["current_electricity_mix"]:
            fig = create_pie_chart(
                *data.current_power_mix(),
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=True)

        with st.session_state.charts["location"]:
            fig = create_map(
                data.country.code,
                data.country.name,
            )
            st.plotly_chart(fig, theme="streamlit", use_container_width=True)

    async def run(self):
        """run the etl process and continuously update the dashboard"""
        if not data_processor.completed:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(self.data_processor.run_etl)

                while not data_processor.completed:
                    self.render()
                    await trio.sleep(1)

        self.render()


data_processor = DataProcessor(st.session_state.get("country_code", "DE"))
dashboard = DashBoard(data_processor)


async def main():
    await dashboard.run()


if __name__ == "__main__":
    trio.run(main)
