# src/core/data_fetcher.py
import numpy as np
import xarray as xr
import metpy
import cartopy.crs as ccrs
import pandas as pd
import zoneinfo
import datetime
from src.config.models import MODEL_ENDPOINTS

def find_nearest_regular_value(lon_coord, lat_coord, grid_data, target_lon, target_lat):
    idx_x = np.abs(lon_coord - target_lon).argmin()
    idx_y = np.abs(lat_coord - target_lat).argmin()
    val = grid_data[idx_y, idx_x]
    return float(np.atleast_1d(val).flat[0])

def find_nearest_projected_value(x_coord, y_coord, grid_data, target_lon, target_lat, data_proj):
    point = data_proj.transform_point(target_lon, target_lat, ccrs.PlateCarree())
    target_x, target_y = point[0], point[1]
    idx_x = np.abs(x_coord - target_x).argmin()
    idx_y = np.abs(y_coord - target_y).argmin()
    val = grid_data[idx_y, idx_x]
    return float(np.atleast_1d(val).flat[0])

def get_model_data(target_model, map_type, forecast_setting, product, region):
    grid_lon, grid_lat, grid_temp = None, None, None
    map_label_temps = {}
    model_name = None
    data_proj = ccrs.PlateCarree()
    run_cycle_str = ""
    
    endpoints = MODEL_ENDPOINTS.copy()
    if target_model:
        endpoints = [ep for ep in endpoints if target_model in ep["name"]] + [ep for ep in endpoints if target_model not in ep["name"]]
        
    for ep in endpoints:
        name = ep["name"]
        url = ep["url"]
        candidates = product.get_candidates(ep, map_type)
            
        print(f"Connecting to Unidata's {name}...")
        try:
            ds = xr.open_dataset(url)
            ds = ds.metpy.parse_cf()
            
            # Wrap longitudes from [0, 360] to [-180, 180] and sort them strictly increasing at the dataset level
            for coord in list(ds.coords) + list(ds.variables):
                if coord.lower() in ['lon', 'longitude']:
                    try:
                        if ds[coord].max() > 180:
                            ds = ds.assign_coords(**{coord: (((ds[coord] + 180) % 360) - 180)})
                            ds = ds.sortby(coord)
                        break
                    except Exception as e:
                        print(f"Skipping early longitude wrapping: {e}")
            
            is_precip = "Precipitation" in map_type
            temp_var = None
            coordinate_names = ['lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'time', 'reftime', 'height_above_ground', 'projection']
            
            # 1. Primary search: exact candidate matches
            for candidate in candidates:
                for v in ds.variables:
                    if candidate.lower() in v.lower():
                        temp_var = v
                        break
                if temp_var is not None:
                    break
                    
            # 2. Resilient secondary search: strict product-type checking (prevents mixing temperature and precipitation)
            if temp_var is None:
                for v in ds.variables:
                    v_lower = v.lower()
                    if any(c in v_lower for c in coordinate_names):
                        continue
                    if is_precip:
                        if 'precip' in v_lower or 'apcp' in v_lower or 'prate' in v_lower:
                            temp_var = v
                            break
                    else:
                        if 'temperature' in v_lower or 'temp' in v_lower:
                            temp_var = v
                            break
                        
            if temp_var is None:
                raise ValueError(f"No matching variables found in the {name} schema.")

            # Identify if the chosen variable is an hourly step or a mixed-interval cumulative bucket
            is_hourly_accumulation = "1_hour" in temp_var.lower()

            reftime_dims = [d for d in ds[temp_var].dims if 'reftime' in d.lower()]
            if reftime_dims:
                ds_var = ds[temp_var].isel(**{reftime_dims[0]: -1})
            else:
                ds_var = ds[temp_var]

            reftime_coord_name = None
            for coord in ds.coords:
                if any(k in coord.lower() for k in ['reftime', 'ref_time', 'reference_time']):
                    reftime_coord_name = coord
                    break
            
            utc_ref = None
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

            temp_dims = ds_var.dims
            is_projected = any('y' in d.lower() for d in temp_dims) and any('x' in d.lower() for d in temp_dims)

            padding = 1.5

            if is_projected:
                x_dim = [d for d in temp_dims if 'x' in d.lower()][0]
                y_dim = [d for d in temp_dims if 'y' in d.lower()][0]
                
                data_proj = ds_var.metpy.cartopy_crs
                
                transformed_corners = data_proj.transform_points(
                    ccrs.PlateCarree(), 
                    np.array([region.extent[0] - padding, region.extent[1] + padding]), 
                    np.array([region.extent[2] - padding, region.extent[3] + padding])
                )
                x_slice = slice(min(transformed_corners[:, 0]), max(transformed_corners[:, 0]))
                y_slice = slice(min(transformed_corners[:, 1]), max(transformed_corners[:, 1]))
                
                subset = ds_var.sel(**{x_dim: x_slice, y_dim: y_slice})
                grid_lon = subset[x_dim].values
                grid_lat = subset[y_dim].values
            else:
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
                
                y_dim = ds[lat_var].dims[0]
                x_dim = ds[lon_var].dims[0]
                
                lat_indices = np.where((lat_arr >= region.extent[2] - padding) & (lat_arr <= region.extent[3] + padding))[0]
                lon_indices = np.where((lon_arr >= region.extent[0] - padding) & (lon_arr <= region.extent[1] + padding))[0]
                
                y_slice = slice(min(lat_indices), max(lat_indices) + 1)
                x_slice = slice(min(lon_indices), max(lon_indices) + 1)
                
                subset = ds_var.isel(**{y_dim: y_slice, x_dim: x_slice})
                grid_lon = lon_arr[x_slice]
                grid_lat = lat_arr[y_slice]
                data_proj = ccrs.PlateCarree()
                
            time_dim = [d for d in subset.dims if 'time' in d][0]
            
            try:
                time_coord = subset[time_dim]
                if len(time_coord) != len(np.unique(time_coord)):
                    _, unique_indices = np.unique(time_coord.values[::-1], return_index=True)
                    unique_indices = len(time_coord) - 1 - unique_indices
                    unique_indices = sorted(unique_indices)
                    subset = subset.isel(**{time_dim: unique_indices})
            except Exception as e:
                print(f"Time deduplication skipped: {e}")
            
            # Squeeze out only non-time singleton dimensions to preserve the time dimension for aggregation
            squeeze_dims = [d for d in subset.dims if 'time' not in d.lower() and subset[d].size == 1]
            if squeeze_dims:
                subset = subset.squeeze(dim=squeeze_dims)
                
            units = ds[temp_var].attrs.get('units', '')
            subset_converted = product.process_units(subset, units)
            
            pd_times = pd.to_datetime(subset[time_dim].values)
            pd_times_utc = pd_times.tz_localize('UTC') if pd_times.tz is None else pd_times.tz_convert('UTC')
            
            if "Precipitation" in map_type:
                # Calculate active model run initialization index (anchor point)
                base_ref = utc_ref if utc_ref is not None else pd_times_utc[0]
                start_idx = np.abs(pd_times_utc - base_ref).argmin()
                
                target_time_utc = base_ref + datetime.timedelta(hours=int(forecast_setting))
                target_idx = np.abs(pd_times_utc - target_time_utc).argmin()
                target_hour = int(forecast_setting)
                
                hours_since_ref = np.array([(t - base_ref).total_seconds() / 3600.0 for t in pd_times_utc])
                
                if is_hourly_accumulation:
                    # HRRR, RAP, NAM 3km (Sum intervals only from active initialization index)
                    time_indices = slice(start_idx, target_idx + 1)
                else:
                    # GFS, NDFD, NAM 12km (mixed-interval running total buckets)
                    bounds_var_name = ds[time_dim].attrs.get('bounds')
                    
                    # Robust fallback variable scanner to identify dynamically changing bounds dimensions
                    if not bounds_var_name or bounds_var_name not in ds.variables:
                        time_size = ds[time_dim].size
                        for v in ds.variables:
                            v_lower = v.lower()
                            if 'bounds' in v_lower:
                                shape = ds[v].shape
                                if len(shape) == 2 and shape[0] == time_size and shape[1] == 2:
                                    bounds_var_name = v
                                    print(f"[DEBUG] Fallback bounds resolver found: {bounds_var_name} (time_size: {time_size})")
                                    break
                                    
                    exact_target_match = []
                    
                    if bounds_var_name and bounds_var_name in ds.variables:
                        try:
                            bounds_arr = ds[bounds_var_name].values
                            print(f"[DEBUG] Loaded bounds variable '{bounds_var_name}' with shape {bounds_arr.shape}")
                            
                            # Strategy A: Look for a master bucket spanning exactly 0 to target_hour
                            for i in range(start_idx, len(bounds_arr)):
                                start_h = float(bounds_arr[i, 0])
                                end_h = float(bounds_arr[i, 1])
                                if abs(start_h) < 0.01 and abs(end_h - target_hour) < 0.1:
                                    exact_target_match = [i]
                                    print(f"[DEBUG] Strategy A Triggered: Found master 0-to-{target_hour}h bucket at index {i} (bounds: {start_h} -> {end_h})")
                                    break
                            
                            # Strategy B: If no 0-to-H bucket exists (common at/after Hour 120),
                            # gather all non-overlapping contiguous intervals up to the target_hour
                            if not exact_target_match:
                                print(f"[DEBUG] Strategy A failed (No 0-to-{target_hour}h master bucket found). Triggering Strategy B (backward-stitching)...")
                                interval_indices = []
                                current_seeking_end = target_hour
                                
                                # Walk backwards from the target hour to stitch intervals together
                                for i in reversed(range(start_idx, target_idx + 1)):
                                    start_h = float(bounds_arr[i, 0])
                                    end_h = float(bounds_arr[i, 1])
                                    
                                    if abs(end_h - current_seeking_end) < 0.1:
                                        interval_indices.append(i)
                                        print(f"[DEBUG] Strategy B: Selected interval at index {i} (bounds: {start_h} -> {end_h}, matching end: {current_seeking_end})")
                                        current_seeking_end = start_h # Next, find the chunk feeding into this one
                                        if current_seeking_end < 0.01:
                                            print(f"[DEBUG] Strategy B: Backward-stitching completed successfully. Reached 0.0h initialization.")
                                            break
                                
                                if interval_indices:
                                    exact_target_match = sorted(interval_indices)
                                    print(f"[DEBUG] Strategy B final selected indices: {exact_target_match}")
                                else:
                                    print(f"[DEBUG] Strategy B failed to stitch intervals up to {target_hour}h.")
                                    
                        except Exception as e:
                            print(f"[DEBUG] Error parsing mixed interval bounds: {e}")
                            
                    if len(exact_target_match) > 0:
                        time_indices = exact_target_match
                    else:
                        time_indices = [target_idx]
            else:
                # Traditional temperature calendar indexing
                pd_times_local = pd_times_utc.tz_convert(region.timezone_str)
                target_tz = zoneinfo.ZoneInfo(region.timezone_str)
                now_local = datetime.datetime.now(target_tz)
                today_date = now_local.date()
                target_date = today_date + datetime.timedelta(days=int(forecast_setting))
                local_dates = pd_times_local.date
                time_indices = np.where(local_dates == target_date)[0]
                if len(time_indices) == 0:
                    time_indices = np.where(local_dates == local_dates[0])[0]
                if len(time_indices) == 0:
                    time_indices = [0]
                    
            subset_day = subset_converted.isel(**{time_dim: time_indices})
            
            # Force explicit handling for Precipitation accumulations [input_file_5.py]
            if is_precip:
                if len(time_indices) > 1:
                    print(f"[DEBUG] Strategy B Active: Explicitly summing {len(time_indices)} intervals for Total Precipitation.")
                    max_temp_grid = subset_day.sum(dim=time_dim).load()
                else:
                    print(f"[DEBUG] Strategy A Active: Extracting single master accumulation bucket at index {time_indices[0]}.")
                    # Squeeze out the time dimension since we are using a single index, ensuring it matches grid expectations
                    max_temp_grid = subset_day.squeeze(dim=time_dim).load()
            else:
                # Traditional temperature or other non-accumulation variables
                max_temp_grid = product.aggregate_time(subset_day, time_dim, map_type)
                
            grid_temp = max_temp_grid.values
            
            # If latitudes are descending, reverse them and the grid values to be strictly increasing
            if not is_projected and len(grid_lat) > 1 and grid_lat[1] < grid_lat[0]:
                grid_lat = grid_lat[::-1]
                grid_temp = grid_temp[::-1, :]
            
            for city, (lat, lon) in region.cities.items():
                if is_projected:
                    val = find_nearest_projected_value(grid_lon, grid_lat, grid_temp, lon, lat, data_proj)
                else:
                    val = find_nearest_regular_value(grid_lon, grid_lat, grid_temp, lon, lat)
                
                # Render floats for precipitation, integers for temperature
                map_label_temps[city] = round(val, 2) if "Precipitation" in map_type else int(round(val))
                
            print(f"-> Successfully loaded forecast from: {name}")
            return grid_lon, grid_lat, grid_temp, map_label_temps, name, data_proj, run_cycle_str
            
        except Exception as ex:
            print(f"   [!] Failed to pull from {name}: {ex}")
            print("   Trying next dataset...")
            
    raise ConnectionError("Live NOAA/NWS forecast servers are currently unreachable. Please try again soon.")
