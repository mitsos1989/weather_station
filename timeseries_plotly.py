import dash
from dash import dcc, html, Input, Output
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
import os, glob, base64

# Include Roboto font from Google Fonts
external_stylesheets = ['https://fonts.googleapis.com/css?family=Roboto:400,700']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server

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
        <style>
          /* Keyframes for blinking effect */
          @keyframes blinker {
              50% { opacity: 0; }
          }
        </style>
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
        # Read CSV and parse timestamps
        df = pd.read_csv(
            CSV_PATH,
            parse_dates=["timestamp"],
            date_format="%Y-%m-%d %H:%M:%S"
        )
        # Localize the naive timestamps to UTC (data are in UTC)
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        
        # Get current time in Greece (Europe/Athens)
        now_greece = datetime.now(ZoneInfo("Europe/Athens"))
        threshold = now_greece - timedelta(hours=24)
        threshold_utc = threshold.astimezone(ZoneInfo("UTC"))
        # Filter for the last 24 hours
        df = df[df["timestamp"] >= threshold_utc]
        
        numeric_cols = [
            col for col in df.columns
            if col not in ["timestamp", "Lightning Detection (AS3935)", "Rain Event (LM393)"]
        ]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        
        ffilled_cols = [
            "Temperature (BME280) (°C)",
            "Humidity (BME280) (%)",
            "Pressure (BME280) (hPa)",
            "Light Intensity (BH1750) (lux)"
        ]
        df[ffilled_cols] = df[ffilled_cols].ffill()
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

def get_latest_cloud_camera_image():
    files = glob.glob("whole_sky_camera/*.jpg")
    if not files:
        return None
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return "data:image/jpeg;base64," + encoded

# Common font settings for figures
common_font = dict(family="Roboto, sans-serif")
title_font = dict(size=20, family="Roboto, sans-serif")
axis_title_font = dict(size=16, family="Roboto, sans-serif")
tick_font = dict(size=14, family="Roboto, sans-serif")
legend_font = dict(size=16, family="Roboto, sans-serif")

# Update each plotting function to include a landscape width (900px)

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
                    line=dict(width=2)
                )
            )
    fig.update_layout(
        xaxis=dict(
            type="date",
            tickformat="%H:%M",  # Display time in hh:mm format
            showticklabels=True,
            tickfont=tick_font,
            title=dict(text="", font=axis_title_font),
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        yaxis=dict(
            title=dict(text=ytitle, font=axis_title_font),
            tickfont=tick_font,
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        margin=dict(b=80, t=40, l=60, r=30),
        title=dict(text=title, x=0.05, xanchor="left", font=title_font),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode="zoom",
        font=common_font,
        legend=dict(
            orientation="h",
            font=legend_font,
            x=0.5,
            xanchor="center",
            y=-0.2,
            yanchor="top"
        )
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
            showticklabels=True,
            tickfont=tick_font,
            title=dict(text="", font=axis_title_font),
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        yaxis=dict(
            title=dict(text=ytitle, font=axis_title_font),
            tickfont=tick_font,
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        margin=dict(b=80, t=40, l=60, r=30),
        title=dict(text=title, x=0.05, xanchor="left", font=title_font),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode="zoom",
        font=common_font,
        legend=dict(
            orientation="h",
            font=legend_font,
            x=0.5,
            xanchor="center",
            y=-0.2,
            yanchor="top"
        )
    )
    return fig

def create_wind_rose(df):
    if df.empty or "Wind Direction (Wind Vane) (deg)" not in df.columns:
        return go.Figure()
    try:
        wind_df = df[["Wind Direction (Wind Vane) (deg)", "Wind Speed (Anemometer) (m/s)"]].copy()
        wind_df["direction"] = wind_df["Wind Direction (Wind Vane) (deg)"] % 360
        bins = np.arange(-11.25, 348.76, 22.5)
        labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
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
                    tickfont=tick_font,
                    gridcolor="#f0f0f0"
                ),
                radialaxis=dict(visible=False),
                bgcolor="whitesmoke"
            ),
            title=dict(text="Wind Rose", font=title_font),
            width=900,
            height=500,
            margin=dict(t=80, b=80, l=80, r=80),
            font=common_font,
            legend=dict(
                orientation="h",
                font=legend_font,
                x=0.5,
                xanchor="center",
                y=-0.2,
                yanchor="top"
            )
        )
        return fig
    except Exception as e:
        print(f"Wind rose error: {e}")
        return go.Figure()

