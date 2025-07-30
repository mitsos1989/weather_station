import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import os

import metpy.calc as mpcalc
from metpy.cbook import get_test_data
from metpy.plots import SkewT
from metpy.units import units
from metpy.interpolate import interpolate_1d
from siphon.simplewebservice.wyoming import WyomingUpperAir


def plot_skewt_for_station(station_id, station_name_long, save_dir):
    """
    Fetches the latest upper-air data for a given station ID, prioritizing 06Z
    and falling back to 00Z. It then calculates thermodynamic properties
    and instability indices, and plots a Skew-T diagram with an information box.

    Args:
        station_id (str): The WMO station identifier (e.g., '16622' for LGTS).
        station_name_long (str): The full name for the plot title.
        save_dir (str): The directory where the plot will be saved.
    """
    try:
        # ### MODIFICATION START ###
        # --- 1. & 2. Set Time and Request Data (with fallback logic) ---
        now_utc = datetime.now(timezone.utc)
        # Define the hours to try in order of preference
        hours_to_try = [6, 0] 
        df = None # Initialize dataframe to None
        
        for hour in hours_to_try:
            try:
                # Set the target datetime for the current attempt
                dt = now_utc.replace(hour=hour, minute=0, second=0, microsecond=0)
                print(f"Attempting to fetch data for station {station_id} for {dt:%Y-%m-%d %H:%M}Z...")

                # Request data for the specified time
                df = WyomingUpperAir().request_data(time=dt, site_id=station_id)
                
                # If the request succeeds, we have our data.
                print(f"Data fetched successfully for {dt:%Y-%m-%d %H:%M}Z.")
                break # Exit the loop since we found data
                
            except Exception:
                # If it fails, print a message. The loop will try the next hour.
                print(f"-> No data available for {hour:02d}Z. Trying next available time.")
        
        # If the loop finished and df is still None, no data was found for any time.
        if df is None:
            print("Could not retrieve data for 06Z or 00Z. No plot will be generated.")
            return # Exit the function cleanly
        # ### MODIFICATION END ###

        # --- 3. Prepare Data for MetPy ---
        # Extract the necessary columns and assign units.
        p = df['pressure'].values * units.hPa
        T = df['temperature'].values * units.degC
        Td = df['dewpoint'].values * units.degC
        u = df['u_wind'].values * units.knots
        v = df['v_wind'].values * units.knots
        height = df['height'].values * units.meter
        
        # Drop rows with missing pressure, temperature, or dewpoint data
        valid_mask = ~np.isnan(p.magnitude) & ~np.isnan(T.magnitude) & ~np.isnan(Td.magnitude)
        p = p[valid_mask]
        T = T[valid_mask]
        Td = Td[valid_mask]
        u = u[valid_mask]
        v = v[valid_mask]
        height = height[valid_mask] # Apply mask to height as well

        # Get the time from the dataframe's attributes for the title
        # The 'dt' from the successful fetch is used as the valid time
        time_val = dt

        print(f"Processing data for {station_name_long} at {time_val:%Y-%m-%d %H:%M}Z.")
        
        # --- 4. Calculate Thermodynamic Properties ---
        # Define the mixed-layer parcel using the average of the lowest 3 observations.
        if len(p) >= 3:
            sfc_pressure = p[0]
            sfc_temperature = np.mean(T[:3])
            sfc_dewpoint = np.mean(Td[:3])
            print("Using mixed-layer parcel (mean of lowest 3 points).")
        else:
            sfc_pressure = p[0]
            sfc_temperature = T[0]
            sfc_dewpoint = Td[0]
            print("Fewer than 3 points available; using surface-based parcel.")

        # Calculate the parcel profile for plotting and CAPE/CIN calculations.
        parcel_prof = mpcalc.parcel_profile(p, sfc_temperature, sfc_dewpoint).to('degC')

        # Calculate CAPE and CIN
        cape, cin = mpcalc.cape_cin(p, T, Td, parcel_prof)
        print(f"Calculated CAPE: {cape:.2f}")
        print(f"Calculated CIN: {cin:.2f}")
        
        # Calculate LCL, LFC, and EL
        lcl_pressure, lcl_temperature = mpcalc.lcl(sfc_pressure, sfc_temperature, sfc_dewpoint)
        p_for_lfc, T_for_lfc, Td_for_lfc = p, T.copy(), Td.copy()
        T_for_lfc[0], Td_for_lfc[0] = sfc_temperature, sfc_dewpoint
        lfc_pressure, lfc_temperature = mpcalc.lfc(p_for_lfc, T_for_lfc, Td_for_lfc, which='most_cape')
        el_pressure, el_temperature = mpcalc.el(p_for_lfc, T_for_lfc, Td_for_lfc, which='most_cape')

        # --- 4a. Calculate Additional Instability Indices ---
        print("Calculating instability indices...")
        indices = {}
        
        # ### MODIFICATION START: LIFTED-INDEX CALCULATION ###
        # Lifted Index
        try:
            # Use the same robust data preparation as the K-Index to ensure we use
            # all available temperature data, ignoring any gaps in dewpoint data.
            p_full = df['pressure'].values * units.hPa
            T_full = df['temperature'].values * units.degC
            valid_T_mask = ~np.isnan(p_full.magnitude) & ~np.isnan(T_full.magnitude)
            p_for_interp = p_full[valid_T_mask]
            T_for_interp = T_full[valid_T_mask]

            # Recalculate the parcel profile using the full pressure column for temperature.
            # This ensures the parcel path extends as high as the temperature data does.
            parcel_prof_full = mpcalc.parcel_profile(p_for_interp, sfc_temperature, sfc_dewpoint)

            # Define target pressure
            p_500 = 500 * units.hPa

            # Interpolate environmental temperature at 500 hPa from the full T profile.
            # We add [0] to extract the single value from the array returned by interpolate_1d.
            t_500 = interpolate_1d(p_500, p_for_interp, T_for_interp)[0]

            # Interpolate parcel temperature at 500 hPa from the full parcel profile.
            parcel_t_500 = interpolate_1d(p_500, p_for_interp, parcel_prof_full)[0]

            # Calculate Lifted Index. The units library correctly handles degC - degC = delta_degC.
            li_val = t_500 - parcel_t_500

            indices['Lifted Index'] = f'Lifted Index: {li_val.to("delta_degC").magnitude:.2f} °C'
            print("Lifted Index calculated successfully.")

        except Exception as e:
            indices['Lifted Index'] = 'Lifted Index: N/A'
            print(f"Could not calculate Lifted Index. Error: {e}")
        # ### MODIFICATION END ###

        # Showalter Index
        try:
            si_val = mpcalc.showalter_index(p, T, Td)
            indices['Showalter Index'] = f'Showalter Index: {si_val[0].to("delta_degC").magnitude:.2f} °C'
        except Exception:
            indices['Showalter Index'] = 'Showalter Index: N/A'

        # ### MODIFICATION START: K-INDEX CALCULATION ###
        # K Index - Interpolate to required levels to avoid 'N/A'
        try:
            # We need T at 850, 700, 500 hPa and Td at 850, 700 hPa.
            # T data is often available higher up than Td data. We will handle them
            # separately to ensure we use all available data.

            # Prepare data for Temperature interpolation (only requires valid P and T)
            p_full = df['pressure'].values * units.hPa
            T_full = df['temperature'].values * units.degC
            valid_T_mask = ~np.isnan(p_full.magnitude) & ~np.isnan(T_full.magnitude)
            p_for_T_interp = p_full[valid_T_mask]
            T_for_T_interp = T_full[valid_T_mask]

            # Prepare data for Dewpoint interpolation (requires valid P, T, and Td)
            Td_full = df['dewpoint'].values * units.degC
            valid_Td_mask = ~np.isnan(p_full.magnitude) & ~np.isnan(T_full.magnitude) & ~np.isnan(Td_full.magnitude)
            p_for_Td_interp = p_full[valid_Td_mask]
            Td_for_Td_interp = Td_full[valid_Td_mask]

            # Interpolate temperatures.
            p_req_T = np.array([850, 700, 500]) * units.hPa
            T_req = interpolate_1d(p_req_T, p_for_T_interp, T_for_T_interp)
            T850, T700, T500 = T_req[0], T_req[1], T_req[2]

            # Interpolate dewpoints.
            p_req_Td = np.array([850, 700]) * units.hPa
            Td_req = interpolate_1d(p_req_Td, p_for_Td_interp, Td_for_Td_interp)
            Td850, Td700 = Td_req[0], Td_req[1]

            # **FIX for units**: Extract magnitudes for calculation to avoid unit conflicts.
            t850_m = T850.magnitude
            t500_m = T500.magnitude
            td850_m = Td850.magnitude
            t700_m = T700.magnitude
            td700_m = Td700.magnitude

            # Perform calculation on raw numbers
            k_val_mag = (t850_m - t500_m) + td850_m - (t700_m - td700_m)

            # Re-attach the final, correct unit for an index
            k_val = k_val_mag * units.delta_degC

            indices['K Index'] = f'K Index: {k_val.to("delta_degC").magnitude:.2f} °C'
            print("K-Index calculated successfully.")

        except Exception as e:
            # This block will now only be entered if data is truly missing within the required layers.
            indices['K Index'] = 'K Index: N/A'
            print(f"Could not calculate K-Index, likely due to missing data within the 850-700 hPa layer. Error: {e}")
        # ### MODIFICATION END ###
            
        # Total Totals Index
        try:
            tt_val = mpcalc.total_totals_index(p, T, Td)
            indices['Total Totals'] = f'Total Totals: {tt_val.to("delta_degC").magnitude:.2f} °C'
        except Exception:
            indices['Total Totals'] = 'Total Totals: N/A'

        # Precipitable Water (mm)
        try:
            pwat_val = mpcalc.precipitable_water(p, Td)
            indices['Precipitable Water'] = f'Precipitable Water: {pwat_val.to("mm").magnitude:.2f} mm'
        except Exception:
            indices['Precipitable Water'] = 'Precipitable Water: N/A'

        # 0-6 km Bulk Shear
        try:
            shear_u, shear_v = mpcalc.bulk_shear(p, u, v, height=height, depth=6000 * units.meter)
            shear_mag = mpcalc.wind_speed(shear_u, shear_v)
            indices['0-6km Bulk Shear'] = f'0-6km Bulk Shear: {shear_mag.to("knots").magnitude:.2f} kts'
        except Exception:
            indices['0-6km Bulk Shear'] = '0-6km Bulk Shear: N/A'

        # --- 5. Create the Skew-T Plot ---
        print("Generating Skew-T plot...")
        fig = plt.figure(figsize=(12, 12)) 
        skew = SkewT(fig, rotation=45)

        skew.plot(p, T, 'r', linewidth=2, label='Temperature')
        skew.plot(p, Td, 'g', linewidth=2, label='Dewpoint')
        skew.plot_barbs(p[::5], u[::5], v[::5], y_clip_radius=0.03)
        skew.plot(p, parcel_prof, 'k', linewidth=2, linestyle='--', label='Parcel Path')

        skew.shade_cin(p, T, parcel_prof, Td, alpha=0.2, color='blue')
        skew.shade_cape(p, T, parcel_prof, alpha=0.2, color='red')
        
        if np.isfinite(lcl_pressure):
             skew.plot(lcl_pressure, lcl_temperature, 'ko', markerfacecolor='black', label='LCL')
        if np.isfinite(lfc_pressure):
             skew.plot(lfc_pressure, lfc_temperature, 'bo', markerfacecolor='blue', label='LFC')
        if np.isfinite(el_pressure):
             skew.plot(el_pressure, el_temperature, 'ro', markerfacecolor='red', label='EL')

        skew.plot_dry_adiabats(alpha=0.25)
        skew.plot_moist_adiabats(alpha=0.25)
        skew.plot_mixing_lines(alpha=0.25)

        # --- 6. Finalize the Plot ---
        skew.ax.set_ylim(1050, 100)
        skew.ax.set_xlim(-40, 40)
        
        plt.title(f'Skew-T Log-P for {station_name_long}', loc='left')
        plt.title(f'Valid: {time_val:%Y-%m-%d %H:%M}Z', loc='right')
        plt.xlabel(f'Temperature ({T.units:~P})')
        plt.ylabel(f'Pressure ({p.units:~P})')
        skew.ax.tick_params(axis='x', colors='black')
        skew.ax.tick_params(axis='y', colors='black')
        
        # --- 6a. Add Indices to Plot ---
        indices_text = (
            f'CAPE: {cape.magnitude:.2f} J/kg\n'
            f'CIN: {cin.magnitude:.2f} J/kg\n'
            f'{indices.get("Lifted Index", "Lifted Index: N/A")}\n'
            f'{indices.get("Showalter Index", "Showalter Index: N/A")}\n'
            f'{indices.get("K Index", "K Index: N/A")}\n'
            f'{indices.get("Total Totals", "Total Totals: N/A")}\n'
            f'{indices.get("Precipitable Water", "Precipitable Water: N/A")}\n'
            f'{indices.get("0-6km Bulk Shear", "0-6km Bulk Shear: N/A")}'
        )
        
        # ### MODIFICATION START: MOVE TEXT BOX ###
        # Place text box in the upper-left corner of the plot axes
        skew.ax.text(0.02, 0.98, indices_text,
                     transform=skew.ax.transAxes,
                     verticalalignment='top',
                     horizontalalignment='left',
                     fontsize=10,
                     bbox=dict(boxstyle='round', facecolor='white', alpha=0.75))
        # ### MODIFICATION END ###

        skew.ax.legend()
        plt.grid(True)

        # --- 7. Save and Show the Plot ---
        os.makedirs(save_dir, exist_ok=True)
        date_str = time_val.strftime('%Y%m%d_%H%M')
        # Updated filename to reflect the station ID
        filename = f"{station_id}_sounding_{date_str}.png"
        filepath = os.path.join(save_dir, filename)

        plt.savefig(filepath, bbox_inches='tight')
        print(f"Plot saved to: {filepath}")
        
        plt.show()
        print("Plot displayed.")

    except Exception as e:
        # This will catch errors in plotting or data processing *after* a successful download
        print(f"An error occurred during plot generation: {e}")


# --- Main execution ---
if __name__ == '__main__':
    # WMO ID for Thessaloniki, Makedonia Airport is 16622
    thessaloniki_station_id = '16622'
    station_full_name = 'Thessaloniki International Airport (LGTS)'
    # Define the directory to save the sounding plot
    # Make sure this path is correct for your system
    save_directory = '/home/dimitris/weather_station/upper_air_soundings'
    
    plot_skewt_for_station(thessaloniki_station_id, station_full_name, save_directory)
