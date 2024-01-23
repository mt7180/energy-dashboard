import streamlit as st
from streamlit_extras.stylable_container import stylable_container
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd

from entsoe import Area as ensoe_areas
# from entsoe.mappings import lookup_area

import random
import pathlib
import os

from etl.extract_transform_ENTSOE import DataHandler


API_URL = ""
APP_TITLE = "Power Generation Dashboard"
cfd = pathlib.Path(__file__).parent
COUNTRY_CODES = ensoe_areas.__members__.keys()

container_style = """
{
background-color: white;
border-radius: 8px;
margin: 0px 0px;  
}
"""

data_handler = DataHandler(os.getenv("ENTSOE_API_KEY", ""))


def set_page_settings():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="⚡",
        layout="wide",
    )
    with open(cfd / "static" / "style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def initialize_session_state():
    if "country_code" not in st.session_state:
        st.session_state.country_code = "DE"  # default value
    if "container_counter" not in st.session_state:
        st.session_state.container_counter = 0


def set_country_code():
    st.session_state.country_code = st.session_state.select_box


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
        left, right = st.columns((0.6, 0.4))
        with left:
            with st.container():
                st.title(APP_TITLE)

        with right:
            with st.container():
                st.selectbox(
                    "country_code",
                    COUNTRY_CODES,
                    24,
                    format_func=lambda x: ": ".join((x, ensoe_areas[x].meaning)),
                    label_visibility="collapsed",
                    on_change=set_country_code,
                    key="select_box",
                )


def plot_gauge(
    indicator_number, indicator_color, indicator_suffix, indicator_title, max_bound
):
    st.session_state.container_counter += 1
    with stylable_container(
        key=f"container_{st.session_state.container_counter}",
        css_styles=container_style,
    ):
        fig = go.Figure(
            go.Indicator(
                value=indicator_number,
                mode="gauge+number",
                domain={"x": [0, 1], "y": [0, 1]},
                number={
                    "suffix": indicator_suffix,
                    "font.size": 26,
                },
                gauge={
                    "axis": {"range": [0, max_bound], "tickwidth": 1},
                    "bar": {"color": indicator_color},
                },
                title={
                    "text": indicator_title,
                    "font": {"size": 20},
                },
            )
        )
        fig.update_layout(
            # paper_bgcolor="lightgrey",
            height=150,
            margin=dict(l=30, r=30, t=0, b=0, pad=8),
        )
        st.plotly_chart(fig, use_container_width=True)


def plot_metric(label, value, prefix="", suffix="", show_graph=False, color_graph=""):
    # with st.container(border=True):
    st.session_state.container_counter += 1
    with stylable_container(
        key=f"container_{st.session_state.container_counter}",
        css_styles=container_style,
    ):
        fig = go.Figure()

        fig.add_trace(
            go.Indicator(
                value=value,
                gauge={"axis": {"visible": False}},
                number={
                    "prefix": prefix,
                    "suffix": suffix,
                    "font.size": 30,
                },
                title={
                    "text": label,
                    "font": {"size": 14},
                },
            )
        )
        if show_graph:
            fig.add_trace(
                go.Scatter(
                    y=random.sample(range(0, 101), 30),
                    hoverinfo="skip",
                    fill="tozeroy",
                    fillcolor=color_graph,
                    line={
                        "color": color_graph,
                    },
                )
            )

        fig.update_xaxes(visible=False, fixedrange=True)
        fig.update_yaxes(visible=False, fixedrange=True)
        fig.update_layout(
            # paper_bgcolor="lightgrey",
            margin=dict(t=30, b=0),
            showlegend=False,
            plot_bgcolor="white",
            height=100,
        )

        st.plotly_chart(fig, use_container_width=True)


def plot_bar():
    fig = px.bar(
        data_handler.calculate_chart1_data(),
        labels={
            "value": "Actual Aggregated Generation [MW]",
            "variable": "Production Type",
            "index": "Date",
        },
        # https://plotly.com/python/discrete-color/
        color_discrete_sequence=px.colors.qualitative.Light24,
    )
    country_code = st.session_state.country_code
    title_str = "Current Power Generation and Forecast by Source for " + ": ".join(
        (country_code, ensoe_areas[country_code].code)
    )
    fig.update_layout(title=dict(text=title_str, font=dict(size=15), automargin=True))
    now = pd.Timestamp.today(tz="Europe/Brussels")
    fig.add_shape(  # add a vertical line (now)
        type="line",
        line_color="lightgreen",
        line_width=4,
        opacity=1,
        line_dash="dot",
        x0=now,
        x1=now,
        y0=0,
        y1=0.9,
        xref="x",
        yref="paper",
    )
    fig.add_annotation(  # add a text callout with arrow
        text="Now", x=now, y=0.9, yref="paper", arrowhead=1, showarrow=True
    )
    st.plotly_chart(fig, theme="streamlit", use_container_width=True)


def main_page():
    country_code = st.session_state.country_code
    data_handler.get_new_data(country_code)
    top_left, top_right = st.columns(2)
    bottom_left, bottom_right = st.columns((1, 2))

    with top_left:
        col1, col2, col3 = st.columns(3)
        with col1:
            plot_metric("Debt Equity", 1.10, prefix="", suffix=" %", show_graph=False)
            plot_gauge(1.86, "#0068C9", "%", "Current Ratio", 3)
        with col2:
            plot_metric("Debt Equity", 1.10, prefix="", suffix=" %", show_graph=False)
            plot_gauge(1.86, "#0068C9", "%", "Current Ratio", 3)
        with col3:
            plot_metric("Debt Equity", 1.10, prefix="", suffix=" %", show_graph=False)
            plot_gauge(1.86, "#0068C9", "%", "Current Ratio", 3)
    with bottom_right:
        plot_bar()


def main():
    """put the streamlit app together"""
    set_page_settings()
    initialize_session_state()
    display_header()
    # display_sidemenu()
    main_page()


if __name__ == "__main__":
    main()
