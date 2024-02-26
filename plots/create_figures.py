import plotly.express as px
import plotly.graph_objs as go
import pandas as pd
import copy
import math

from .helpers import get_color, color_sequences

SECONDARY_COLOR = "#1B8A85"
TEXT_COLOR = "#818494"
TITLE_SIZE = 20


def create_bar_chart(df_data):
    fig = px.bar(
        df_data.loc[:, ["FC_" not in col for col in df_data.columns]],
        labels={
            "value": "Actual Aggregated Generation [MW]",
            "variable": "Production Type",
            "index": "Date",
        },
        # https://plotly.com/python/discrete-color/
        color_discrete_sequence=px.colors.qualitative.Light24,
    )
    title_str = "Current Power Generation and Forecast by Source"

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
        text="today", x=now, y=1.5, yref="paper", arrowhead=1, showarrow=True
    )

    fig.add_trace(
        go.Bar(
            x=df_data.index,  # df_data, #.loc[:, "FC_" not in df_data.columns],#~df_data.columns.isin(['FC_', 'C'])],
            y=df_data.loc[:, ["FC_" in col for col in df_data.columns]],
            name="test",
        )
    )
    return fig


# def color(type: str) -> str:


def create_bar_chart2(df_data: pd.DataFrame, tz):
    # breakpoint()
    color_sequences_copy = copy.deepcopy(color_sequences)
    data = (
        [
            go.Bar(
                x=df_data.index,  # df_data, #.loc[:, "FC_" not in df_data.columns],#~df_data.columns.isin(['FC_', 'C'])],
                y=df_data[column],
                name=column,
                showlegend=False,
                marker_color=get_color(column, color_sequences_copy),
                hovertext=column,
                # labels={
                #     "value": "Actual Aggregated Generation [MW]",
                #     "variable": "Production Type",
                #     "index": "Date",
                # },
                # https://plotly.com/python/discrete-color/
            )
            for column in sorted(df_data.columns)
            if "FC_" not in column
        ]
        + [  # in df_data.loc[:, ["FC_" not in col for col in df_data.columns ]]
            go.Bar(
                x=df_data.index,  # df_data, #.loc[:, "FC_" not in df_data.columns],#~df_data.columns.isin(['FC_', 'C'])],
                y=df_data[column],
                name=column,
                legend="legend2",
            )
            for column in sorted(
                df_data.loc[:, ["FC_" in col for col in df_data.columns]]
            )
        ]
    )
    fig = go.Figure(data=data)

    fig.update_layout(
        # title="Aggregated Generation per Production Type",
        # template="simple_white",
        height=250,
        margin=dict(t=50, b=10),
        yaxis=dict(title_text="MW"),
        barmode="stack",
        showlegend=True,
        title=dict(
            text="Aggregated Generation per Production Type",
            yanchor="top",
            y=0.95,
            xanchor="center",
            x=0.5,
            font={"size": TITLE_SIZE, "color": TEXT_COLOR},
        ),
        # title_font = dict(
        #     size=TITLE_SIZE,
        #     color=TEXT_COLOR
        # ),
        # legend={
        #     "orientation":"h",
        #     #"title": "Types",
        #     "yanchor":"top",
        #     "y":1.6,
        #     "xanchor":"center",
        #     "x":0.5,
        #     "yref": "paper",
        #     "bgcolor":"rgba(0,0,0,0)",
        #     "font_size": 10,
        # },
        legend2={
            # "title": "Forecast",
            # "orientation":"h",
            "yanchor": "bottom",
            "xanchor": "right",
            "yref": "paper",
            "x": 0.99,
            "y": 0.01,
        },
    )

    today = pd.Timestamp.today(tz=tz)
    fig.add_shape(  # add a vertical line (now)
        type="line",
        line_color="#1B8A85",
        line_width=2,
        opacity=1,
        line_dash="dot",
        x0=today,
        x1=today,
        y0=0,
        y1=0.95,
        xref="x",
        yref="paper",
    )
    fig.add_annotation(  # add a marker for today
        text="now",
        x=today,
        y=1.1,
        yref="paper",
        showarrow=False,
        font={"color": "gray"},
        bgcolor="white",
    )
    # fig.layout.legend.itemwidth = 30
    return fig


