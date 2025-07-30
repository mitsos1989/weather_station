# -*- coding: utf-8 -*-
"""
T850 Anomaly Script

This script downloads ERA5 reanalysis data to calculate and plot the temperature
anomaly at 850 hPa over Europe.

It performs the following steps:
1. Downloads the monthly climatology (1975-2005) for temperature at 850 hPa.
2. Downloads the temperature at 850 hPa for the most recent available day at 12:00 UTC.
3. Calculates the anomaly by subtracting the corresponding month's climatology
   from the recent day's data.
4. Plots the resulting anomaly field on a map using Matplotlib and Cartopy.

Requirements:
- cdsapi: For downloading data from the Copernicus Climate Data Store.
  You need a CDS account and an API key set up in your ~/.cdsapirc file.
  Instructions: https://cds.climate.copernicus.eu/api-how-to
- xarray: For data manipulation.
- numpy: For numerical operations.
- matplotlib: For plotting.
- cartopy: For map projections and geographical features.

Installation:
pip install cdsapi xarray numpy matplotlib cartopy
"""
import cdsapi
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime, timedelta, timezone
import os

# --- Configuration ---
# Bounding box for Europe: [North, West, South, East]
# Extended the area south by 10 deg, west by 5 deg, and east by 7 deg.
EUROPE_AREA = [75, -35, 20, 57] 
CLIMATOLOGY_YEARS = [str(y) for y in range(1975, 2006)]
CLIMATOLOGY_FILE = 't850_climatology_1975-2005.nc'
LATEST_DAY_FILE_TEMPLATE = 't850_latest_{date_str}.nc'

def download_climatology():
    """
    Downloads the monthly mean temperature at 850hPa for the climatology
    period (1975-2005) if the data file doesn't already exist.
    """
    if os.path.exists(CLIMATOLOGY_FILE):
        print(f"Climatology file '{CLIMATOLOGY_FILE}' already exists. Skipping download.")
        return

    print("Downloading monthly climatology data (1975-2005)...")
    c = cdsapi.Client()
    c.retrieve(
        'reanalysis-era5-pressure-levels-monthly-means',
        {
            'product_type': 'monthly_averaged_reanalysis',
            'variable': 'temperature',
            'pressure_level': '850',
            'year': CLIMATOLOGY_YEARS,
            'month': [f'{m:02d}' for m in range(1, 13)],
            'time': '00:00',
            'area': EUROPE_AREA,
            'format': 'netcdf',
        },
        CLIMATOLOGY_FILE)
    print("Climatology download complete.")

def download_latest_day():
    """
    Downloads the T850 data for the most recent available day.
    ERA5 data has a typical delay of about 5 days. This function will try
    to download data starting from 5 days ago and moving backwards until
    it succeeds.
    """
    c = cdsapi.Client()
    for i in range(5, 10): # Try from 5 days ago up to 9 days ago
        target_date = datetime.now(timezone.utc) - timedelta(days=i)
        date_str = target_date.strftime('%Y-%m-%d')
        latest_day_file = LATEST_DAY_FILE_TEMPLATE.format(date_str=date_str)

        if os.path.exists(latest_day_file):
            print(f"Latest day file '{latest_day_file}' already exists. Skipping download.")
            return latest_day_file, target_date

        print(f"Attempting to download data for {date_str} at 12:00 UTC...")
        try:
            c.retrieve(
                'reanalysis-era5-pressure-levels',
                {
                    'product_type': 'reanalysis',
                    'variable': 'temperature',
                    'pressure_level': '850',
                    'year': target_date.strftime('%Y'),
                    'month': target_date.strftime('%m'),
                    'day': target_date.strftime('%d'),
                    'time': '12:00',
                    'area': EUROPE_AREA,
                    'format': 'netcdf',
                },
                latest_day_file)
            print(f"Successfully downloaded data for {date_str}.")
            return latest_day_file, target_date
        except Exception as e:
            print(f"Could not download data for {date_str}. Error: {e}")
            print("Trying the previous day...")
            if os.path.exists(latest_day_file):
                 os.remove(latest_day_file) # Clean up failed download

    print("Failed to download recent data after several attempts.")
    return None, None

