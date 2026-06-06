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
                if lon_arr.max() > 180:
                    lon_arr = lon_arr - 360
                    
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
                # Resolve the single forecast frame closest to the initialization time (reftime + h hours)
                base_ref = utc_ref if utc_ref is not None else pd_times_utc[0]
                target_time_utc = base_ref + datetime.timedelta(hours=int(forecast_setting))
                target_idx = np.abs(pd_times_utc - target_time_utc).argmin()
                target_hour = int(forecast_setting)
                
                # Compute hours since initialization for each forecast timestep
                hours_since_ref = np.array([(t - base_ref).total_seconds() / 3600.0 for t in pd_times_utc])
                
                is_gfs_or_ndfd = any(k in name.lower() for k in ["gfs", "ndfd"])
                
                if is_gfs_or_ndfd:
                    # GFS/NDFD mixed-intervals logic (isolates non-overlapping contiguous steps)
                    selected_indices = []
                    if target_hour % 6 == 0:
                        for i, h in enumerate(hours_since_ref):
                            if h > 0 and h <= target_hour and h % 6 == 0:
                                selected_indices.append(i)
                    else:
                        for i, h in enumerate(hours_since_ref):
                            if h > 0 and h < target_hour and h % 6 == 0:
                                selected_indices.append(i)
                            if int(round(h)) == target_hour:
                                selected_indices.append(i)
                                
                    if not selected_indices:
                        selected_indices = [target_idx]
                    time_indices = sorted(list(set(selected_indices)))
                else:
                    # HRRR, RAP, NAM 3km, and NAM 12km (contiguous hourly/3-hourly steps)
                    time_indices = slice(0, target_idx + 1)
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
            max_temp_grid = product.aggregate_time(subset_day, time_dim, map_type)
            grid_temp = max_temp_grid.values
            
            # If latitudes are descending, reverse them and the grid values to be strictly increasing [input_file_5.py]
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
