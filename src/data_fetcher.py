# src/data_fetcher.py
import numpy as np
import xarray as xr
import metpy
import cartopy.crs as ccrs
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

            # 4. Classify grid type based solely on active dimensions of the variable
            temp_dims = ds_var.dims
            is_projected = any('y' in d.lower() for d in temp_dims) and any('x' in d.lower() for d in temp_dims)

            # 5. Crop spatial region
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
                
            # 6. Locate time dimension
            time_dim = [d for d in subset.dims if 'time' in d][0]
            
            # 7. Deduplicate time dimension
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
            time_vals = subset[time_dim].values
            hours_since_start = (time_vals - time_vals[0]) / np.timedelta64(1, 'h')
            
            # High-Precision Unit Conversions
            units = ds[temp_var].attrs.get('units', '').lower()
            sample_val = float(np.atleast_1d(subset.values).flat[0])
            if 'k' in units or sample_val > 150:
                subset_converted = (subset - 273.15) * 1.8 + 32
            elif 'c' in units or sample_val < 50:
                subset_converted = subset * 1.8 + 32
            else:
                subset_converted = subset
            
            # Isolate the exact 24-hour diurnal slice corresponding to selected day
            start_hour = forecast_setting * 24
            end_hour = (forecast_setting + 1) * 24
            
            time_indices = np.where((hours_since_start >= start_hour) & (hours_since_start <= end_hour))[0]
            if len(time_indices) == 0:
                time_indices = np.where(hours_since_start >= start_hour)[0]
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
            return grid_lon, grid_lat, grid_temp, map_label_temps, name, data_proj
            
        except Exception as ex:
            print(f"   [!] Failed to pull from {name}: {ex}")
            print("   Trying next dataset...")
            
    raise ConnectionError(
        "Live NOAA/NWS forecast servers are currently undergoing index updates and are unreachable. "
        "Please try again in a few minutes."
    )