def calculate_and_plot_anomaly(latest_day_file, latest_date):
    """
    Calculates the temperature anomaly and plots it on a map.
    """
    print("Loading datasets with xarray...")
    # Load climatology and calculate the long-term mean for each month
    ds_clim = xr.open_dataset(CLIMATOLOGY_FILE)
    monthly_clim = ds_clim.groupby('valid_time.month').mean('valid_time')

    # Load the latest day's data
    ds_latest = xr.open_dataset(latest_day_file)
    
    # --- Process latest day data to be 2D ---
    t850_latest = ds_latest.t.squeeze(drop=True)
    if t850_latest.ndim != 2:
        raise ValueError(
            f"Error: Processed latest-day data is not 2D. Dims: {t850_latest.dims}"
        )

    # --- Process climatology data to be 2D ---
    target_month = latest_date.month
    print(f"Calculating anomaly for month: {target_month}")
    t850_clim_month_raw = monthly_clim.sel(month=target_month).t
    # Squeeze the climatology data as well to ensure it is 2D
    t850_clim_month = t850_clim_month_raw.squeeze(drop=True)
    if t850_clim_month.ndim != 2:
         raise ValueError(
            f"Error: Processed climatology data is not 2D. Dims: {t850_clim_month.dims}"
        )

    # Calculate the anomaly
    anomaly = t850_latest - t850_clim_month

    print("Plotting the anomaly map...")
    # --- Plotting ---
    fig = plt.figure(figsize=(12, 10))
    # Centered the projection over the central Mediterranean.
    projection = ccrs.LambertConformal(central_longitude=15.0, central_latitude=38.0)
    ax = fig.add_subplot(1, 1, 1, projection=projection)

    ax.set_extent([EUROPE_AREA[1], EUROPE_AREA[3], EUROPE_AREA[2], EUROPE_AREA[0]], crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.COASTLINE.with_scale('50m'), edgecolor='black', linewidth=0.5)
    ax.add_feature(cfeature.BORDERS.with_scale('50m'), edgecolor='black', linewidth=0.5)
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='aliceblue')

    # Set fixed contour levels from -12 to 12 with a step of 2.
    levels = np.arange(-12, 13, 2)
    
    # Plot the filled contours
    contour = ax.contourf(
        anomaly['longitude'], anomaly['latitude'], anomaly,
        levels=levels,
        cmap='RdBu_r',
        transform=ccrs.PlateCarree(),
        extend='both' # 'both' extends the colorbar for values outside the levels
    )
    
    # Removed contour lines by commenting out the ax.contour() call.
    # ax.contour(
    #     anomaly['longitude'], anomaly['latitude'], anomaly,
    #     levels=levels,
    #     colors='k',
    #     linewidths=0.3,
    #     transform=ccrs.PlateCarree()
    # )

    # EDIT: Shrunk the colorbar to make it shorter.
    cbar = fig.colorbar(contour, ax=ax, orientation='vertical', pad=0.03, shrink=0.7)
    cbar.set_label('Temperature Anomaly at 850 hPa (K)', fontsize=12)

    # EDIT: Removed gridlines.
    # ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)

    title_date = latest_date.strftime('%Y-%m-%d at 12:00 UTC')
    ax.set_title(f'ERA5 T850hPa Anomaly vs 1975-2005 Climatology\n{title_date}', fontsize=14)

    output_filename = f'/home/dimitris/weather_station/temp_anomaly_map/t850_anomaly_{latest_date.strftime("%Y%m%d")}.png'
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"Map saved as '{output_filename}'")
    plt.show()


if __name__ == '__main__':
    # For a clean run, it's best to delete the old daily file first
    # as its data structure might differ from a fresh download.
    # Also, if the EUROPE_AREA changes, old files must be deleted.
    for f in os.listdir('.'):
        if f.startswith('t850_latest_'):
            print(f"Forcing a fresh download by removing old file: {f}")
            os.remove(f)
    # Also remove old climatology if area changes.
    # A simple check is to see if the climatology file exists and if so,
    # assume the area might have changed and remove it. A more robust check
    # would be to store metadata, but this is sufficient for this script.
    if os.path.exists(CLIMATOLOGY_FILE):
        print(f"Domain area may have changed. Removing old climatology file: {CLIMATOLOGY_FILE}")
        os.remove(CLIMATOLOGY_FILE)


    download_climatology()

    latest_day_file, latest_date = download_latest_day()

    if latest_day_file and latest_date:
        calculate_and_plot_anomaly(latest_day_file, latest_date)
    else:
        print("\nCould not proceed with anomaly calculation due to download failure.")
