import os
import datetime
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Circle
from matplotlib.patheffects import withStroke
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.io import shapereader
from scipy.interpolate import griddata

# ==========================================
# 1. Configuration & Dictionaries
# ==========================================
# Supported States & Coordinates
REGIONS = {
    'Texas': {
        'extent': [-112.44, -87.56, 24.0, 38.0],
        'center_lon': -100.0,
        'state_name': 'Texas'
    },
    'Oklahoma': {
        'extent': [-104.0, -93.5, 33.0, 38.0],
        'center_lon': -98.7,
        'state_name': 'Oklahoma'
    },
    'Gulf Coast': {
        'extent': [-100.0, -80.0, 24.0, 33.0],
        'center_lon': -90.0,
        'state_name': None  # Do not mask if regional
    }
}

# Supported Map Types with Variable Schemas and Colormaps
MAP_TYPES = {
    'Forecast High Temperatures': {
        'candidates': ['maximum_temperature_height_above_ground', 'temperature_height_above_ground'],
        'colormap': 'nipy_spectral',
        'vmin': -40,
        'vmax': 120,
        'ticks': [-40, -20, 0, 20, 40, 60, 80, 100, 120],
        'unit': '°F'
    },
    'Forecast Low Temperatures': {
        'candidates': ['minimum_temperature_height_above_ground', 'temperature_height_above_ground'],
        'colormap': 'nipy_spectral',
        'vmin': -40,
        'vmax': 120,
        'ticks': [-40, -20, 0, 20, 40, 60, 80, 100, 120],
        'unit': '°F'
    },
    'Simulated Radar (Reflectivity)': {
        'candidates': ['total_refl_3d_index_above_ground', 'composite_reflectivity_entire_atmosphere', 'reflectivity'],
        'colormap': 'metpy_NWS',  # Pulls MetPy's NWS standard radar colormap
        'vmin': 0,
        'vmax': 75,
        'ticks': [0, 15, 30, 45, 60, 75],
        'unit': 'dBZ'
    }
}

# ==========================================
# 2. Streamlit Dashboard GUI Layout
# ==========================================
st.set_page_config(page_title="Impulse Weather Map Dashboard", layout="wide")

st.sidebar.title("Map Control Panel")
st.sidebar.write("Configure your map options below without editing code.")

# Dropdowns and sliders
selected_map = st.sidebar.selectbox("Select Map Type:", list(MAP_TYPES.keys()))
selected_region = st.sidebar.selectbox("Select Geographic Region:", list(REGIONS.keys()))
selected_model = st.sidebar.selectbox("Select Numerical Model:", ["NDFD", "HRRR (2.5km)", "NAM (12km)", "GFS (0.25deg)"])
forecast_hour = st.sidebar.slider("Forecast Hour Outlook:", min_value=1, max_value=36, value=6)

# File uploader for logo
uploaded_logo = st.sidebar.file_uploader("Upload Brand Logo (Optional):", type=["png"])

# Custom manual coordinate override
with st.sidebar.expander("Custom Coordinate Bounds"):
    use_custom = st.checkbox("Override with custom coordinates")
    custom_lon_min = st.number_input("West Longitude:", value=-110.0)
    custom_lon_max = st.number_input("East Longitude:", value=-90.0)
    custom_lat_min = st.number_input("South Latitude:", value=25.0)
    custom_lat_max = st.number_input("North Latitude:", value=38.0)

