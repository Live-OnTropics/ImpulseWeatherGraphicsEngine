# diagnose.py
import sys
import traceback
import datetime
import numpy as np
import cartopy.crs as ccrs
from src.config.regions import TexasRegion
from src.products.precipitation import PrecipitationProduct
from src.core.data_fetcher import get_model_data

def run_diagnostics():
    log_file = "diagnostics_log.txt"
    with open(log_file, "w") as f:
        f.write("=== Impulse Weather Graphics Engine Diagnostics ===\n")
        f.write(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        try:
            f.write("Testing Precipitation data-fetcher with GFS...\n")
            product = PrecipitationProduct()
            region = TexasRegion()
            
            grid_lon, grid_lat, grid_values, map_label_values, model_name, data_proj, run_cycle_str = get_model_data(
                "GFS", "Total Precipitation", 24, product, region
            )
            
            f.write("Successfully executed data fetcher!\n")
            f.write(f"Model: {model_name}\n")
            f.write(f"Reference Cycle: {run_cycle_str}\n")
            f.write(f"Grid Longitude shape: {grid_lon.shape if grid_lon is not None else 'None'}\n")
            f.write(f"Grid Latitude shape: {grid_lat.shape if grid_lat is not None else 'None'}\n")
            f.write(f"Grid Values shape: {grid_values.shape if grid_values is not None else 'None'}\n")
            
            if grid_values is not None:
                f.write(f"Grid Values range: Min={grid_values.min():.4f}, Max={grid_values.max():.4f}\n")
                f.write(f"Grid Values NaNs count: {np.isnan(grid_values).sum()}\n")
                
            f.write("\nCity Label Values calculated:\n")
            for city, val in map_label_values.items():
                f.write(f"  - {city}: {val}\n")
                
            print(f"Diagnostics passed! Logs saved to {log_file}")
        except Exception as e:
            f.write("\n!!! Diagnostics Failed !!!\n")
            traceback.print_exc(file=f)
            print(f"Diagnostics failed. Details saved to {log_file}")

if __name__ == '__main__':
    run_diagnostics()