def create_horizontal_bar_chart(data_df: pd.DataFrame, title: str) -> go.Figure:
    if data_df.empty:
        return None
    color_sequences_copy = copy.deepcopy(color_sequences)

    fig = go.Figure(
        go.Bar(
            x=data_df["capacity"],
            y=data_df.reset_index()["index"],
            orientation="h",
            marker_color="whitesmoke",
            name="Installed Capacity",
            showlegend=True,
        )
    )

    fig.add_trace(
        go.Bar(
            x=data_df["Daily Mean Aggregated"],
            y=data_df.reset_index()["index"],
            orientation="h",
            text=data_df["CF_Day"],
            texttemplate="%{text:.1%}",
            textposition="outside",
            # marker_color=SECONDARY_COLOR,
            name="Daily Mean Aggregated",  # will be monthly?!
            # marker=dict(color=data_df["capacity"],colorscale=px.colors.sequential.Viridis), #Blugrn
            marker_color=[
                get_color(source, color_sequences_copy) for source in data_df.index
            ],
        ),
    )
    fig.add_trace(go.Scatter(x=[], y=[], name="yaxis data"))

    fig.update_layout(
        title=dict(
            text="Capacity Factor by Source (last 24 Hours)",
            yanchor="top",
            y=0.95,
            xanchor="center",
            x=0.5,
            font={"size": TITLE_SIZE, "color": TEXT_COLOR},
        ),
        barmode="overlay",
        yaxis=dict(
            anchor="free",
            position=0.99,
        ),
        margin=dict(l=30, r=30, t=80),
        xaxis=dict(title="installed capacity, aggregated [MW] / capacity factor [%]"),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=1.1,
            xanchor="center",
            x=0.5,
        ),
    )

    return fig


def create_gauge(value, indicator_suffix, indicator_title, threshold, sub_text):
    max_bound = max(1, math.ceil(threshold))

    fig = go.Figure()

    fig.update_layout(
        autosize=False,
        width=200,
        height=150,
        margin=dict(l=30, r=30, t=0, b=0, pad=5),  # pad=8
    )

    fig.add_trace(
        go.Indicator(
            mode="gauge",
            value=value,
            # number={
            #     "suffix": "<span style='color:gray'>" + indicator_suffix + "</span>",
            #     "font.size": TITLE_SIZE,
            # },
            gauge={
                "axis": {
                    "range": [0, max_bound],
                    "tickwidth": 1,
                    "nticks": 10,
                },
                "threshold": {
                    "line": {"color": "red", "width": 2},
                    "thickness": 0.9,
                    "value": threshold,
                },
                "bar": {"color": SECONDARY_COLOR},
            },
            title={
                # "text": "<span style='font-size:1rem'>" + indicator_title + "</span>",
                "text": indicator_title
                + "<br><span style='font-size:0.8em; color:gray'>"
                + sub_text
                + "</span>",
                "font": {"size": 15},
            },
            # domain={"x": [0, 1], "y": [0.25,0.75]},
            domain={"x": [0, 1], "y": [0.1, 0.5]},
        )
    )

    # fig.add_trace(go.Indicator(
    #     mode = "number",
    #     value = value,
    #     number={
    #         "suffix": "<span style='color:gray'>" + indicator_suffix + "</span>",
    #         "font.size": TITLE_SIZE,
    #     },

    #     #delta = {'reference': 400, 'relative': True},
    #     domain = {'x': [0, 1], 'y': [0, 0.25]}
    #    )
    # )

    # fig.add_trace(go.Scatter(x=[0,1,2], y=[0,2,0], fill="toself", color="black"))
    print(value)
    y_offset = 0.1
    radius = 0.4
    width = 0.02

    theta = value / max_bound * 180
    theta_rad = theta / 180 * math.pi

    x0 = 0.5 - math.sin(theta_rad) * width
    y0 = y_offset - math.cos(theta_rad) * width

    x1 = 0.5 * (1 - math.cos(theta_rad))
    y1 = y_offset + math.sin(theta_rad) * radius

    x2 = 0.5 + math.sin(theta_rad) * width
    y2 = y_offset + math.cos(theta_rad) * width

    print(f"{theta=} {x1=} {y1=}")
    # fig.add_shape(
    fig.update_layout(
        xaxis={"showgrid": False, "showticklabels": False, "range": [0, 1]},
        yaxis={"showgrid": False, "showticklabels": False, "range": [0, 1]},
        shapes=[
            dict(
                type="path",
                path=f" M {x0} {y0} L {x1} {y1} L {x2} {y2} Z",
                fillcolor="black",
                # line_color="black",
                # line_width=1,
                # opacity=1,
                # line_dash="dot",
                # x0=0.5,
                # x1=x1,
                # y0=0.3,
                # y1=y1+0.12,
                xref="x",
                # xref="paper",
                yref="y",
            ),
            go.layout.Shape(
                type="circle",
                x0=0.5 - width,
                x1=0.5 + width,
                y0=y_offset - width,
                y1=y_offset + width,
                fillcolor="#333",
                line_color="#333",
            ),
        ],
    )
    # fig.add_annotation(  # add a text callout
    #     text="<span style='font-size:0.7rem'>" + sub_text + "</span>", x=0.5, y=0, yref="paper",xanchor="center", showarrow=False, bgcolor="white",
    #     #domain={'x': [0,1], 'y':[0.7,1]}
    # )

    return fig


