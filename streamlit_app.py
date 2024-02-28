import streamlit as st
from streamlit_extras.stylable_container import stylable_container
from dotenv import load_dotenv

from entsoe import Area as entsoe_areas
# from entsoe.mappings import lookup_area

import trio

import pathlib

from etl.etl import Orchestrator

# from etl.extract_data import DataHandler
# from etl.visualize_data import draw_charts
# from plots.create_figures import create_generation_by_source, create_gauge
load_dotenv()

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


def set_page_settings():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="⚡",
        layout="wide",
    )
    with open(cfd / "static" / "style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def initialize_session_state():
    if "container_counter" not in st.session_state:
        st.session_state.container_counter = 0
    if "country_code" not in st.session_state:
        st.session_state.country_code = "de"  # default value
    if "charts" not in st.session_state:
        st.session_state.charts = {}
    if "grid_created" not in st.session_state:
        st.session_state.grid_created = False
    if "data_orchestrator" not in st.session_state:
        st.session_state.data_orchestrator = None


# def set_country_code():
#     st.session_state.country_code = st.session_state.select_box
#     DataHandler.get_handler().country_code = st.session_state.country_code


def display_header():
    with stylable_container(
        key="header_container",
        css_styles=[
            """
            {
            background-color: #1B8A85;
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
                st.title(APP_TITLE)
        with right:
            with st.container():
                st.selectbox(
                    "country_code",
                    COUNTRY_CODES,
                    24,
                    format_func=lambda x: ": ".join((x, entsoe_areas[x].meaning)),
                    label_visibility="collapsed",
                    on_change=set_country_code,
                    key="select_box",
                )


def set_country_code():
    st.session_state.country_code = st.session_state.select_box.lower()
    print("st.session_state.country_code now: ", st.session_state.country_code)
    st.session_state.data_orchestrator.country_code = st.session_state.country_code
    st.session_state.data_orchestrator.data.clear()
    st.session_state.grid_created = False


def main_page():
    # country_code = st.session_state.country_code

    if not st.session_state.grid_created:
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

    if not st.session_state.data_orchestrator:
        st.session_state.data_orchestrator = Orchestrator("de")

    trio.run(st.session_state.data_orchestrator.run_orchestration)


def main():
    """put the streamlit app together"""
    set_page_settings()
    initialize_session_state()
    display_header()
    main_page()


if __name__ == "__main__":
    main()
