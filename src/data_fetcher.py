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


def get_time_index(ds, time_dim, param_type, value):
    """
    Finds the exact index in the time dimension coordinate arrays.
    For Temps: maps "Today", "Tomorrow", "Day 3" indices.
    For Rain: maps target forecast accumulation hours (24h, 48h, 72h).
    """
    try:
        time_vals = ds[time_dim].values
        hours_since_start = (time_vals - time_vals[0]) / np.timedelta64(1, 'h')
        
        if param_type == "rain":
            # For rain, we find the forecast hour that closely matches our target hour window (e.g., 24h)
            idx = np.abs(hours_since_start - float(value)).argmin()
            return int(idx)
        else:
            # For temperatures, NDFD publishes 12-hour maximums, so index maps cleanly
            if "ndfd" in str(ds).lower():
                return int(value)
            # In GFS/NAM, max temperature isn't aggregated into daily intervals.
            # We locate the maximum temperature point by scanning 24h chunks (index 8, 16, 24)
            step = 8 if "gfs" in str(ds).lower() or "nam" in str(ds).lower() else 24
            return int(value * step)
    except:
        # Static index fallback
        if param_type == "rain":
            mapping = {24: 8, 48: 16, 72: 24}
            return mapping.get(value, 8)
        return int(value)


def get_model_data(target_model, map_type, forecast_setting):
    """
    Queries THREDDS. Dynamically detects variable, coordinates (1D vs 2D), and 
    time boundaries. Raises a ConnectionError if the network or servers are offline.
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
                raise ValueError("Variable is currently missing on the active server instance.")

            ds = ds.metpy.parse_cf()
            temp_dims = ds[temp_var].dims
            is_projected = 'x' in temp_dims and 'y' in temp_dims
            
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
                if lon_arr.ndim == 1:
                    lon_arr = lon_arr - 360
                else:
                    lon_arr = np.where(lon_arr > 180, lon_arr - 360, lon_arr)
                    
            # Crop spatial region (1D GFS vs 2D Lambert CONUS grids)
            if ds[lat_var].ndim == 1:
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
            else:
                y_dim = ds[lat_var].dims[0]
                x_dim = ds[lat_var].dims[1]
                data_proj = ds[temp_var].metpy.cartopy_crs
                
                transformed_corners = data_proj.transform_points(
                    ccrs.PlateCarree(), np.array([-112.44, -87.56]), np.array([24.0, 38.0])
                )
                x_slice = slice(min(transformed_corners[:, 0]), max(transformed_corners[:, 0]))
                y_slice = slice(min(transformed_corners[:, 1]), max(transformed_corners[:, 1]))
                
                subset = ds[temp_var].sel(**{x_dim: x_slice, y_dim: y_slice})
                grid_lon = subset[x_dim].values
                grid_lat = subset[y_dim].values
                
            # Locate time index based on dropdown settings
            time_dim = [d for d in subset.dims if 'time' in d][0]
            time_idx = get_time_index(ds, time_dim, param_class, forecast_setting)
            subset_sliced = subset.isel(**{time_dim: min(time_idx, len(subset[time_dim]) - 1)}).squeeze()
            
            # Unit translations
            if param_class == "temp":
                units = ds[temp_var].attrs.get('units', '').lower()
                sample_val = float(np.atleast_1d(subset_sliced.values).flat[0])
                if 'k' in units or sample_val > 150:
                    grid_data = (subset_sliced - 273.15) * 1.8 + 32
                elif 'c' in units or sample_val < 50:
                    grid_data = subset_sliced * 1.8 + 32
                else:
                    grid_data = subset_sliced
            else:
                # Convert precipitation millimeter outputs to standard inches
                units = ds[temp_var].attrs.get('units', '').lower()
                if 'mm' in units:
                    grid_data = subset_sliced / 25.4
                else:
                    grid_data = subset_sliced
                    
            grid_temp = grid_data.squeeze().load().values
            
            # Match grid to stations
            for city, (lat, lon) in MAP_LABELS_REDUCED.items():
                if is_projected:
                    val = find_nearest_projected_value(grid_lon, grid_lat, grid_temp, lon, lat, data_proj)
                else:
                    val = find_nearest_regular_value(grid_lon, grid_lat, grid_temp, lon, lat)
                
                # Format to standard decimals if rainfall, otherwise round to integer
                map_label_temps[city] = round(val, 2) if param_class == "rain" else int(round(val))
                
            print(f"-> Successfully loaded forecast from: {name}")
            return grid_lon, grid_lat, grid_temp, map_label_temps, name, data_proj
            
        except Exception as ex:
            print(f"   [!] Failed to pull from {name}: {ex}")
            print("   Trying next dataset...")
            
    raise ConnectionError(
        "Live NOAA/NWS servers are currently undergoing index updates and are unreachable. "
        "Please try again in a few minutes."
    )
