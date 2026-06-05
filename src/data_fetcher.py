# src/data_fetcher.py
import numpy as np
import xarray as xr
import metpy
import cartopy.crs as ccrs
import pandas as pd
import zoneinfo
import datetime
from src.config import MODEL_ENDPOINTS, MAP_LABELS_REDUCED

def find_nearest_regular_value(lon_coord, lat_coord, grid_data, target_lon, target_lat):
    """Finds nearest coordinate values on standard 1D grids."""
    idx_x = np.abs(lon_coord - target_lon).argmin()
    idx_y = np.abs(lat_coord - target_lat).argmin()
    val = grid_data[idx_y, idx_x]
    return float(np.atleast_1d(val).flat[0])


def find_nearest_projected_value(x_coord, y_coord, grid_data, target_lon, target_lat, data_proj):
    """Projects stations into native coordinate spaces for high-speed 1D indexing."""
    point = data_proj.transform_point(target_lon, target_lat, ccrs.PlateCarree())
    target_x, target_y = point[0], point[1]
    idx_x = np.abs(x_coord - target_x).argmin()
    idx_y = np.abs(y_coord - target_y).argmin()
    val = grid_data[idx_y, idx_x]
    return float(np.atleast_1d(val).flat[0])


def get_model_data(target_model, map_type, forecast_setting):
    """
    Queries THREDDS. Dynamically detects variable, coordinate dimensions, and 
    time boundaries. Raises a ConnectionError if the network is offline.
    """
    grid_lon, grid_lat, grid_temp = None, None, None
    map_label_temps = {}
    model_name = None
    data_proj = ccrs.PlateCarree()
    run_cycle_str = ""
    
    # Priority sequence list of Unidata THREDDS datasets
    endpoints = MODEL_ENDPOINTS.copy()
    if target_model:
        endpoints = [ep for ep in endpoints if target_model in ep["name"]] + [ep for ep in endpoints if target_model not in ep["name"]]
        
    for ep in endpoints:
        name = ep["name"]
        url = ep["url"]
        
        # Pull candidate names matching the selected parameters
        if map_type == "Forecast High Temperatures":
            candidates = ep["highs_candidates"]
        else:
            candidates = ep["lows_candidates"]
            
        print(f"Connecting to Unidata's {name}...")
        try:
            ds = xr.open_dataset(url)
            
            # 1. Parse CF metadata on the Dataset level immediately (This is where parse_cf exists)
            ds = ds.metpy.parse_cf()
            
            # 2. Discover temperature variable robustly
            temp_var = None
            coordinate_names = ['lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'time', 'reftime', 'height_above_ground', 'projection']
            temp_candidates = [
                'temperature_height_above_ground',
                'maximum_temperature_height_above_ground',
                'temperature_surface',
                'temp_air'
            ]
            
            for candidate in temp_candidates:
                for v in ds.variables:
                    if candidate in v.lower():
                        temp_var = v
                        break
                if temp_var is not None:
                    break
                    
            if temp_var is None:
                for v in ds.variables:
                    v_lower = v.lower()
                    if any(c in v_lower for c in coordinate_names) and 'temp' not in v_lower:
                        continue
                    if 'temperature' in v_lower or 'temp' in v_lower:
                        temp_var = v
                        break
                        
            if temp_var is None:
                raise ValueError(f"No matching temperature variables found in the {name} schema.")

            # 3. Isolate the latest single model run cycle (reftime) to prevent summing overlapping forecasts
            reftime_dims = [d for d in ds[temp_var].dims if 'reftime' in d.lower()]
            if reftime_dims:
                # Select only the most recent model run cycle
                ds_var = ds[temp_var].isel(**{reftime_dims[0]: -1})
            else:
                ds_var = ds[temp_var]

            # 4. Extract and format the model run cycle (reftime) for display
            reftime_coord_name = None
            for coord in ds.coords:
                if any(k in coord.lower() for k in ['reftime', 'ref_time', 'reference_time']):
                    reftime_coord_name = coord
                    break
                    
            if reftime_coord_name is not None:
                try:
                    ref_val = ds[reftime_coord_name].values
                    if ref_val.ndim > 0:
                        ref_val = ref_val[-1]
                    pd_ref = pd.to_datetime(ref_val)
                    if pd_ref.tz is None:
                        pd_ref = pd_ref.tz_localize('UTC')
                    utc_ref = pd_ref.tz_convert('UTC')
                    utc_hour = utc_ref.strftime("%H")
                    run_date = utc_ref.strftime("%Y-%m-%d")
                    run_cycle_str = f" ({run_date} {utc_hour}Z)"
                except Exception as e:
                    print(f"Reference time parsing skipped: {e}")

            # 5. Classify grid type based solely on active dimensions of the variable
            temp_dims = ds_var.dims
            is_projected = any('y' in d.lower() for d in temp_dims) and any('x' in d.lower() for d in temp_dims)

            # 6. Crop spatial region
            if is_projected:
                # Projected Grid (NAM, HRRR, NDFD)
                x_dim = [d for d in temp_dims if 'x' in d.lower()][0]
                y_dim = [d for d in temp_dims if 'y' in d.lower()][0]
                
                data_proj = ds_var.metpy.cartopy_crs
                
                transformed_corners = data_proj.transform_points(
                    ccrs.PlateCarree(), np.array([-112.44, -87.56]), np.array([24.0, 38.0])
                )
                x_slice = slice(min(transformed_corners[:, 0]), max(transformed_corners[:, 0]))
                y_slice = slice(min(transformed_corners[:, 1]), max(transformed_corners[:, 1]))
                
                subset = ds_var.sel(**{x_dim: x_slice, y_dim: y_slice})
                grid_lon = subset[x_dim].values
                grid_lat = subset[y_dim].values
            else:
                # Regular Latitude/Longitude Grid (GFS)
                lat_var, lon_var = None, None
                for v in ds.variables:
                    v_lower = v.lower()
                    if v_lower in ['latitude', 'lat']:
                        lat_var = v
                    elif v_lower in ['longitude', 'lon']:
                        lon_var = v
                        
                if lat_var is None or lon_var is None:
                    raise ValueError("Coordinates not found in the dataset schema.")
                    
                lat_arr = ds[lat_var].values
                lon_arr = ds[lon_var].values
                if lon_arr.max() > 180:
                    lon_arr = lon_arr - 360
                    
                y_dim = ds[lat_var].dims[0]
                x_dim = ds[lon_var].dims[0]
                
                lat_indices = np.where((lat_arr >= 24.0) & (lat_arr <= 38.0))[0]
                lon_indices = np.where((lon_arr >= -112.44) & (lon_arr <= -87.56))[0]
                
                y_slice = slice(min(lat_indices), max(lat_indices) + 1)
                x_slice = slice(min(lon_indices), max(lon_indices) + 1)
                
                subset = ds_var.isel(**{y_dim: y_slice, x_dim: x_slice})
                grid_lon = lon_arr[x_slice]
                grid_lat = lat_arr[y_slice]
                data_proj = ccrs.PlateCarree()
                
            # 7. Locate time dimension
            time_dim = [d for d in subset.dims if 'time' in d][0]
            
            # 8. Deduplicate time dimension (Crucial to prevent summing overlapping duplicate forecasts)
            try:
                time_coord = subset[time_dim]
                if len(time_coord) != len(np.unique(time_coord)):
                    _, unique_indices = np.unique(time_coord.values[::-1], return_index=True)
                    unique_indices = len(time_coord) - 1 - unique_indices
                    unique_indices = sorted(unique_indices)
                    subset = subset.isel(**{time_dim: unique_indices})
            except Exception as e:
                print(f"Time deduplication skipped: {e}")
            
            # Squeeze out singleton dimensions before conversions
            subset = subset.squeeze()
            
            # High-Precision Unit Conversions
            units = ds[temp_var].attrs.get('units', '').lower()
            sample_val = float(np.atleast_1d(subset.values).flat[0])
            if 'k' in units or sample_val > 150:
                subset_converted = (subset - 273.15) * 1.8 + 32
            elif 'c' in units or sample_val < 50:
                subset_converted = subset * 1.8 + 32
            else:
                subset_converted = subset
            
            # 9. Timezone-Aware Slicing strictly matching Austin (Central) Calendar Days
            austin_tz = zoneinfo.ZoneInfo("America/Chicago")
            now_austin = datetime.datetime.now(austin_tz)
            today_date = now_austin.date()
            
            # Determine the exact calendar date for the selection
            target_date = today_date + datetime.timedelta(days=int(forecast_setting))
            
            # Convert xarray forecast times to pandas and localize/convert to Austin Time
            pd_times = pd.to_datetime(subset[time_dim].values)
            if pd_times.tz is None:
                pd_times_utc = pd_times.tz_localize('UTC')
            else:
                pd_times_utc = pd_times.tz_convert('UTC')
            pd_times_austin = pd_times_utc.tz_convert('America/Chicago')
            austin_dates = pd_times_austin.date
            
            # Locate indices matching the target calendar date in Austin
            time_indices = np.where(austin_dates == target_date)[0]
            if len(time_indices) == 0:
                # Fallback to nearest day coordinates if target date is outside short-range model outputs
                time_indices = np.where(austin_dates == austin_dates[0])[0]
            if len(time_indices) == 0:
                time_indices = [0]
                
            subset_day = subset_converted.isel(**{time_dim: time_indices})
            
            # Take maximum (Highs) or minimum (Lows) dynamically across the 24h window
            is_high = "High" in map_type
            if is_high:
                max_temp_grid = subset_day.max(dim=time_dim).squeeze().load()
            else:
                max_temp_grid = subset_day.min(dim=time_dim).squeeze().load()
                
            grid_temp = max_temp_grid.values
            
            # Match grid array positions to stations
            for city, (lat, lon) in MAP_LABELS_REDUCED.items():
                if is_projected:
                    val = find_nearest_projected_value(grid_lon, grid_lat, grid_temp, lon, lat, data_proj)
                else:
                    val = find_nearest_regular_value(grid_lon, grid_lat, grid_temp, lon, lat)
                
                map_label_temps[city] = int(round(val))
                
            print(f"-> Successfully loaded forecast from: {name}")
            return grid_lon, grid_lat, grid_temp, map_label_temps, name, data_proj, run_cycle_str
            
        except Exception as ex:
            print(f"   [!] Failed to pull from {name}: {ex}")
            print("   Trying next dataset...")
            
    raise ConnectionError(
        "Live NOAA/NWS forecast servers are currently undergoing index updates and are unreachable. "
        "Please try again in a few minutes."
    )