# ==========================================
# 3. Dynamic Map Generator Logic
# ==========================================
def get_dynamic_model_data(model, map_type, region_info, f_hour):
    """
    Dynamically queries THREDDS to find the requested model, extracts 
    the active variable (e.g. reflectivity vs low temp), crops to the 
    user-selected bounding box, and slices at the selected forecast hour.
    """
    import xarray as xr
    import metpy
    
    # Establish bounding coordinates
    if use_custom:
        bbox_lon = [custom_lon_min, custom_lon_max]
        bbox_lat = [custom_lat_min, custom_lat_max]
    else:
        bbox_lon = [region_info['extent'][0], region_info['extent'][1]]
        bbox_lat = [region_info['extent'][2], region_info['extent'][3]]
        
    # Map model selection to THREDDS URLs
    model_urls = {
        "NDFD": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NDFD/NWS/CONUS/CONDUIT/Best",
        "HRRR (2.5km)": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/HRRR/CONUS_2p5km/Best",
        "NAM (12km)": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NAM/CONUS_12km/Best",
        "GFS (0.25deg)": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/GFS/Global_0p25deg/Best"
    }
    url = model_urls[model]
    
    # Open OPeNDAP dataset
    ds = xr.open_dataset(url)
    
    # Find active variable matching map type candidates
    temp_var = None
    candidates = MAP_TYPES[map_type]['candidates']
    for candidate in candidates:
        for v in ds.variables:
            if candidate in v.lower():
                temp_var = v
                break
        if temp_var is not None:
            break
            
    if temp_var is None:
        raise ValueError(f"Variable for '{map_type}' is not currently available on the active model server.")
        
    # Coordinate extraction and spatial cropping
    ds = ds.metpy.parse_cf()
    temp_dims = ds[temp_var].dims
    is_projected = 'x' in temp_dims and 'y' in temp_dims
    
    # Identify latitude/longitude coordinate variables
    lat_var, lon_var = None, None
    for v in ds.variables:
        v_lower = v.lower()
        if v_lower in ['latitude', 'lat']:
            lat_var = v
        elif v_lower in ['longitude', 'lon']:
            lon_var = v
            
    lat_arr = ds[lat_var].values
    lon_arr = ds[lon_var].values
    if lon_arr.max() > 180:
        if lon_arr.ndim == 1:
            lon_arr = lon_arr - 360
        else:
            lon_arr = np.where(lon_arr > 180, lon_arr - 360, lon_arr)

    # Slice spatial dimensions based on projection type
    if is_projected:
        x_dim = [d for d in temp_dims if d.lower() == 'x'][0]
        y_dim = [d for d in temp_dims if d.lower() == 'y'][0]
        data_proj = ds[temp_var].metpy.cartopy_crs
        
        transformed_corners = data_proj.transform_points(
            ccrs.PlateCarree(), np.array(bbox_lon), np.array(bbox_lat)
        )
        x_bounds = transformed_corners[:, 0]
        y_bounds = transformed_corners[:, 1]
        
        x_slice = slice(min(x_bounds), max(x_bounds))
        y_slice = slice(min(y_bounds), max(y_bounds))
        
        subset = ds[temp_var].sel(**{x_dim: x_slice, y_dim: y_slice})
        grid_lon = subset[x_dim].values
        grid_lat = subset[y_dim].values
    else:
        y_dim = ds[lat_var].dims[0]
        x_dim = ds[lon_var].dims[0]
        
        lat_indices = np.where((lat_arr >= bbox_lat[0]) & (lat_arr <= bbox_lat[1]))[0]
        lon_indices = np.where((lon_arr >= bbox_lon[0]) & (lon_arr <= bbox_lon[1]))[0]
        
        y_slice = slice(min(lat_indices), max(lat_indices) + 1)
        x_slice = slice(min(lon_indices), max(lon_indices) + 1)
        
        subset = ds[temp_var].isel(**{y_dim: y_slice, x_dim: x_slice})
        grid_lon = lon_arr[x_slice]
        grid_lat = lat_arr[y_slice]
        data_proj = ccrs.PlateCarree()
        
    # Slice temporal dimension (use selected forecast hour index)
    time_dim = [d for d in subset.dims if 'time' in d][0]
    time_idx = min(f_hour - 1, len(subset[time_dim]) - 1)
    subset_sliced = subset.isel(**{time_dim: time_idx}).squeeze().load()
    
    # Handle Units
    units = ds[temp_var].attrs.get('units', '').lower()
    sample_val = float(np.atleast_1d(subset_sliced.values).flat[0])
    if 'k' in units or sample_val > 150:
        # Convert Kelvin to Fahrenheit
        grid_data = (subset_sliced - 273.15) * 1.8 + 32
    elif 'c' in units or sample_val < 50:
        # Convert Celsius to Fahrenheit
        grid_data = subset_sliced * 1.8 + 32
    else:
        grid_data = subset_sliced
        
    return grid_lon, grid_lat, grid_data.values, data_proj

