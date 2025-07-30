import asyncio
import telegram
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo



# Initialize your bot with your API token
TELEGRAM_BOT_TOKEN = "7490920595:AAENnqGchyNDxMlHeAZIwydUDFH-GCm3an8"
TELEGRAM_CHAT_ID = "851089620"  # Could be a string or integer

bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

CSV_PATH = "weather_station_data.csv"

def load_all_data():
    """Load the entire CSV (no 24-hour filter) and localize timestamps as UTC."""
    try:
        df = pd.read_csv(
            CSV_PATH,
            parse_dates=["timestamp"],
            date_format="%Y-%m-%d %H:%M:%S",
            low_memory=False
        )
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        return df
    except Exception as e:
        print("Error loading data:", e)
        return pd.DataFrame()

def load_data():
    """For event-based checks: load the last 24 hours of data."""
    try:
        df = pd.read_csv(
            CSV_PATH,
            parse_dates=["timestamp"],
            date_format="%Y-%m-%d %H:%M:%S",
            low_memory=False
        )
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        now_utc = datetime.now(ZoneInfo("UTC"))
        threshold = now_utc - timedelta(hours=24)
        df = df[df["timestamp"] >= threshold]
        numeric_cols = [col for col in df.columns if col not in ["timestamp", "Lightning Detection (AS3935)", "Rain Event (LM393)"]]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        return df
    except Exception as e:
        print("Error loading data:", e)
        return pd.DataFrame()

# ------------------------------
# Notification Functions
# ------------------------------

def check_min_temp_notification(today_date):
    """
    If current UTC time is between 07:00 and 07:05 and no minimum notification has been sent today,
    return the minimum temperature notification message (using the MCP9808 sensor).
    """
    now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    if now_utc.hour == 7 and now_utc.minute < 5:
        df = load_all_data()
        midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        df_today = df[df["timestamp"] >= midnight_utc]
        if df_today.empty or "Temperature (MCP9808) (°C)" not in df_today.columns:
            return None
        min_temp = df_today["Temperature (MCP9808) (°C)"].min()
        if np.isnan(min_temp):
            return None
        return f"Daily Minimum (MCP9808): {min_temp:.1f}°C recorded since midnight UTC."
    return None

def check_max_temp_notification(today_date):
    """
    If current UTC time is between 15:00 and 15:05 and no maximum notification has been sent today,
    return the maximum temperature notification message (using the MCP9808 sensor).
    """
    now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    if now_utc.hour == 15 and now_utc.minute < 5:
        df = load_all_data()
        midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        df_today = df[df["timestamp"] >= midnight_utc]
        if df_today.empty or "Temperature (MCP9808) (°C)" not in df_today.columns:
            return None
        max_temp = df_today["Temperature (MCP9808) (°C)"].max()
        if np.isnan(max_temp):
            return None
        return f"Daily Maximum (MCP9808): {max_temp:.1f}°C recorded since midnight UTC."
    return None

def check_rain_notification():
    df = load_data().sort_values("timestamp")
    col = "Rain Event (LM393)"
    if col not in df.columns:
        return None

    # Keep only non-null, non-blank event rows
    events = (
        df[col]
        .dropna()                   # remove NaNs
        .astype(str)                # ensure string type
        .str.strip()                # trim whitespace
        .reset_index(drop=True)
    )
    if len(events) < 2:
        return None

    prev_event, last_event = events.iloc[-2], events.iloc[-1]
    if last_event.lower() == "rain" and prev_event.lower() == "no rain":
        # get timestamp of that last event row
        ts = df[df[col].notna()].iloc[-1]["timestamp"]
        event_time = ts.astimezone(ZoneInfo("Europe/Athens")).strftime("%H:%M")
        return f"Rain detected at {event_time} (rain started)."
    return None

_last_lightning_time = None  # module-level

def check_lightning_notification():
    global _last_lightning_time
    df = load_data().sort_values("timestamp")
    col = "Lightning Distance (AS3935) (km)"
    if col not in df.columns:
        return None

    # Keep only event rows with a valid float distance
    events = df[[ "timestamp", col ]].dropna(subset=[col])
    if events.empty:
        return None

    # The very latest lightning event:
    last_event = events.iloc[-1]
    event_time = last_event["timestamp"].astimezone(ZoneInfo("Europe/Athens"))
    # Only notify if it’s new
    if _last_lightning_time != event_time:
        _last_lightning_time = event_time
        hhmm = event_time.strftime("%H:%M")
        dist = last_event[col]
        return f"Lightning detected at {hhmm} with distance {dist:.1f} km."
    return None

# ------------------------------
# Async function to send a Telegram notification
# ------------------------------
async def send_notification(message):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

# ------------------------------
# Main async loop to continuously check and send notifications
# ------------------------------
async def main_loop():
    # Track the date when the daily min and max notifications were sent.
    sent_min_date = None
    sent_max_date = None

    # You might also want to track previous event messages for rain or lightning to avoid duplicates.
    previous_rain_notification = None
    previous_lightning_notification = None

    while True:
        notifications = []
        
        now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
        today_date = now_utc.date()

        # 1) Daily minimum temperature notification at 07:00 UTC
        min_msg = check_min_temp_notification(today_date)
        if min_msg and (sent_min_date != today_date):
            notifications.append(min_msg)
            sent_min_date = today_date  # mark today's min as sent

        # 2) Daily maximum temperature notification at 15:00 UTC
        max_msg = check_max_temp_notification(today_date)
        if max_msg and (sent_max_date != today_date):
            notifications.append(max_msg)
            sent_max_date = today_date  # mark today's max as sent

        # 3) Event-based: Rain notification when it changes from "No Rain" to "Rain"
        rain_msg = check_rain_notification()
        if rain_msg and rain_msg != previous_rain_notification:
            notifications.append(rain_msg)
            previous_rain_notification = rain_msg

        # 4) Event-based: Lightning notification with distance
        lightning_msg = check_lightning_notification()
        if lightning_msg and lightning_msg != previous_lightning_notification:
            notifications.append(lightning_msg)
            previous_lightning_notification = lightning_msg

        # Send each notification asynchronously.
        for msg in notifications:
            await send_notification(msg)
            print("Notification sent:", msg)

        # Sleep for 19 seconds before checking again.
        await asyncio.sleep(19)

if __name__ == "__main__":
    asyncio.run(main_loop())
