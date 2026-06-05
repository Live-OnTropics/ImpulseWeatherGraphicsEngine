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
            param_class = "temp"
        elif map_type == "Forecast Low Temperatures":
            candidates = ep["lows_candidates"]
            param_class = "temp"
        else:
            candidates = ep["rain_candidates"]
            param_class = "rain"
            
        print(f"Connecting to Unidata's {name}...")
        try:
            ds = xr.open_dataset(url)
            
            # Locate active variable
            temp_var = None
            for candidate in candidates:
                for v in ds.variables:
                    if candidate in v.lower():
                        temp_var = v
                        break
                if temp_var is not None:
                    break
                    
            if temp_var is None:
                for v in ds.variables:
                    v_lower = v.lower()
                    if 'temperature' in v_lower or 'temp' in v_lower or 'precip' in v_lower:
                        temp_var = v
                        break
                        
            if temp_var is None:
                raise ValueError("Variable is currently missing on the active server instance.")

            # Classify grid type based solely on active dimensions (No coordinate scanning needed)
            temp_dims = ds[temp_var].dims
            is_projected = any('y' in d.lower() for d in temp_dims) and any('x' in d.lower() for d in temp_dims)

            # Crop spatial region
            if is_projected:
                # Projected Grid (NAM, HRRR, NDFD)
                # Resolve dimensions with flexible staggered indices (e.g. x_0, y_0)
                x_dim = [d for d in temp_dims if 'x' in d.lower()][0]
                y_dim = [d for d in temp_dims if 'y' in d.lower()][0]
                
                ds = ds.metpy.parse_cf()
                data_proj = ds[temp_var].metpy.cartopy_crs
                
                transformed_corners = data_proj.transform_points(
                    ccrs.PlateCarree(), np.array([-112.44, -87.56]), np.array([24.0, 38.0])
                )
                x_slice = slice(min(transformed_corners[:, 0]), max(transformed_corners[:, 0]))
                y_slice = slice(min(transformed_corners[:, 1]), max(transformed_corners[:, 1]))
                
                subset = ds[temp_var].sel(**{x_dim: x_slice, y_dim: y_slice})
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
                
                subset = ds[temp_var].isel(**{y_dim: y_slice, x_dim: x_slice})
                grid_lon = lon_arr[x_slice]
                grid_lat = lat_arr[y_slice]
                data_proj = ccrs.PlateCarree()
                
            # Locate time index coordinates
            time_dim = [d for d in subset.dims if 'time' in d][0]
            time_vals = subset[time_dim].values
            hours_since_start = (time_vals - time_vals[0]) / np.timedelta64(1, 'h')
            
            # Squeeze out singleton dimensions before conversions (fixes potential dimension errors)
            subset = subset.squeeze()
            
            # High-Precision Unit Conversions (Performed on raw float arrays prior to temporal calculations)
            units = ds[temp_var].attrs.get('units', '').lower()
            if param_class == "temp":
                sample_val = float(np.atleast_1d(subset.values).flat[0])
                if 'k' in units or sample_val > 150:
                    subset_converted = (subset - 273.15) * 1.8 + 32
                elif 'c' in units or sample_val < 50:
                    subset_converted = subset * 1.8 + 32
                else:
                    subset_converted = subset
            else:
                # Convert precipitation millimeter outputs to standard inches
                if 'mm' in units or 'grib_units_mm' in str(ds[temp_var]).lower():
                    subset_converted = subset / 25.4
                else:
                    subset_converted = subset
            
            if param_class == "temp":
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
            else:
                # For Rain: Find all time steps up to the target forecast accumulation window
                time_indices = np.where(hours_since_start <= float(forecast_setting))[0]
                if len(time_indices) == 0:
                    time_indices = [0]
                    
                subset_rain = subset_converted.isel(**{time_dim: time_indices})
                
                # We only sum if the variable contains "1_hour" or "3_hour" and is NOT a mixed aggregate
                v_lower = temp_var.lower()
                is_interval = ("1_hour" in v_lower or "3_hour" in v_lower) and ("mixed" not in v_lower and "accumulation" not in v_lower)
                
                if is_interval:
                    # Sum all intervals up to target hour for true continuous accumulation
                    subset_sliced = subset_rain.sum(dim=time_dim).squeeze().load()
                else:
                    # Already stored as bulk accumulated values from start (F00), slice last element
                    subset_sliced = subset_rain.isel(**{time_dim: -1}).squeeze().load()
                    
                grid_temp = subset_sliced.values
            
            # Match grid array positions to stations
            for city, (lat, lon) in MAP_LABELS_REDUCED.items():
                if is_projected:
                    val = find_nearest_projected_value(grid_lon, grid_lat, grid_temp, lon, lat, data_proj)
                else:
                    val = find_nearest_regular_value(grid_lon, grid_lat, grid_temp, lon, lat)
                
                # Format rainfall outputs to decimals, and temperature to integers
                map_label_temps[city] = round(val, 2) if param_class == "rain" else int(round(val))
                
            print(f"-> Successfully loaded forecast from: {name}")
            return grid_lon, grid_lat, grid_temp, map_label_temps, name, data_proj
            
        except Exception as ex:
            print(f"   [!] Failed to pull from {name}: {ex}")
            print("   Trying next dataset...")
            
    raise ConnectionError(
        "Live NOAA/NWS forecast servers are currently undergoing index updates and are unreachable. "
        "Please try again in a few minutes."
    )