# ==========================================
# 4. Rendering and Plot Construction
# ==========================================
if st.sidebar.button("Generate Map", type="primary"):
    with st.spinner("Connecting to servers and generating map..."):
        try:
            region_info = REGIONS[selected_region]
            grid_lon, grid_lat, grid_data, data_proj = get_dynamic_model_data(
                selected_model, selected_map, region_info, forecast_hour
            )
            
            # Setup Figure
            fig = plt.figure(figsize=(19.2, 10.8), facecolor='#0d1117')
            ax_map = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            ax_map.set_facecolor('#151c24')
            ax_map.set_position([0, 0, 1, 1])
            
            # Establish Map Limits
            if use_custom:
                ax_map.set_extent([custom_lon_min, custom_lon_max, custom_lat_min, custom_lat_max], crs=ccrs.PlateCarree())
                center_lon = (custom_lon_min + custom_lon_max) / 2.0
            else:
                ax_map.set_extent(region_info['extent'], crs=ccrs.PlateCarree())
                center_lon = region_info['center_lon']
                
            # Configure Variable-Specific Color Tables
            map_config = MAP_TYPES[selected_map]
            vmin, vmax = map_config['vmin'], map_config['vmax']
            norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
            
            # Map standard color tables or MetPy custom tables
            if map_config['colormap'] == 'metpy_NWS':
                from metpy.plots import colortables
                custom_cmap = colortables.get_colortable('NWSReflectivity')
            else:
                # Custom ColorBrewer Spectral_r with Sky Blue transitions for temperatures
                color_points = [
                    (-40, '#ff00ff'), (-30, '#8b008b'), (-20, '#4b0082'), (-10, '#00008b'),
                    (0,   '#0033cc'), (10,  '#0077ff'), (20,  '#00aaff'), (32,  '#00ccd6'),
                    (40,  '#4eb38a'), (50,  '#2ca25f'), (60,  '#addd8e'), (70,  '#fec44f'),
                    (80,  '#fe9929'), (90,  '#cc1111'), (100, '#660011'), (110, '#d47a85'), (120, '#999999')
                ]
                color_list = [( (val + 40.0) / 160.0, color ) for val, color in color_points]
                custom_cmap = mcolors.LinearSegmentedColormap.from_list('impulse_scale', color_list)
                
            # Plot Contour Gradients
            levels = np.linspace(vmin, vmax, 161)
            cf = ax_map.contourf(grid_lon, grid_lat, grid_data, levels=levels, cmap=custom_cmap, norm=norm,
                                 transform=data_proj, extend='both', zorder=1)
            
            # Draw Counties and Borders
            try:
                counties_shp = shapereader.natural_earth(resolution='10m', category='cultural', name='admin_2_counties')
                counties_reader = shapereader.Reader(counties_shp)
                counties_feature = cfeature.ShapelyFeature(counties_reader.geometries(), ccrs.PlateCarree())
                ax_map.add_feature(counties_feature, facecolor='none', edgecolor='white', linewidth=0.45, alpha=0.35, zorder=2)
            except:
                pass
                
            # Draw Background Negative Mask for Selected State if requested
            if not use_custom and region_info['state_name'] is not None:
                states_shp = shapereader.natural_earth(resolution='50m', category='cultural', name='admin_1_states_provinces')
                reader = shapereader.Reader(states_shp)
                state_geom = None
                for record in reader.records():
                    if record.attributes['name'] == region_info['state_name']:
                        state_geom = record.geometry
                        break
                if state_geom is not None:
                    from shapely.geometry import box
                    map_box = box(-130, 15, -60, 50)
                    state_negative_mask = map_box.difference(state_geom)
                    ax_map.add_geometries([state_negative_mask], crs=ccrs.PlateCarree(), facecolor='#151c24', edgecolor='none', zorder=3)
                    ax_map.add_geometries([state_geom], crs=ccrs.PlateCarree(), facecolor='none', edgecolor='white', linewidth=1.5, zorder=5)
                    
            ax_map.add_feature(cfeature.STATES.with_scale('50m'), facecolor='none', edgecolor='white', linewidth=0.5, alpha=0.2, zorder=4)
            ax_map.add_feature(cfeature.BORDERS.with_scale('50m'), facecolor='none', edgecolor='white', linewidth=0.5, alpha=0.2, zorder=4)
            
            # Hide borders
            for spine in ax_map.spines.values():
                spine.set_visible(False)
                
            # ------------------------------------------
            # DYNAMIC HUD HEADER (TOP LEFT)
            # ------------------------------------------
            ax_header_card = fig.add_axes([0.105, 0.82, 0.45, 0.14])
            ax_header_card.axis('off')
            
            # Reconstruct Circular Badge
            logo_drawn = False
            if uploaded_logo is not None:
                try:
                    from PIL import Image
                    img = Image.open(uploaded_logo)
                    width, height = img.size
                    left, top, right, bottom = int(width * 0.10), int(height * 0.20), int(width * 0.90), int(height * 0.80)
                    cropped_img = img.crop((left, top, right, bottom))
                    
                    ax_logo = fig.add_axes([0.02, 0.825, 0.065, 0.11555], facecolor='none')
                    ax_logo.axis('off')
                    ax_logo.set_aspect('equal')
                    ax_logo.set_xlim(0, 1)
                    ax_logo.set_ylim(0, 1)
                    
                    circle = Circle((0.5, 0.5), 0.46, facecolor='#020617', edgecolor='white', linewidth=2.5, transform=ax_logo.transAxes, zorder=1)
                    ax_logo.add_patch(circle)
                    
                    img_w, img_h = cropped_img.size
                    aspect = img_w / img_h
                    x_start, x_end, y_start, y_end = (0.0, 1.0, (1.0 - 1.0/aspect)/2.0, (1.0 + 1.0/aspect)/2.0) if aspect > 1.0 else ((1.0 - aspect)/2.0, (1.0 + aspect)/2.0, 0.0, 1.0)
                    
                    im = ax_logo.imshow(cropped_img, extent=[x_start, x_end, y_start, y_end], aspect='equal', zorder=2)
                    clip_circle = Circle((0.5, 0.5), 0.44, transform=ax_logo.transAxes)
                    im.set_clip_path(clip_circle)
                    logo_drawn = True
                except Exception as e:
                    st.sidebar.error(f"Error rendering logo: {e}")
                    
            title_x = 0.01
            capsule_x = 0.01
            path_effects = [withStroke(linewidth=3, foreground='#151c24')]
            
            # Render Text overlays with shadows
            ax_header_card.text(title_x + 0.003, 0.64 - 0.015, selected_map, color='black', alpha=0.6, fontsize=36, fontweight='bold', va='center')
            ax_header_card.text(title_x, 0.64, selected_map, color='white', fontsize=36, fontweight='bold', va='center')
            
            # Forecast Day / Hour pill
            forecast_time = (datetime.datetime.now() + datetime.timedelta(hours=int(forecast_hour))).strftime("%A %I:%M %p").upper()
            ax_header_card.text(capsule_x, 0.35, f" {selected_model.upper()} MODEL - OUTLOOK FOR {forecast_time} ", color='white', fontsize=20, 
                                fontweight='bold', va='center', bbox=dict(boxstyle="round,pad=0.35", fc="#020617", ec="none"))
            
            # ------------------------------------------
            # HORIZONTAL COLORBAR (TOP RIGHT)
            # ------------------------------------------
            cax = fig.add_axes([0.60, 0.89, 0.36, 0.015])
            cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=custom_cmap), cax=cax, orientation='horizontal')
            
            fig.text(0.58, 0.897, map_config['unit'], color='white', fontsize=12, fontweight='bold', va='center', ha='right', path_effects=path_effects)
            cb.ax.tick_params(labelsize=10, colors='white', labelbottom=True)
            cb.set_ticks(map_config['ticks'])
            
            for label in cb.ax.get_xticklabels():
                label.set_path_effects(path_effects)
            cb.outline.set_visible(False)
            
            # Save and Render in Streamlit
            output_path = "texas_forecast_highs.png"
            plt.savefig(output_path, dpi=100)
            plt.close()
            
            st.image(output_path, use_container_width=True)
            
            # Provide Free Download Button
            with open(output_path, "rb") as file:
                st.download_button(
                    label="Download High-Resolution Map PNG",
                    data=file,
                    file_name="forecast_map_1080p.png",
                    mime="image/png"
                )
        except Exception as e:
            st.error(f"Failed to generate map: {e}")