def create_temperature_figure(df):
    fig = go.Figure()
    col_mcp = "Temperature (MCP9808) (°C)"
    if col_mcp in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=df["timestamp"],
                y=df[col_mcp],
                mode="lines",
                name="MCP9808",
                line=dict(width=2, color="red")
            )
        )
    col_bme = "Temperature (BME280) (°C)"
    if col_bme in df.columns:
        fig.add_trace(
            go.Scattergl(
                x=df["timestamp"],
                y=df[col_bme],
                mode="lines",
                name="BME280",
                line=dict(width=2, color="blue")
            )
        )
    fig.update_layout(
        xaxis=dict(
            type="date",
            showticklabels=True,
            tickfont=tick_font,
            title=dict(text="", font=axis_title_font),
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        yaxis=dict(
            title=dict(text="°C", font=axis_title_font),
            tickfont=tick_font,
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        margin=dict(b=80, t=40, l=60, r=30),
        title=dict(text="Temperature", x=0.05, xanchor="left", font=title_font),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode="zoom",
        font=common_font,
        legend=dict(
            orientation="h",
            font=legend_font,
            x=0.5,
            xanchor="center",
            y=-0.2,
            yanchor="top"
        )
    )
    return fig

def create_air_quality_figure(df):
    fig = go.Figure()
    # Define threshold values (µg/m³)
    thresholds = {"PM1.0": 20, "PM2.5": 25, "PM10.0": 50}
    cols = [
        "PM1.0 (PMSA003I) (µg/m³)",
        "PM2.5 (PMSA003I) (µg/m³)",
        "PM10.0 (PMSA003I) (µg/m³)"
    ]
    for col in cols:
        if col in df.columns:
            short_name = col.split("(")[0].strip()  # e.g., "PM1.0"
            # For PM10.0, use the specified transparent green color
            if short_name == "PM10.0":
                line_props = dict(width=2, shape='spline', smoothing=0.8, color='rgba(0, 128, 0, 0.5)')
            else:
                line_props = dict(width=2, shape='spline', smoothing=0.8)
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[col],
                    mode="lines",
                    name=short_name,
                    line=line_props
                )
            )
    # Add threshold lines and labels
    for pollutant, thresh in thresholds.items():
        if any(pollutant in trace.name for trace in fig.data):
            fig.add_shape(
                type="line",
                xref="paper", x0=0, x1=1,
                yref="y",
                y0=thresh, y1=thresh,
                line=dict(dash="dash", width=2, color="black")
            )
            fig.add_annotation(
                xref="paper",
                x=1.01,
                y=thresh,
                yshift=10,  # move label up a bit
                text=f"<b>{pollutant} ({thresh} µg/m³)</b>",
                showarrow=False,
                font=axis_title_font
            )
    fig.update_layout(
        xaxis=dict(
            type="date",
            tickformat="%H:%M",
            showticklabels=True,
            tickfont=tick_font,
            title=dict(text="", font=axis_title_font),
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        yaxis=dict(
            title=dict(text="Concentration (µg/m³)", font=axis_title_font),
            tickfont=tick_font,
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        margin=dict(b=80, t=40, l=60, r=100),
        title=dict(text="Air Quality Monitoring", x=0.05, xanchor="left", font=title_font),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode="zoom",
        font=common_font,
        legend=dict(
            orientation="h",
            font=legend_font,
            x=0.5,
            xanchor="center",
            y=-0.2,
            yanchor="top"
        )
    )
    return fig

# Updated header: only the clear foreground title remains.
header = html.Div(
    html.Div(
        [
            "Experimental Environmental",
            html.Br(),
            "Monitoring Station"
        ],
        className="title-foreground",
        style={
            "textAlign": "center",
            "lineHeight": "1.2",
            "fontSize": "24px",
            "fontWeight": "bold",
            "color": "#333"
        }
    ),
    style={
        "padding": "20px",
        "border": "1px solid #ccc",
        "borderRadius": "10px",
        "margin": "0 auto",
        "maxWidth": "500px",
        "backgroundColor": "rgba(255, 255, 255, 0.8)",
        "marginBottom": "30px"
    }
)

# Footer to display designer credit
footer = html.Footer(
    "Designed by Dimitris Mitropoulos",
    style={
        "position": "fixed",
        "bottom": "10px",
        "right": "10px",
        "fontSize": "12px",
        "color": "#666",
        "fontFamily": "Roboto, sans-serif"
    }
)

# Define smaller tab styling
tab_style = {
    "padding": "5px 10px",
    "fontSize": "12px",
    "minHeight": "30px",
    "fontFamily": "Roboto, sans-serif"
}
tab_selected_style = {
    "padding": "5px 10px",
    "fontSize": "12px",
    "minHeight": "30px",
    "fontFamily": "Roboto, sans-serif",
    "backgroundColor": "#ddd",
    "borderBottom": "2px solid #333"
}

# Station status indicator placeholder (we'll update its content via a callback)
station_status = html.Div(id="station-status", style={"textAlign": "center", "marginBottom": "20px"})

# Updated layout with the new "Cloud Camera" tab included.
app.layout = html.Div(
    [
        header,
        station_status,  # Displays last read timestamp and online/offline status
        dcc.Interval(id="interval", interval=5000),
        dcc.Tabs(
            id="tabs",
            value="Temperature",
            children=[
                dcc.Tab(label="Temperature", value="Temperature", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Humidity", value="Humidity", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Atmospheric Pressure", value="Atmospheric Pressure", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Light Intensity", value="Light Intensity", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="UV Index", value="UV Index", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Wind Rose", value="Wind Rose", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Air Quality Monitoring", value="Air Quality Monitoring", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Rain Accumulation", value="Rain Accumulation", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Cloud Camera", value="Cloud Camera", style=tab_style, selected_style=tab_selected_style)
            ],
            persistence=True,
            persistence_type="session",
            style={"display": "grid", "gridTemplateColumns": "repeat(2, 1fr)"}
        ),
        html.Div(id="tabs-content", style={"transition": "opacity 0.5s ease"}),
        footer
    ],
    style={
        "padding": "40px",
        "maxWidth": "1200px",
        "margin": "0 auto",
        "backgroundColor": "#f8f8f8",
        "backgroundImage": "url('/assets/background.png')",
        "backgroundRepeat": "repeat",
        "backgroundSize": "contain",
        "color": "#333333",
        "fontFamily": "Roboto, sans-serif"
    }
)


# Callback to update tab content with a loading effect during data refresh
@app.callback(
    Output("tabs-content", "children"),
    [Input("tabs", "value"),
     Input("interval", "n_intervals")]
)
def render_content(tab, n_intervals):
    df = load_data()
    if tab == "Temperature":
        fig = create_temperature_figure(df)
        content = dcc.Graph(figure=fig, className="dash-graph")
    elif tab == "Humidity":
        fig = create_line_figure(df, ["Humidity (BME280) (%)"], "Humidity", "%")
        content = dcc.Graph(figure=fig, className="dash-graph")
    elif tab == "Atmospheric Pressure":
        fig = create_line_figure(df, ["Pressure (BME280) (hPa)"], "Atmospheric Pressure", "hPa")
        content = dcc.Graph(figure=fig, className="dash-graph")
    elif tab == "Light Intensity":
        fig = create_line_figure(df, ["Light Intensity (BH1750) (lux)"], "Light Intensity", "lux")
        content = dcc.Graph(figure=fig, className="dash-graph")
    elif tab == "UV Index":
        fig = create_line_figure(df, ["UV Index (GY-8511)"], "UV Index", "")
        content = dcc.Graph(figure=fig, className="dash-graph")
    elif tab == "Wind Rose":
        fig = create_wind_rose(df)
        content = dcc.Graph(figure=fig, className="dash-graph")
    elif tab == "Air Quality Monitoring":
        fig = create_air_quality_figure(df)
        content = dcc.Graph(figure=fig, className="dash-graph")
    elif tab == "Rain Accumulation":
        fig = create_bar_figure(df, "Rain Accumulation (SEN0575) (mm)", "Rain Accumulation", "mm")
        content = dcc.Graph(figure=fig, className="dash-graph")
    elif tab == "Cloud Camera":
        img_src = get_latest_cloud_camera_image()
        if img_src is None:
            content = html.Div("No image found in whole_sky_camera folder.", style={"textAlign": "center", "padding": "20px"})
        else:
            content = html.Div(
                html.Img(src=img_src, style={"maxWidth": "100%", "height": "auto"}),
                style={"textAlign": "center", "padding": "20px"}
            )
    else:
        content = html.Div("No content available.", style={"textAlign": "center"})
    
    return dcc.Loading(
        children=content,
        type="circle",
        fullscreen=False
    )

# New callback to update station status and last data timestamp

@app.callback(
    Output("station-status", "children"),
    [Input("interval", "n_intervals")]
)
def update_station_status(n_intervals):
    df = load_data()
    if df.empty or df["timestamp"].max() is None:
        return html.Div("No data available", style={"color": "gray"})
    last_ts = df["timestamp"].max()  # Timestamp in UTC
    last_ts_greece = last_ts.astimezone(ZoneInfo("Europe/Athens"))
    now_greece = datetime.now(ZoneInfo("Europe/Athens"))
    diff_minutes = (now_greece - last_ts_greece).total_seconds() / 60.0
    if diff_minutes > 30:
        status_text = "Station is OFFLINE"
        indicator = html.Span(
            "",
            style={
                "display": "inline-block",
                "width": "15px",
                "height": "15px",
                "borderRadius": "50%",
                "backgroundColor": "red",
                "marginRight": "10px",
                "animation": "blinker 1s linear infinite"
            }
        )
    else:
        status_text = "Station is Online"
        indicator = html.Span(
            "",
            style={
                "display": "inline-block",
                "width": "15px",
                "height": "15px",
                "borderRadius": "50%",
                "backgroundColor": "green",
                "marginRight": "10px"
            }
        )
    ts_str = last_ts_greece.strftime("%Y-%m-%d %H:%M:%S")
    return html.Div(
        [indicator, html.Span(f"{status_text} (Last data at: {ts_str})")],
        style={
            "fontSize": "16px",
            "fontFamily": "Roboto, sans-serif",
            "padding": "20px",
            "border": "1px solid #ccc",
            "borderRadius": "10px",
            "margin": "0 auto",
            "maxWidth": "500px",
            "backgroundColor": "rgba(255, 255, 255, 0.8)",
            "marginBottom": "30px",
            "textAlign": "center"
        }
    )

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=False)
