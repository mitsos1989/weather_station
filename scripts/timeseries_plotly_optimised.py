import os, glob, base64
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

import dash
from dash import dcc, html, Input, Output
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo  # Python 3.9+
import io
import math
import ephem
import imageio

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN not found. Make sure it's set in your .env file.")




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

cached_df = None
last_load_time = None
CACHE_TIMEOUT_SECONDS = 4 # Update interval is 5s, so we cache for 4s

CSV_PATH = "weather_station_data.csv"

def load_data():
    global cached_df, last_load_time
    now = datetime.now()

    # 1. Check if a valid cache exists and is fresh
    if cached_df is not None and last_load_time is not None:
        if (now - last_load_time).total_seconds() < CACHE_TIMEOUT_SECONDS:
            return cached_df

    # 2. If cache is stale, load new data
    try:
        # --- OPTIMIZATION V2: Correctly read the tail of the CSV ---
        num_lines_to_read = 5000
        
        with open(CSV_PATH, "rb") as f:
            # Go to the end of the file to determine its size
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            buffer = bytearray()
            
            # Read backwards from the end of the file in chunks
            while pos > 0 and buffer.count(b'\n') < num_lines_to_read + 1:
                # Determine how far back to move the cursor
                seek_amount = min(pos, 4096)
                pos -= seek_amount
                
                # Move the cursor and read the chunk
                f.seek(pos)
                buffer = f.read(seek_amount) + buffer

        # Decode the byte buffer to a string
        tail_str = buffer.decode('utf-8', errors='ignore')
        
        # We might have started reading mid-line. Find the first full newline
        # and take everything after it to ensure we have complete rows.
        first_newline_pos = tail_str.find('\n')
        if first_newline_pos != -1:
            tail_str = tail_str[first_newline_pos + 1:]

        # Get the header row from the top of the file
        with open(CSV_PATH, 'r') as f:
            header = f.readline()
        
        # Combine the header with the tail data
        final_csv_data = header + tail_str
        
        # Read this smaller dataset into pandas
        df = pd.read_csv(
            io.StringIO(final_csv_data),
            parse_dates=["timestamp"], # This should now work reliably
            date_format="%Y-%m-%d %H:%M:%S",
            low_memory=False
        )

        # --- The rest of your processing logic remains the same ---
        # Localize the naive timestamps to UTC (data are in UTC)
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

        # Filter for the last 24 hours. Use .copy() to prevent pandas warnings.
        now_greece = datetime.now(ZoneInfo("Europe/Athens"))
        threshold = now_greece - timedelta(hours=24)
        threshold_utc = threshold.astimezone(ZoneInfo("UTC"))
        df = df[df["timestamp"] >= threshold_utc].copy()

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

        # Update the cache
        cached_df = df
        last_load_time = now
        return df

    except FileNotFoundError:
        print(f"Error: {CSV_PATH} not found.")
        cached_df = None
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading data: {e}")
        cached_df = None
        return pd.DataFrame()


def get_latest_cloud_camera_image():
    files = glob.glob("whole_sky_camera/*.jpg")
    if not files:
        return None
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return "data:image/jpeg;base64," + encoded

def get_camera_gif():
    # Get list of jpg files in the whole_sky_camera folder
    files = glob.glob("whole_sky_camera/*.jpg")
    if not files:
        return None
    # Sort files by creation time descending (latest first)
    files_sorted = sorted(files, key=os.path.getctime, reverse=True)
    # Take the latest 10 images (if there are less than 10, it takes all)
    latest_10_files = files_sorted[:10]
    # Read each image using imageio
    images = [imageio.imread(f) for f in latest_10_files]
    # Create an in-memory binary stream
    gif_bytes = io.BytesIO()
    # Write the images as a GIF to the binary stream. Each frame lasts 0.2 seconds.
    imageio.mimwrite(gif_bytes, images, format="GIF", duration=0.2)
    gif_bytes.seek(0)
    # Encode the binary GIF in base64
    gif_base64 = base64.b64encode(gif_bytes.read()).decode("utf-8")
    return "data:image/gif;base64," + gif_base64



def get_satellite_image():
    path = "/home/dimitris/weather_station/satellite_latest/satellite_greece.jpg"
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return "data:image/jpeg;base64," + encoded

def get_latest_anomaly_map():
    """
    Finds the latest temperature anomaly map from the specified folder,
    encodes it in base64, and returns it as a data URI.
    """
    folder_path = "/home/dimitris/weather_station/temp_anomaly_map/*.png"
    files = glob.glob(folder_path)
    if not files:
        return None
    # Find the latest file based on creation time
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    # Return the data URI for the PNG image
    return "data:image/png;base64," + encoded

