import dash
from dash import dcc, html, Input, Output
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

app = dash.Dash(__name__)
server = app.server

# Custom index string for manifest support
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        <!-- Link to the manifest file -->
        <link rel="manifest" href="/assets/manifest.json">
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

CSV_PATH = "weather_station_data.csv"

def load_data():
    try:
        df = pd.read_csv(
            CSV_PATH,
            parse_dates=["timestamp"],
            date_format="%Y-%m-%d %H:%M:%S"
        )
        print("Sample timestamps:", df["timestamp"].head())

        numeric_cols = [
            col for col in df.columns
            if col not in [
                "timestamp",
                "Lightning Detection (AS3935)",
                "Rain Event (LM393)"
            ]
        ]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

        # Forward-fill a few key columns if needed
        ffilled_cols = [
            "Temperature (BME280) (°C)",
            "Humidity (BME280) (%)",
            "Pressure (BME280) (hPa)",
            "Light Intensity (BH1750) (lux)"
        ]
        df[ffilled_cols] = df[ffilled_cols].ffill()

        print("Data shape:", df.shape)
        print("Min/Max timestamps:", df["timestamp"].min(), df["timestamp"].max())

        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

def create_line_figure(df, y_cols, title, ytitle):
    fig = go.Figure()
    for col in y_cols:
        if col in df.columns:
            fig.add_trace(
                go.Scattergl(
                    x=df["timestamp"],
                    y=df[col],
                    mode="lines",
                    name=col.split("(")[0].strip(),
                    line=dict(width=1)
                )
            )

    fig.update_layout(
        xaxis=dict(
            type="date",
            showticklabels=False,
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030",
        ),
        yaxis=dict(
            title=ytitle,
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030",
        ),
        margin=dict(b=80, t=40, l=60, r=30),
        title=dict(text=title, x=0.05, xanchor="left"),
        height=500,
        plot_bgcolor="white",
        dragmode="zoom"
    )
    return fig

def create_bar_figure(df, col, title, ytitle):
    fig = go.Figure()
    if col in df.columns:
        fig.add_trace(
            go.Bar(
                x=df["timestamp"],
                y=df[col],
                name=col.split(" (")[0],
                marker_color="royalblue"
            )
        )

    fig.update_layout(
        xaxis=dict(
            type="date",
            showticklabels=False,
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030",
        ),
        yaxis=dict(
            title=ytitle,
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030",
        ),
        margin=dict(b=80, t=40, l=60, r=30),
        title=dict(text=title, x=0.05, xanchor="left"),
        height=500,
        plot_bgcolor="white",
        dragmode="zoom"
    )
    return fig

def create_wind_rose(df):
    if df.empty or "Wind Direction (Wind Vane) (deg)" not in df.columns:
        return go.Figure()

    try:
        wind_df = df[["Wind Direction (Wind Vane) (deg)", "Wind Speed (Anemometer) (m/s)"]].copy()
        wind_df["direction"] = wind_df["Wind Direction (Wind Vane) (deg)"] % 360

        bins = np.arange(-11.25, 348.76, 22.5)
        labels = [
            "N", "NNE", "NE", "ENE", "E", "ESE",
            "SE", "SSE", "S", "SSW", "SW", "WSW",
            "W", "WNW", "NW", "NNW"
        ]
        wind_df["direction"] = pd.cut(
            wind_df["direction"],
            bins=bins,
            labels=labels,
            include_lowest=True
        )

        speed_bins = [0, 1, 2, 3, 4, 5, 6, 20]
        speed_labels = ["0-1", "1-2", "2-3", "3-4", "4-5", "5-6", "6+"]
        wind_df["strength"] = pd.cut(
            wind_df["Wind Speed (Anemometer) (m/s)"],
            bins=speed_bins,
            labels=speed_labels
        )

        wind_df = wind_df.groupby(["direction", "strength"], observed=False).size().reset_index(name="frequency")

        fig = px.bar_polar(
            wind_df,
            r="frequency",
            theta="direction",
            color="strength",
            template="plotly_white",
            color_discrete_sequence=px.colors.sequential.Plasma_r,
            direction="clockwise",
            start_angle=90
        )

        fig.update_layout(
            polar=dict(
                angularaxis=dict(
                    tickvals=np.arange(0, 360, 22.5),
                    ticktext=labels,
                    gridcolor="#f0f0f0"
                ),
                radialaxis=dict(visible=False),
                bgcolor="white"
            ),
            title="Wind Rose",
            height=500,
            margin=dict(t=80, b=80, l=80, r=80),
            legend=dict(
                title="Wind Speed (m/s)",
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )
        return fig
    except Exception as e:
        print(f"Wind rose error: {e}")
        return go.Figure()

def create_temperature_figure(df):
    fig = go.Figure()

    # MCP9808 (red)
    col_mcp = "Temperature (MCP9808) (°C)"
    if col_mcp in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=df["timestamp"],
                y=df[col_mcp],
                mode="lines",
                name="MCP9808",
                line=dict(width=1, color="red")
            )
        )

    # BME280 (blue)
    col_bme = "Temperature (BME280) (°C)"
    if col_bme in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=df["timestamp"],
                y=df[col_bme],
                mode="lines",
                name="BME280",
                line=dict(width=1, color="blue")
            )
        )

    fig.update_layout(
        xaxis=dict(
            type="date",
            showticklabels=False,
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030",
        ),
        yaxis=dict(
            title="°C",
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030",
        ),
        margin=dict(b=80, t=40, l=60, r=30),
        title=dict(text="Temperature", x=0.05, xanchor="left"),
        height=500,
        plot_bgcolor="white",
        dragmode="zoom",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="center",
            x=0.5,
            traceorder="normal"
        )
    )

    return fig

