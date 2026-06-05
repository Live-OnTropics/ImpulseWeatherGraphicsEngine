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


def get_model_data(target_model=None):
    """
    Attempts to fetch live forecasts from selected THREDDS datasets.
    Raises a clean ConnectionError if all live sources are down.
    """
    grid_lon, grid_lat, grid_temp = None, None, None
    map_label_temps = {}
    model_name = None
    data_proj = ccrs.PlateCarree()
    
    # Priority sequence list of Unidata THREDDS datasets
    endpoints = MODEL_ENDPOINTS.copy()
    if target_model:
        endpoints = [ep for ep in endpoints if target_model in ep["name"]] + [ep for ep in endpoints if target_model not in ep["name"]]
        
    for ep in endpoints:
        name = ep["name"]
        url = ep["url"]
        candidates = ep["temp_candidates"]
        
        print(f"Attempting to connect to Unidata's {name}...")
        try:
            ds = xr.open_dataset(url)
            
            # Discover temperature variable robustly
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

            # Retrieve spatial coordinates using CF parser
            ds = ds.metpy.parse_cf()
            temp_dims = ds[temp_var].dims
            is_projected = 'x' in temp_dims and 'y' in temp_dims
            
            # Identify coordinate variables
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
                    
            # Slice spatial dimensions based on grid type (1D vs 2D)
            if ds[lat_var].ndim == 1:
                y_dim = ds[lat_var].dims[0]
                x_dim = ds[lon_var].dims[0]
                
                lat_indices = np.where((lat_arr >= 24.0) & (lat_arr <= 38.0))[0]
                lon_indices = np.where((lon_arr >= -112.44) & (lon_arr <= -87.56))[0]
                
                y_min, y_max = int(lat_indices.min()), int(lat_indices.max())
                x_min, x_max = int(lon_indices.min()), int(lon_indices.max())
                
                y_slice = slice(min(y_min, y_max), max(y_min, y_max) + 1)
                x_slice = slice(min(x_min, x_max), max(x_min, x_max) + 1)
                
                subset = ds[temp_var].isel(**{y_dim: y_slice, x_dim: x_slice})
                time_dim = [d for d in subset.dims if 'time' in d][0]
                subset = subset.isel(**{time_dim: slice(0, 8)}).squeeze()
                
                grid_lon = lon_arr[x_slice]
                grid_lat = lat_arr[y_slice]
                data_proj = ccrs.PlateCarree()
            else:
                y_dim = ds[lat_var].dims[0]
                x_dim = ds[lat_var].dims[1]
                
                data_proj = ds[temp_var].metpy.cartopy_crs
                
                # Convert bounding corners from degrees to native coordinate space
                plate_carree = ccrs.PlateCarree()
                transformed_corners = data_proj.transform_points(
                    plate_carree,
                    np.array([-112.44, -87.56]),    # Wide bounds matching 16:9 ratio
                    np.array([24.0, 38.0])
                )
                x_bounds = transformed_corners[:, 0]
                y_bounds = transformed_corners[:, 1]
                
                x_slice = slice(min(x_bounds), max(x_bounds))
                y_slice = slice(min(y_bounds), max(y_bounds))
                
                # Slice variables using coordinate boundaries
                subset = ds[temp_var].sel(**{x_dim: x_slice, y_dim: y_slice})
                time_dim = [d for d in subset.dims if 'time' in d][0]
                subset = subset.isel(**{time_dim: slice(0, 8)}).squeeze()
                
                grid_lon = subset[x_dim].values
                grid_lat = subset[y_dim].values
                
            # Convert units dynamically
            units = ds[temp_var].attrs.get('units', '').lower()
            sample_val = float(np.atleast_1d(subset.values).flat[0])
            if 'k' in units or sample_val > 150:
                temp_f = (subset - 273.15) * 1.8 + 32
            elif 'c' in units or sample_val < 50:
                temp_f = subset * 1.8 + 32
            else:
                temp_f = subset
                
            max_temp_grid = temp_f.max(dim=time_dim).squeeze().load()
            grid_temp = max_temp_grid.values
            
            # Match actual grid values to stations
            for city, (lat, lon) in MAP_LABELS_REDUCED.items():
                if is_projected:
                    map_label_temps[city] = int(round(find_nearest_projected_value(grid_lon, grid_lat, grid_temp, lon, lat, data_proj)))
                else:
                    map_label_temps[city] = int(round(find_nearest_regular_value(grid_lon, grid_lat, grid_temp, lon, lat)))
                    
            print(f"-> Successfully loaded forecast from: {name}")
            model_name = name
            return grid_lon, grid_lat, grid_temp, map_label_temps, model_name, data_proj
            
        except Exception as ex:
            print(f"   [!] Failed to pull from {name}: {ex}")
            print("   Trying next dataset...")
            
    # If all priority endpoints fail, raise a clean ConnectionError (Never use fake data)
    raise ConnectionError(
        "NOAA/NWS forecast servers are currently undergoing scheduled indexing and are unreachable. "
        "Please wait a few minutes and try again."
    )