def create_metrics(label, value, tz, data_df=None, prefix="", suffix=""):
    fig = go.Figure()

    fig.add_trace(
        go.Indicator(
            value=round(value, 2),
            gauge={"axis": {"visible": False}},
            number={
                "prefix": prefix,
                "suffix": suffix,
                "font.size": 24,
            },
            # title={
            #     "text": label,
            #     "font": {"size": 24},
            # },
            domain={"x": [0.0, 1.0], "y": [0.5, 1]},
        )
    )

    if data_df is not None:
        color_sequence = px.colors.sequential.Teal[2::2]
        for color, column in zip(color_sequence, data_df.columns):
            fig.add_trace(
                go.Scatter(
                    # data,
                    x=data_df.index[::2],
                    y=data_df[column][::2],
                    # hoverinfo="skip",
                    fill="tozeroy",
                    line={
                        "color": color,
                        "width": 1.2,
                    },
                    name=column,
                )
            )

        this_year = pd.Timestamp.today(tz=tz).year
        last_entry = data_df[this_year].last_valid_index()
        fig.add_trace(
            go.Scatter(
                x=[last_entry],
                y=[data_df[this_year].loc[last_entry]],
                # hoverinfo="skip",
                mode="markers",
                showlegend=False,
                marker=dict(
                    color=SECONDARY_COLOR,
                ),
            )
        )
        fig.add_annotation(
            x=last_entry,
            y=0.0,
            text="today",
            showarrow=False,
            xanchor="center",
            yanchor="bottom",
        )
        fig.add_annotation(
            x=int(last_entry + (365 - last_entry) / 2),
            y=0.0,
            text=min(data_df.columns),
            font={"color": "gray"},
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
        )

    fig.update_xaxes(visible=False, fixedrange=True)
    fig.update_yaxes(visible=False, fixedrange=True)
    fig.update_layout(
        # paper_bgcolor="lightgrey",
        margin=dict(t=10, b=0),
        showlegend=False,
        plot_bgcolor="white",
        height=70,
        width=200,
    )

    return fig


def create_pie_chart(df, datetime):
    color_sequences_copy = copy.deepcopy(color_sequences)
    # fig = go.Figure()

    colors = {
        source_type: get_color(source_type, color_sequences_copy)
        for source_type in df.index
    }
    print(colors)
    total = df.sum()
    # print(df[df["data"]/float(total) > 0.005]["data"],)
    # df.drop(df[df["data"]/float(total) < 0.005].index, inplace=True)
    # fig.add_trace(
    #     go.Pie(
    #         values=df["data"],
    #         labels=df.index,
    #         #textinfo="percent",
    #         #showlegend=False,
    #         #insidetextorientation='radial',
    #         marker=dict(colors=pd.Series(colors)),
    #         sort=False,
    #     )
    # )
    fig = px.pie(
        df.reset_index(),
        values="data",
        names="index",
        color="index",
        color_discrete_map=colors,
        title=f"Current Power Mix: {datetime: %d.%m.%Y %H:%M}",
    )

    fig.update_traces(
        sort=False,
        textinfo="percent",
    )

    fig.update_layout(
        margin=dict(t=70, b=90),
        # height=250,
        # width=200,
        title=dict(
            yanchor="top",
            y=0.95,
            xanchor="center",
            x=0.5,
            font={"size": TITLE_SIZE, "color": TEXT_COLOR},
        ),
    )

    return fig


def create_map(df, country_code: str):
    df = pd.DataFrame(data={"iso_alpha": "DEU"}, index=[1])
    fig = px.choropleth(
        df,
        locations="iso_alpha",
        scope="europe",
        color=[1],
        # color="renewable_share", # lifeExp is a column of gapminder
        # hover_name="country", # column to add to hover information
        color_continuous_scale="Darkmint",
        # locationmode='USA-states',
    )
    fig.update_geos(
        # fitbounds="locations",
        showcountries=True,
        countrycolor="Black",
        # projection_type="orthographic",
        visible=True,
        showlakes=True,
        lakecolor="Blue",
        showrivers=True,
        rivercolor="Blue",
    )
    fig.update_layout(
        margin=dict(t=0, b=0),
        height=250,
        showlegend=False,
        autosize=True,
        geo=dict(projection_scale=1.5),
    )
    fig.update_coloraxes(showscale=False)

    return fig

    # https://stackoverflow.com/questions/72496150/user-friendly-names-for-plotly-css-colors
    # https://python-charts.com/spatial/choropleth-map-plotly/


if __name__ == "__main__":
    import streamlit as st

    c1, c2 = st.columns([1, 2])
    fig = create_gauge(2.0, "TWh", "Total Power Generation", 5.8, "Yesterday")
    c1.plotly_chart(fig, theme="streamlit", use_container_width=False)
    c2.plotly_chart(fig, theme="streamlit", use_container_width=False)