def create_air_quality_figure(df):
    fig = go.Figure()
    cols = [
        "PM1.0 (PMSA003I) (µg/m³)",
        "PM2.5 (PMSA003I) (µg/m³)",
        "PM10.0 (PMSA003I) (µg/m³)",
    ]
    for col in cols:
        if col in df.columns:
            short_name = col.split("(")[0].strip()
            fig.add_trace(
                go.Scattergl(
                    x=df["timestamp"],
                    y=df[col],
                    mode="lines",
                    name=short_name,
                    line=dict(width=1)
                )
            )

    fig.update_layout(
        xaxis=dict(
            type="date",
            showticklabels=False,
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030",
        ),
        yaxis=dict(
            title="µg/m³",
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030",
        ),
        margin=dict(b=80, t=40, l=60, r=30),
        title=dict(text="Air Quality Monitoring", x=0.05, xanchor="left"),
        height=500,
        plot_bgcolor="white",
        dragmode="zoom",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="center",
            x=0.5,
            traceorder="normal"
        )
    )

    return fig

# Updated layout with tabs for each plot
app.layout = html.Div(
    [
        html.H1(
            "Weather Station Dashboard",
            style={"textAlign": "center", "marginBottom": "30px"}
        ),
        dcc.Interval(id="interval", interval=5000),
        dcc.Tabs(
            id="tabs",
            value="Temperature",
            children=[
                dcc.Tab(label="Temperature", value="Temperature"),
                dcc.Tab(label="Humidity", value="Humidity"),
                dcc.Tab(label="Atmospheric Pressure", value="Atmospheric Pressure"),
                dcc.Tab(label="Light Intensity", value="Light Intensity"),
                dcc.Tab(label="UV Index", value="UV Index"),
                dcc.Tab(label="Wind Rose", value="Wind Rose"),
                dcc.Tab(label="Air Quality Monitoring", value="Air Quality Monitoring"),
                dcc.Tab(label="Rain Accumulation", value="Rain Accumulation"),
            ]
        ),
        html.Div(id="tabs-content")
    ],
    style={
        "padding": "40px",
        "maxWidth": "1200px",
        "margin": "0 auto",
        "backgroundColor": "#f8f8f8",
        "color": "#333333",
        "fontFamily": "Arial, sans-serif"
    }
)

# Callback to update tab content based on selected tab and interval refresh
@app.callback(
    Output("tabs-content", "children"),
    [Input("tabs", "value"),
     Input("interval", "n_intervals")]
)
def render_content(tab, n_intervals):
    df = load_data()
    
    if tab == "Temperature":
        fig = create_temperature_figure(df)
    elif tab == "Humidity":
        fig = create_line_figure(df, ["Humidity (BME280) (%)"], "Humidity", "%")
    elif tab == "Atmospheric Pressure":
        fig = create_line_figure(df, ["Pressure (BME280) (hPa)"], "Atmospheric Pressure", "hPa")
    elif tab == "Light Intensity":
        fig = create_line_figure(df, ["Light Intensity (BH1750) (lux)"], "Light Intensity", "lux")
    elif tab == "UV Index":
        fig = create_line_figure(df, ["UV Index (GY-8511)"], "UV Index", "")
    elif tab == "Wind Rose":
        fig = create_wind_rose(df)
    elif tab == "Air Quality Monitoring":
        fig = create_air_quality_figure(df)
    elif tab == "Rain Accumulation":
        fig = create_bar_figure(df, "Rain Accumulation (SEN0575) (mm)", "Rain Accumulation", "mm")
    else:
        fig = go.Figure()

    return dcc.Graph(figure=fig, className="dash-graph")

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=False)