def get_latest_upper_air_sounding_image():
    """
    Finds the latest upper air sounding figure from the specified folder,
    encodes it in base64, and returns it as a data URI.
    """
    folder_path = "/home/dimitris/weather_station/upper_air_soundings/*"
    # Look for common image file extensions
    files = [f for f in glob.glob(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not files:
        return None
    # Find the latest file based on creation time
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    # Determine image type from extension for the data URI
    file_ext = os.path.splitext(latest_file)[1][1:].lower()
    if file_ext == 'jpg':
        file_ext = 'jpeg' # common practice for data URIs
    # Return the data URI for the image
    return f"data:image/{file_ext};base64," + encoded

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
                    connectgaps=True,
                    name=col.split("(")[0].strip(),
                    line=dict(width=2)
                )
            )
    fig.update_layout(
        xaxis=dict(
            type="date",
            tickformat="%H:%M",  # Display date and time
            showticklabels=True,
            tickangle=0,
            tickfont=tick_font,
            title=dict(text="Time (UTC)", font=axis_title_font),
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
        margin=dict(b=120, t=40, l=60, r=30),
        title=dict(text=title, x=0.05, xanchor="left", font=title_font),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode=False,
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
    # Set up y-axis configuration.
    yaxis_config = dict(
        title=dict(text=ytitle, font=axis_title_font),
        tickfont=tick_font,
        gridcolor="#f0f0f0",
        showgrid=True,
        showline=True,
        linewidth=2,
        linecolor="#303030"
    )
    # If this is the Rain Accumulation graph, force the minimum to 0.
    if col == "Rain Accumulation (SEN0575) (mm)":
        yaxis_config["rangemode"] = "tozero"

    fig.update_layout(
        xaxis=dict(
            type="date",
            showticklabels=True,
            tickfont=tick_font,
            title=dict(text="Time (UTC)", font=axis_title_font),
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        yaxis=yaxis_config,
        margin=dict(b=120, t=40, l=60, r=30),
        title=dict(text=title, x=0.05, xanchor="left", font=title_font),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode=False,
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

def create_rain_line_figure(df, col, title, ytitle):
    fig = go.Figure()
    if col in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df[col],
                mode="lines",
                name=col.split(" (")[0],
                line=dict(width=2, color="blue"),
                connectgaps=True
            )
        )

    # Force y-axis minimum to 0
    yaxis_config = dict(
        title=dict(text=ytitle, font=axis_title_font),
        tickfont=tick_font,
        gridcolor="#f0f0f0",
        showgrid=True,
        showline=True,
        linewidth=2,
        linecolor="#303030",
        rangemode="tozero"
    )

    fig.update_layout(
        xaxis=dict(
            type="date",
            tickformat="%m-%d %H:%M",
            showticklabels=True,
            tickfont=tick_font,
            title=dict(text="Time (UTC)", font=axis_title_font),
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        yaxis=yaxis_config,
        margin=dict(b=120, t=40, l=60, r=30),
        title=dict(text=title, x=0.05, xanchor="left", font=title_font),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode=False,
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
        wind_df["deg"] = wind_df["Wind Direction (Wind Vane) (deg)"] % 360

        def cardinal_direction(deg):
            if deg < 22.5 or deg >= 337.5:
                return "N"
            elif deg < 67.5:
                return "NE"
            elif deg < 112.5:
                return "E"
            elif deg < 157.5:
                return "SE"
            elif deg < 202.5:
                return "S"
            elif deg < 247.5:
                return "SW"
            elif deg < 292.5:
                return "W"
            elif deg < 337.5:
                return "NW"

        wind_df["cardinal"] = wind_df["deg"].apply(cardinal_direction)

        speed_bins = [0, 1, 2, 3, 4, 5, 6, 7, 10, 15, 25]
        speed_labels = ["0-1", "1-2", "2-3", "3-4", "4-5", "5-6", "6-7", "7-10", "10-15", "15+"]
        wind_df["strength"] = pd.cut(
            wind_df["Wind Speed (Anemometer) (m/s)"],
            bins=speed_bins,
            labels=speed_labels
        )

        wind_df = wind_df.groupby(["cardinal", "strength"], observed=False).size().reset_index(name="frequency")

        fig = px.bar_polar(
            wind_df,
            r="frequency",
            theta="cardinal",
            color="strength",
            labels={"strength": "Wind Speed (m/s)"},
            template="plotly_white",
            color_discrete_sequence=px.colors.sequential.Plasma_r,
            direction="clockwise",
            start_angle=90
        )

        fig.update_layout(
            polar=dict(
                angularaxis=dict(
                    tickmode="array",
                    tickvals=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                    ticktext=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                    categoryorder="array",
                    categoryarray=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                    tickfont=tick_font,
                    gridcolor="#f0f0f0"
                ),
                radialaxis=dict(visible=False),
                bgcolor="whitesmoke"
            ),
            title=dict(text="Wind Rose", font=title_font),
            
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

    # MCP9808 (red) with smaller markers
    col_mcp = "Temperature (MCP9808) (°C)"
    if col_mcp in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df[col_mcp],
                mode="lines+markers",
                name="MCP9808",
                line=dict(width=2, color="red"),
                marker=dict(size=4)
            )
        )

    # BME280 (blue) with slightly transparent line
    col_bme = "Temperature (BME280) (°C)"
    if col_bme in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df[col_bme],
                mode="lines",
                name="BME280",
                line=dict(width=2, color="blue", dash="solid"),
                opacity=0.8
            )
        )

    fig.update_layout(
        xaxis=dict(
            type="date",
            tickformat="%H:%M",
            showticklabels=True,
            tickangle=0,
            tickfont=dict(size=14, family="Roboto, sans-serif"),
            title=dict(text="Time (UTC)", font=dict(size=16, family="Roboto, sans-serif")),
            showgrid=True,
            gridcolor="#f0f0f0",
            rangeslider=dict(visible=False),
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        yaxis=dict(
            title=dict(text="Temperature (°C)", font=dict(size=16, family="Roboto, sans-serif")),
            tickfont=dict(size=14, family="Roboto, sans-serif"),
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        margin=dict(b=120, t=40, l=60, r=30),
        title=dict(text="Temperature", x=0.05, xanchor="left", font=dict(size=20, family="Roboto, sans-serif")),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode=False,
        legend=dict(
            orientation="h",
            font=dict(size=16, family="Roboto, sans-serif"),
            x=0.5,
            xanchor="center",
            y=-0.2,
            yanchor="top"
        )
    )
    return fig

def create_air_quality_figure(df):
    # Ensure the data is sorted by timestamp
    df = df.sort_values("timestamp")

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
            # For PM10.0, use the transparent green color
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
                    connectgaps=True,
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
                yshift=10,
                text=f"<b>{pollutant} ({thresh} µg/m³)</b>",
                showarrow=False,
                font=axis_title_font
            )
    # Extend x-axis range slightly to ensure last point is visible
    if not df.empty:
        max_ts = df["timestamp"].max()
        min_ts = df["timestamp"].min()
        fig.update_layout(
            xaxis=dict(
                range=[min_ts, max_ts + pd.Timedelta(minutes=1)],
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
            )
        )
    fig.update_layout(
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
        dragmode=False,
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

# --- NEW FUNCTION ---
def create_wind_timeseries_figure(df):
    """
    Creates a time series plot for wind speed and wind direction arrows,
    applying a moving average to smooth the data.
    """
    fig = go.Figure()

    # Ensure required columns exist
    if "Wind Speed (Anemometer) (m/s)" not in df.columns or "Wind Direction (Wind Vane) (deg)" not in df.columns:
        fig.add_annotation(text="Wind data not available.", showarrow=False)
        fig.update_layout(width=900, height=500, plot_bgcolor="whitesmoke", font=common_font)
        return fig

    # --- DATA SMOOTHING ---
    # Define the window size for the moving average. Assuming data is every 20s, 30 points = 10 minutes.
    window_size = 30

    # Apply a simple rolling mean to wind speed
    df['speed_smoothed'] = df['Wind Speed (Anemometer) (m/s)'].rolling(window=window_size, center=True, min_periods=1).mean()

    # Apply a circular rolling average to wind direction
    radians = np.deg2rad(df['Wind Direction (Wind Vane) (deg)'])
    x_comp = np.cos(radians)
    y_comp = np.sin(radians)
    x_mean = x_comp.rolling(window=window_size, center=True, min_periods=1).mean()
    y_mean = y_comp.rolling(window=window_size, center=True, min_periods=1).mean()
    avg_radians = np.arctan2(y_mean, x_mean)

    # --- CORRECTION IS HERE: Add 180 degrees to reverse the direction ---
    df['direction_smoothed'] = (np.rad2deg(avg_radians) + 180) % 360

    # 1. Add SMOOTHED Wind Speed Line Trace
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["speed_smoothed"], # Use smoothed data
            mode="lines",
            name="Wind Speed (10-min avg)",
            line=dict(color="royalblue", width=2),
            yaxis="y1"
        )
    )

    # 2. Prepare data for Wind Direction Arrows
    # Take one point every 30 minutes (90 points) for clarity.
    # (30 mins * 60 secs/min) / 20 secs/reading = 90
    df_arrows = df.iloc[::90].copy()

    # 3. Add Wind Direction Arrows Trace from SMOOTHED data
    if not df_arrows.empty:
        fig.add_trace(
            go.Scatter(
                x=df_arrows["timestamp"],
                y=[1] * len(df_arrows),
                mode="markers",
                name="Wind Direction",
                marker=dict(
                    symbol="arrow",
                    color="rgba(200, 30, 30, 0.8)",
                    size=16,
                    angle=df_arrows["direction_smoothed"], # Use smoothed and reversed data
                    angleref="up",
                    line=dict(width=1, color='DarkSlateGrey')
                ),
                yaxis="y2",
                hoverinfo='skip'
            )
        )

    # Create a specific font dictionary for the y-axis title to add color
    y_axis_title_font = axis_title_font.copy()
    y_axis_title_font['color'] = "royalblue"

    # 4. Update Layout with dual Y-axes
    fig.update_layout(
        title=dict(text="Wind Speed and Direction (10-Minute Moving Average)", x=0.05, xanchor="left", font=title_font),
        xaxis=dict(
            title=dict(text="Time (UTC)", font=axis_title_font),
            tickfont=tick_font,
            showgrid=True,
            gridcolor="#f0f0f0",
            showline=True,
            linewidth=2,
            linecolor="#303030",
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            title=dict(text="Wind Speed (m/s)", font=y_axis_title_font),
            tickfont=tick_font,
            gridcolor="#f0f0f0",
            showgrid=True,
            showline=True,
            linewidth=2,
            linecolor="#303030"
        ),
        yaxis2=dict(
            visible=False,
            range=[0, 1.5],
            overlaying="y",
            anchor="x",
            side="right"
        ),
        margin=dict(b=120, t=40, l=60, r=30),
        width=900,
        height=500,
        plot_bgcolor="whitesmoke",
        dragmode=False,
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

def get_moon_phase_and_rise_info():
    """
    Calculates the current moon phase, name, icon, illumination,
    and next moonrise time for Thessaloniki.
    """
    current_dt_utc = datetime.now(ZoneInfo("UTC"))
    obs_date = ephem.Date(current_dt_utc)

    moon = ephem.Moon()
    moon.compute(obs_date)

    illumination_percent = moon.moon_phase * 100

    prev_new_moon_date = ephem.previous_new_moon(obs_date)
    moon_age_days = obs_date - prev_new_moon_date

    synodic_period = 29.530588853
    phase_angle_deg = (moon_age_days / synodic_period) * 360.0

    phase_name = ""
    icon_char = ""

    if phase_angle_deg >= 337.5 or phase_angle_deg < 22.5:
        phase_name = "New Moon"
        icon_char = "🌑"
    elif phase_angle_deg < 67.5:
        phase_name = "Waxing Crescent"
        icon_char = "🌒"
    elif phase_angle_deg < 112.5:
        phase_name = "First Quarter"
        icon_char = "🌓"
    elif phase_angle_deg < 157.5:
        phase_name = "Waxing Gibbous"
        icon_char = "🌔"
    elif phase_angle_deg < 202.5:
        phase_name = "Full Moon"
        icon_char = "🌕"
    elif phase_angle_deg < 247.5:
        phase_name = "Waning Gibbous"
        icon_char = "🌖"
    elif phase_angle_deg < 292.5:
        phase_name = "Last Quarter"
        icon_char = "🌗"
    elif phase_angle_deg < 337.5:
        phase_name = "Waning Crescent"
        icon_char = "🌘"
    else:
        phase_name = "Unknown Phase"
        icon_char = "❔"

    phase_display_str = f"{phase_name} {icon_char} ({illumination_percent:.0f}% illum.)"

    # Moonrise for Thessaloniki
    moonrise_info_str = "Moonrise (Thessaloniki): N/A"
    try:
        thessaloniki_lat = '40.6401'  # Latitude for Thessaloniki
        thessaloniki_lon = '22.9444'  # Longitude for Thessaloniki

        observer = ephem.Observer()
        observer.lat = thessaloniki_lat
        observer.lon = thessaloniki_lon
        observer.date = obs_date # Current UTC for calculation
        # observer.horizon = '0' # Using default horizon for ephem

        next_rise_utc_event = observer.next_rising(ephem.Moon())

        moonrise_utc_dt = next_rise_utc_event.datetime() # naive UTC datetime
        moonrise_local_dt = moonrise_utc_dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Athens"))

        current_local_observer_dt = datetime.now(ZoneInfo("Europe/Athens"))

        # Display date if moonrise is not on the current local day
        if moonrise_local_dt.date() == current_local_observer_dt.date():
            moonrise_time_str = moonrise_local_dt.strftime("%H:%M %Z")
        else:
            moonrise_time_str = moonrise_local_dt.strftime("%b %d, %H:%M %Z") # e.g., May 14, 03:30 EEST

        moonrise_info_str = f"Moonrise (Thessaloniki): {moonrise_time_str}"

    except ephem.NeverUpError:
        moonrise_info_str = "Moonrise (Thessaloniki): Does not rise"
    except ephem.AlwaysUpError:
        moonrise_info_str = "Moonrise (Thessaloniki): Always up"
    except Exception as e_rise:
        # Log the specific error for debugging
        print(f"Error calculating moonrise for Thessaloniki: {e_rise}")
        # moonrise_info_str remains "N/A" as set by default

    return f"{phase_display_str} | {moonrise_info_str}"

def create_dashboard(df):
    if df.empty:
        return html.Div("No data available", style={"textAlign": "center", "fontFamily": "Roboto, sans-serif"})

    # Define the parameters to display in the summary table.
    dashboard_parameters = [
        "Temperature (BME280) (°C)",
        "Temperature (MCP9808) (°C)",
        "Humidity (BME280) (%)",
        "Pressure (BME280) (hPa)",
        "PM1.0 (PMSA003I) (µg/m³)",
        "PM2.5 (PMSA003I) (µg/m³)",
        "PM10.0 (PMSA003I) (µg/m³)",
        "Wind Speed (Anemometer) (m/s)",
        "UV Index (GY-8511)"
    ]

    # Define which parameters get both min and max versus max only.
    extra_stats = {
        "Temperature (BME280) (°C)": "minmax",
        "Temperature (MCP9808) (°C)": "minmax",
        "Humidity (BME280) (%)": "minmax",
        "Pressure (BME280) (hPa)": "minmax",
        "PM1.0 (PMSA003I) (µg/m³)": "minmax",
        "PM2.5 (PMSA003I) (µg/m³)": "minmax",
        "PM10.0 (PMSA003I) (µg/m³)": "minmax",
        "Wind Speed (Anemometer) (m/s)": "max",
        "UV Index (GY-8511)": "max"
    }

    # Define thresholds for PM parameters.
    pm_thresholds = {
        "PM1.0 (PMSA003I) (µg/m³)": 20,
        "PM2.5 (PMSA003I) (µg/m³)": 25,
        "PM10.0 (PMSA003I) (µg/m³)": 50
    }

    rows = []
    for param in dashboard_parameters:
        if param in df.columns:
            df_param = df[df[param].notnull()]
            # Determine the display parameter name.
            if param.startswith("UV Index"):
                display_param = "UV Index"
            elif param.startswith("Wind Speed"):
                display_param = "Wind Speed (km/h)"
            else:
                # Keep text before the first parenthesis and add the unit from the last parentheses.
                unit_start = param.rfind("(")
                if unit_start != -1:
                    unit_str = param[unit_start:].strip()  # e.g., "(°C)" or "(µg/m³)"
                    display_param = param.split(" (")[0] + " " + unit_str
                else:
                    display_param = param

            if df_param.empty:
                latest_value = "N/A"
                stats_str = ""
            else:
                # Latest measurement (for simplicity, using the row with the max timestamp)
                latest_row = df_param.loc[df_param["timestamp"].idxmax()]
                latest_value = latest_row[param]
                # Special handling for Wind Speed: convert m/s to km/h.
                if param == "Wind Speed (Anemometer) (m/s)":
                    latest_value = round(latest_value * 3.6, 1)

                if extra_stats.get(param) == "minmax":
                    # Calculate min and max values and their timestamps.
                    min_val = df_param[param].min()
                    max_val = df_param[param].max()
                    min_row = df_param[df_param[param] == min_val].iloc[0]
                    max_row = df_param[df_param[param] == max_val].iloc[0]
                    # For wind speed, convert values from m/s to km/h.
                    if param == "Wind Speed (Anemometer) (m/s)":
                        min_val = round(min_val * 3.6, 1)
                        max_val = round(max_val * 3.6, 1)
                    # Format timestamps to show only hour and minute.
                    min_ts = min_row["timestamp"].astimezone(ZoneInfo("Europe/Athens")).strftime("%H:%M")
                    max_ts = max_row["timestamp"].astimezone(ZoneInfo("Europe/Athens")).strftime("%H:%M")
                    stats_str = f"Min: {min_val} ({min_ts}), Max: {max_val} ({max_ts})"
                elif extra_stats.get(param) == "max":
                    max_val = df_param[param].max()
                    max_row = df_param[df_param[param] == max_val].iloc[0]
                    if param == "Wind Speed (Anemometer) (m/s)":
                        max_val = round(max_val * 3.6, 1)
                    max_ts = max_row["timestamp"].astimezone(ZoneInfo("Europe/Athens")).strftime("%H:%M")
                    stats_str = f"Max: {max_val} ({max_ts})"
                else:
                    stats_str = ""

                # For PM parameters, if the latest and maximum values exceed thresholds, apply bold red styling.
                value_style = {}
                if param in pm_thresholds and not df_param.empty:
                    threshold = pm_thresholds[param]
                    if latest_value > threshold:
                        if extra_stats.get(param) == "minmax":
                            max_val = df_param[param].max()
                        else:
                            max_val = None
                        if (max_val is not None and max_val > threshold) or (max_val is None):
                            value_style = {"color": "red", "fontWeight": "bold"}

            rows.append(
                html.Tr([
                    html.Td(display_param, style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"}),
                    html.Td(latest_value, style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px", **value_style}),
                    html.Td(stats_str, style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px", **value_style})
                ])
            )

    # --- NEW: Add Daily Rainfall and Rain Intensity rows ---
    # Daily Rainfall: if the column exists, compute (max - min) over the day.
    if "Rain Accumulation (SEN0575) (mm)" in df.columns:
        # We assume the CSV data are already filtered to the last 24 hours.
        daily_rainfall = df["Rain Accumulation (SEN0575) (mm)"].max() - df["Rain Accumulation (SEN0575) (mm)"].min()
        daily_rainfall = round(daily_rainfall, 1)
    else:
        daily_rainfall = "N/A"

    # Rain Intensity: if it's currently raining (check last row of "Rain Event (LM393)"),
    # compute difference over the last 60 minutes.
    if "Rain Accumulation (SEN0575) (mm)" in df.columns and "Rain Event (LM393)" in df.columns:
        # Check if the last rain event indicates "Rain"
        if not df[df["Rain Event (LM393)"].notnull()].empty and df[df["Rain Event (LM393)"].notnull()].iloc[-1]["Rain Event (LM393)"] == "Rain":
            now_greece = datetime.now(ZoneInfo("Europe/Athens"))
            df_last60 = df[df["timestamp"] >= now_greece.astimezone(ZoneInfo("UTC")) - timedelta(minutes=60)]
            if not df_last60.empty:
                intensity = df_last60["Rain Accumulation (SEN0575) (mm)"].max() - df_last60["Rain Accumulation (SEN0575) (mm)"].min()
                rain_intensity = round(intensity, 1)
            else:
                rain_intensity = "N/A"
        else:
            rain_intensity = 0
    else:
        rain_intensity = "N/A"

    # Append new rows for daily rainfall and rain intensity.
    rows.append(
        html.Tr([
            html.Td("Daily Rainfall (mm)", style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"}),
            html.Td(daily_rainfall, style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"}),
            html.Td("", style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"})
        ])
    )
    rows.append(
        html.Tr([
            html.Td("Rain Intensity (mm/h)", style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"}),
            html.Td(rain_intensity, style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"}),
            html.Td("", style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"})
        ])
    )
    # --- End New Rows ---

    header_table = html.Thead(
        html.Tr([
            html.Th("Parameter", style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"}),
            html.Th("Latest Value", style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"}),
            html.Th("Min/Max (with Timestamps)", style={"padding": "8px", "border": "1px solid #ccc", "fontSize": "14px"})
        ])
    )

    table = html.Table(
        [header_table, html.Tbody(rows)],
        style={"width": "100%", "margin": "0 auto", "borderCollapse": "collapse"}
    )

    # Mobile-friendly layout: adjust container width for a typical smartphone.
    return html.Div(
        [
            html.H2("Latest Measurements", style={"fontFamily": "Roboto, sans-serif", "fontWeight": "bold", "fontSize": "20px"}),
            table
        ],
        style={
            "padding": "10px",
            "textAlign": "center",
            "backgroundColor": "rgba(255,255,255,0.9)",
            "border": "1px solid #ccc",
            "borderRadius": "10px",
            "width": "100%",
            "maxWidth": "400px",
            "margin": "20px auto",
            "fontFamily": "Roboto, sans-serif"
        }
    )

def create_thermometer_dashboard(df):
    # Use the BME280 temperature sensor column
    sensor_col = "Temperature (BME280) (°C)"
    if sensor_col not in df.columns or df[sensor_col].isnull().all():
        return go.Figure()  # Return an empty figure if no data

    # Get current time in Greece and calculate midnight (local)
    now_greece = datetime.now(ZoneInfo("Europe/Athens"))
    midnight = now_greece.replace(hour=0, minute=0, second=0, microsecond=0)
    # Convert midnight to UTC for filtering (timestamps are in UTC)
    midnight_utc = midnight.astimezone(ZoneInfo("UTC"))

    # Filter data for today (from midnight onward)
    df_today = df[df["timestamp"] >= midnight_utc]
    if df_today.empty:
        return go.Figure()

    # Compute original values
    orig_latest = df_today.loc[df_today["timestamp"].idxmax()][sensor_col]
    orig_min = df_today[sensor_col].min()
    orig_max = df_today[sensor_col].max()

    # Get the latest, minimum, and maximum temperatures for today
    latest_value = orig_latest - 0
    min_value = orig_min - 0
    max_value = orig_max - 0

    # Create a gauge (thermometer) using a Plotly Indicator.
    # Set the gauge range a bit beyond the min and max for aesthetics.
    gauge_range = [min_value - 1, max_value + 1]
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = latest_value,
        title = {"text": "Temperature (°C)"},
        gauge = {
            "axis": {"range": gauge_range, "dtick": 1.0},
            "bar": {"color": "red"},
            "steps": [
                {"range": [min_value-0.125, min_value+0.125], "color": "lightblue"},
                {"range": [max_value-0.125, max_value+0.125], "color": "orange"}
            ],
            "threshold": {
                "line": {"color": "black", "width": 4},
                "thickness": 0.80,
                "value": latest_value
            }
        }
    ))

    # Add an annotation below the gauge for min and max (only hour and minute are relevant here,
    # but since these are daily aggregates, we display the values without timestamps).
    fig.add_annotation(
        x=0.5, y=-0.15,
        xref="paper", yref="paper",
        text=f"Min: {min_value:.1f} °C, Max: {max_value:.1f} °C",
        showarrow=False,
        font=dict(size=14)
    )

    # Optionally, adjust layout for a mobile-friendly size.
    fig.update_layout(width=400, height=400, margin=dict(t=50, b=100))
    return fig

# Updated header with logo
header = html.Div(
    [
        # Text part of the header
        html.Div(
            [
                "Experimental Environmental",
                html.Br(),
                "Monitoring Station"
            ],
            className="title-foreground",
            style={
                "textAlign": "left", # Align text to the left
                "lineHeight": "1.2",
                "fontSize": "24px",
                "fontWeight": "bold",
                "color": "#333",
                "flex": "1" # Allow text to take available space
            }
        ),
        # Logo part of the header
        html.Img(
            # Use app.get_asset_url for robust path handling
            src=app.get_asset_url('icons/SKG_weather_station_logo-removebg-preview.png'),
            style={
                "height": "50px", # Adjust height as needed
                "width": "auto"
            }
        )
    ],
    style={
        "display": "flex", # Use flexbox for layout
        "justifyContent": "space-between", # Space items out
        "alignItems": "center", # Vertically align items
        "padding": "20px",
        "border": "1px solid #ccc",
        "borderRadius": "10px",
        "margin": "0 auto",
        "maxWidth": "500px",
        "backgroundColor": "rgba(255, 255, 255, 0.8)",
        "marginBottom": "30px"
    }
)


# Footer with a line break before the rights statement
footer = html.Footer(
    children=[
        "Weather data & visualizations © ",
        f"{date.today().year} ",
        html.A(
            "Dimitris Mitropoulos",
            href="https://www.linkedin.com/in/wx42",
            target="_blank",
            style={"color": "#0077B5"}
        ),
        html.Br(),  # This creates the line break
        "All rights reserved."
    ],
    style={
        "position": "fixed",
        "bottom": "10px",
        "right": "10px",
        "fontSize": "12px",
        "color": "#666",
        "fontFamily": "Roboto, sans-serif",
        "textAlign": "right"  # Ensures both lines are right-aligned
    }
)


# <<< MODIFIED: Redesigned tab styling to allow text wrapping within each tab.
tab_style = {
    'padding': '8px 12px',
    'fontSize': '14px',
    'fontFamily': 'Roboto, sans-serif',
    'border': '1px solid #ccc',
    'borderBottom': 'none',
    'borderRadius': '5px 5px 0 0',
    'backgroundColor': '#f8f8f8',
    'margin': '2px 2px 0 2px',
    'cursor': 'pointer',
    'minHeight': '40px',          # Give space for two lines of text
    'display': 'flex',            # Use flexbox for vertical alignment
    'alignItems': 'center',       # Center text vertically
    'justifyContent': 'center',   # Center text horizontally
    'textAlign': 'center',        # Ensure text is centered if it wraps
    'flex': '1 1 0',              # Allow tabs to grow and shrink as needed
    'minWidth': '120px'           # Set a minimum width for shorter tabs
}

tab_selected_style = {
    'padding': '8px 12px',
    'fontSize': '14px',
    'fontFamily': 'Roboto, sans-serif',
    'border': '1px solid #ccc',
    'borderBottom': '1px solid white',
    'borderRadius': '5px 5px 0 0',
    'backgroundColor': 'white',
    'fontWeight': 'bold',
    'margin': '2px 2px 0 2px',
    'cursor': 'pointer',
    'minHeight': '40px',
    'display': 'flex',
    'alignItems': 'center',
    'justifyContent': 'center',
    'textAlign': 'center',
    'flex': '1 1 0',
    'minWidth': '120px'
}


# Station status indicator placeholder (we'll update its content via a callback)
station_status = html.Div(id="station-status", style={"textAlign": "center", "marginBottom": "20px"})

# --- MODIFIED LAYOUT ---
# Updated layout with the new "Wind Time Series" tab included.
app.layout = html.Div(
    [
        header,
        station_status,  # Displays last read timestamp and online/offline status
        dcc.Interval(id="interval", interval=5000),
        dcc.Tabs(
            id="tabs",
            value="Dashboard",
            children=[
                dcc.Tab(label="Dashboard", value="Dashboard", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Weather Summary", value="Weather Summary", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Temperature", value="Temperature", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Relative Humidity", value="Humidity", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Atmospheric Pressure", value="Atmospheric Pressure", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Ambient Visible Light", value="Light Intensity", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="UV Index", value="UV Index", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Wind Rose", value="Wind Rose", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Wind Time Series", value="Wind Time Series", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Air Quality Monitoring", value="Air Quality Monitoring", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Rain Accumulation", value="Rain Accumulation", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Cloud Camera", value="Cloud Camera", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Satellite Greece", value="Satellite Greece", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Temperature Anomaly", value="Temperature Anomaly", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Upper Air Sounding", value="Upper Air Sounding", style=tab_style, selected_style=tab_selected_style)
            ],
            persistence=True,
            persistence_type="session",
            # <<< MODIFIED: This style makes the container of the tabs a flexible, wrapping row.
            style={'display': 'flex', 'flexWrap': 'wrap'},
            content_style={'border': '1px solid #ccc', 'borderTop': 'none', 'padding': '10px'}
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

def create_wind_rose_range(df, time_delta, title_text):
    # Get current UTC time
    now_utc = datetime.now(ZoneInfo("UTC"))
    # Filter the DataFrame based on the time_delta
    filtered_df = df[df["timestamp"] >= now_utc - time_delta]
    # Create the wind rose from the filtered data
    fig = create_wind_rose(filtered_df)
    # Update the title of the wind rose
    fig.update_layout(title=dict(text=title_text, font=title_font))
    return fig

def create_reflected_wind_direction_figure(mean_wind_speed_kmh, mean_direction):
    """
    Invert wind direction across the west-east axis by computing:
        reflected_angle = (180 - mean_direction) mod 360
    Then draw a circle with N/E/S/W, and an inward arrow from the perimeter
    to the center. So if the sensor says 271°, we show 269°, etc.

    0° => top (N), 90° => right (E), 180° => bottom (S), 270° => left (W).
    """

    # 1) Reflect the angle
    #    e.g. 0 -> 180, 45 -> 135, 90 -> 90, 271 -> 269
    reflected_angle = (180 - mean_direction) % 360

    # 2) We'll define an x–y data space of [0..1] × [0..1].
    fig = go.Figure()
    r = 0.4  # circle radius

    # Draw the circle
    fig.add_shape(
        type="circle",
        xref="x", yref="y",
        x0=0.5 - r, x1=0.5 + r,
        y0=0.5 - r, y1=0.5 + r,
        line=dict(color="black", width=2),
        fillcolor="white"
    )

    # Cardinal directions: N=top, E=right, S=bottom, W=left
    offset = 0.06
    # N at top => (0.5, 0.5-r-offset)
    fig.add_annotation(x=0.5, y=0.5 + r + offset, text="N", showarrow=False, font=dict(size=16), xref="x", yref="y")
    # E at right => (0.5+r+offset, 0.5)
    fig.add_annotation(x=0.5 + r + offset, y=0.5, text="E", showarrow=False, font=dict(size=16), xref="x", yref="y")
    # S at bottom => (0.5, 0.5+r+offset)
    fig.add_annotation(x=0.5, y=0.5 - r - offset, text="S", showarrow=False, font=dict(size=16), xref="x", yref="y")
    # W at left => (0.5-r-offset, 0.5)
    fig.add_annotation(x=0.5 - r - offset, y=0.5, text="W", showarrow=False, font=dict(size=16), xref="x", yref="y")

    # 3) Compute arrow coordinates from perimeter to center
    #    0° => top, 90° => right, 180° => bottom, 270° => left
    #    x = 0.5 + r*sin(angle), y = 0.5 - r*cos(angle)
    angle_rad = math.radians(reflected_angle)
    x_perim = 0.5 + r * math.sin(angle_rad)
    y_perim = 0.5 - r * math.cos(angle_rad)

    # Arrow from perimeter to center
    fig.add_annotation(
        x=0.5, y=0.5,          # arrow head at center
        ax=x_perim, ay=y_perim,  # arrow tail on perimeter
        xref="x", yref="y",
        axref="x", ayref="y",
        arrowhead=5,
        arrowwidth=5,
        arrowcolor="red",
        showarrow=True
    )

    # 4) Mean wind speed text in the center
    fig.add_annotation(
        x=0.5, y=0.5,
        xref="x", yref="y",
        text=f"{mean_wind_speed_kmh} km/h",
        showarrow=False,
        font=dict(size=42, color="black")
    )

    # 5) Hide axes, fix range
    fig.update_xaxes(range=[0,1], visible=False)
    fig.update_yaxes(range=[0,1], visible=False)

    fig.update_layout(width=400, height=400,
        margin=dict(t=50, b=50, l=50, r=50),
        
        title=f"Wind: {mean_wind_speed_kmh} km/h, {int(mean_direction)}°"
    )
    return fig


@app.callback(
    Output("tabs-content", "children"),
    [Input("tabs", "value"),
     Input("interval", "n_intervals")]
)
def render_content(tab, n_intervals):
    df = load_data()

    # 1. Dashboard tab: Thermometer + Wind Arrow
    if tab == "Dashboard":
        # 1) Thermometer
        thermo_fig = create_thermometer_dashboard(df)

        # 2) Filter data for last 10 minutes
        now_utc = datetime.now(ZoneInfo("UTC"))
        df_last10 = df[df["timestamp"] >= now_utc - timedelta(minutes=10)]

        # 3) Check columns
        if (
            df_last10.empty or
            "Wind Speed (Anemometer) (m/s)" not in df_last10.columns or
            "Wind Direction (Wind Vane) (deg)" not in df_last10.columns
        ):
            wind_fig = go.Figure()
            wind_fig.add_annotation(text="No wind data", showarrow=False, font=dict(size=16))
        else:
            mean_wind_speed_mps = df_last10["Wind Speed (Anemometer) (m/s)"].mean()
            if np.isnan(mean_wind_speed_mps):
                wind_fig = go.Figure()
                wind_fig.add_annotation(text="No wind data", showarrow=False, font=dict(size=16))
            else:
                mean_wind_speed_kmh = round(mean_wind_speed_mps * 3.6, 1)
                mean_direction = df_last10["Wind Direction (Wind Vane) (deg)"].tail(10).mean()
                if np.isnan(mean_direction):
                    mean_direction = 0

                wind_fig = create_reflected_wind_direction_figure(mean_wind_speed_kmh, mean_direction)

        # 5) Show them side by side
        content = html.Div(
            [
                html.Div(dcc.Graph(figure=thermo_fig, className="dash-graph"), style={"flex": "1", "padding": "10px"}),
                html.Div(dcc.Graph(figure=wind_fig, className="dash-graph"), style={"flex": "1", "padding": "10px"})
            ],
            style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"}
        )


    elif tab == "Weather Summary":
        content = create_dashboard(df)

    elif tab == "Temperature":
        content = dcc.Graph(figure=create_temperature_figure(df), className="dash-graph")
    elif tab == "Humidity":
        content = dcc.Graph(figure=create_line_figure(df, ["Humidity (BME280) (%)"], "Relative Humidity", "%"), className="dash-graph")
    elif tab == "Atmospheric Pressure":
        content = dcc.Graph(figure=create_line_figure(df, ["Pressure (BME280) (hPa)"], "Atmospheric Pressure", "hPa"), className="dash-graph")
    elif tab == "Light Intensity":
        content = dcc.Graph(figure=create_line_figure(df, ["Light Intensity (BH1750) (lux)"], "Ambient Visible Light", "Illuminance (lux)"), className="dash-graph")
    elif tab == "UV Index":
        content = dcc.Graph(figure=create_line_figure(df, ["UV Index (GY-8511)"], "UV Index", ""), className="dash-graph")
    elif tab == "Wind Rose":
        wind_rose_24 = dcc.Graph(
            figure=create_wind_rose_range(df, timedelta(hours=24), "Last 24 hours"),
            className="dash-graph"
        )
        wind_rose_1 = dcc.Graph(
            figure=create_wind_rose_range(df, timedelta(hours=1), "Last 1 hour"),
            className="dash-graph"
        )
        wind_rose_10 = dcc.Graph(
            figure=create_wind_rose_range(df, timedelta(minutes=10), "Last 10 minutes"),
            className="dash-graph"
        )
        content = html.Div(
            [wind_rose_24, wind_rose_1, wind_rose_10],
            style={"display": "flex", "justifyContent": "space-around", "flexWrap": "wrap"}
        )
    elif tab == "Wind Time Series":
        content = dcc.Graph(
            figure=create_wind_timeseries_figure(df),
            className="dash-graph"
        )
    elif tab == "Air Quality Monitoring":
        content = dcc.Graph(figure=create_air_quality_figure(df), className="dash-graph")
    elif tab == "Rain Accumulation":
        content = dcc.Graph(
        figure=create_rain_line_figure(
            df,
            "Rain Accumulation (SEN0575) (mm)",
            "Rain Accumulation (last 24 hours)",
            "Precipitation Height (mm)"
        ),
        className="dash-graph"
    )

    elif tab == "Cloud Camera":
        img_src = get_latest_cloud_camera_image()
        if img_src is None:
            content = html.Div("No image found in whole_sky_camera folder.", style={"textAlign": "center", "padding": "20px"})
        else:
            content = html.Div(
                html.Img(src=img_src, style={"maxWidth": "100%", "height": "auto"}),
                style={"textAlign": "center", "padding": "20px"}
            )
    elif tab == "Satellite Greece":
        sat_img = get_satellite_image()
        if sat_img is None:
            content = html.Div("No satellite image found.", style={"textAlign": "center", "padding": "20px"})
        else:
            content = html.Div(
                html.Img(src=sat_img, style={"maxWidth": "100%", "height": "auto"}),
                style={"textAlign": "center", "padding": "20px"}
            )
    elif tab == "Temperature Anomaly":
        anomaly_map_src = get_latest_anomaly_map()
        if anomaly_map_src is None:
            content = html.Div("No temperature anomaly map found.", style={"textAlign": "center", "padding": "20px"})
        else:
            content = html.Div(
                html.Img(src=anomaly_map_src, style={"maxWidth": "100%", "height": "auto"}),
                style={"textAlign": "center", "padding": "20px"}
            )
    elif tab == "Upper Air Sounding":
        sounding_img_src = get_latest_upper_air_sounding_image()
        if sounding_img_src is None:
            content = html.Div("No upper air sounding image found.", style={"textAlign": "center", "padding": "20px"})
        else:
            content = html.Div(
                html.Img(src=sounding_img_src, style={"maxWidth": "100%", "height": "auto"}),
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

@app.callback(Output("station-status", "children"), [Input("interval", "n_intervals")])
def update_station_status(n_intervals):
    df = load_data()
    if df.empty or df["timestamp"].max() is None:
        return html.Div("No data available", style={"color": "gray"})
    last_ts = df["timestamp"].max()
    last_ts_greece = last_ts.astimezone(ZoneInfo("Europe/Athens"))
    now_greece = datetime.now(ZoneInfo("Europe/Athens"))
    diff_minutes = (now_greece - last_ts_greece).total_seconds() / 60.0
    status_text = "Station is OFFLINE" if diff_minutes > 30 else "Station is Online"
    indicator_style = {"display": "inline-block", "width": "15px", "height": "15px", "borderRadius": "50%", "marginRight": "10px"}
    if diff_minutes > 30:
        indicator_style.update({"backgroundColor": "red", "animation": "blinker 1s linear infinite"})
    else:
        indicator_style.update({"backgroundColor": "green"})
    indicator_dot = html.Span("", style=indicator_style)
    ts_str = last_ts_greece.strftime("%Y-%m-%d %H:%M:%S")

    lightning_info_str = "No lightning data available"
    if "Lightning Detection (AS3935)" in df.columns:
        df_lightning = df[df["Lightning Detection (AS3935)"].notnull()]
        if not df_lightning.empty:
            latest_lightning_row = df_lightning.loc[df_lightning["timestamp"].idxmax()]
            lightning_time = latest_lightning_row["timestamp"].astimezone(ZoneInfo("Europe/Athens")).strftime("%Y-%m-%d %H:%M")
            lightning_distance = latest_lightning_row["Lightning Distance (AS3935) (km)"]
            lightning_info_str = f"Last Lightning: {lightning_time} (Distance: {lightning_distance} km)"
        else: lightning_info_str = "No lightning detected"
    lightning_info = html.Div(lightning_info_str, style={"marginTop": "10px", "fontSize": "14px"})

    rain_info_str = "No rain data available"
    if "Rain Event (LM393)" in df.columns:
        df_rain = df[df["Rain Event (LM393)"].notnull()]
        if not df_rain.empty:
            latest_rain_value = df_rain.iloc[-1]["Rain Event (LM393)"]
            if latest_rain_value == "Rain":
                rain_indicator_dot = html.Span("", style={"display": "inline-block", "width": "15px", "height": "15px", "borderRadius": "50%", "backgroundColor": "blue", "marginLeft": "10px", "animation": "blinker 1s linear infinite"})
                rain_info = html.Div(["Rain is happening now", rain_indicator_dot], style={"marginTop": "10px", "fontSize": "14px"})
            else: # Handles "No Rain" and other potential values
                rain_info = html.Div(f"{'No rain at the moment' if latest_rain_value == 'No Rain' else 'Rain status: ' + latest_rain_value}", style={"marginTop": "10px", "fontSize": "14px"})
        else: rain_info = html.Div("No recent rain data", style={"marginTop": "10px", "fontSize": "14px"})
    else: rain_info = html.Div(rain_info_str, style={"marginTop": "10px", "fontSize": "14px"})

    # --- MOON PHASE AND RISE INFO ---
    try:
        moon_details_str = get_moon_phase_and_rise_info() # Modified function
        moon_info = html.Div(
            moon_details_str, # Directly use the combined string
            style={"marginTop": "10px", "fontSize": "14px", "fontFamily": "Roboto, sans-serif"}
        )
    except Exception as e:
        print(f"Error getting moon phase and rise info: {e}")
        moon_info = html.Div(
            "Moon Phase & Rise: N/A",
            style={"marginTop": "10px", "fontSize": "14px", "fontFamily": "Roboto, sans-serif"}
        )
    # --- END MOON PHASE AND RISE INFO ---

    return html.Div([
        indicator_dot, html.Span(f"{status_text} (Last data at: {ts_str})"),
        lightning_info, rain_info, moon_info],
        style={"fontSize": "16px", "fontFamily": "Roboto, sans-serif", "padding": "20px", "border": "1px solid #ccc", "borderRadius": "10px", "margin": "0 auto", "maxWidth": "500px", "backgroundColor": "rgba(255, 255, 255, 0.8)", "marginBottom": "30px", "textAlign": "center"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
