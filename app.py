import os
import datetime
import urllib.request
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Circle
from matplotlib.patheffects import withStroke
from matplotlib import font_manager
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.io import shapereader
from scipy.interpolate import griddata

# Detect if we are running inside a Streamlit Web environment
try:
    import streamlit as st
    import streamlit.runtime as st_runtime
    is_streamlit = st_runtime.exists()
except ImportError:
    is_streamlit = False

# ==========================================
# 1. Robust Font Setup (Space Grotesk)
# ==========================================
def setup_fonts():
    """Downloads Space Grotesk from updated repositories and registers it with matplotlib."""
    font_name = 'Space Grotesk'
    font_files = {
        'SpaceGrotesk-Regular.ttf': [
            'https://raw.githubusercontent.com/floriankarsten/space-grotesk/master/fonts/ttf/static/SpaceGrotesk-Regular.ttf',
            'https://raw.githubusercontent.com/lvgl/lvgl/master/demos/smartwatch/assets/SpaceGrotesk-Regular.ttf'
        ],
        'SpaceGrotesk-Bold.ttf': [
            'https://raw.githubusercontent.com/floriankarsten/space-grotesk/master/fonts/ttf/static/SpaceGrotesk-Bold.ttf',
            'https://raw.githubusercontent.com/lvgl/lvgl/master/demos/smartwatch/assets/SpaceGrotesk-Bold.ttf'
        ]
    }
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for filename, urls in font_files.items():
        if not os.path.exists(filename):
            downloaded = False
            for url in urls:
                try:
                    print(f"Downloading {filename} from {url}...")
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req) as response, open(filename, 'wb') as out_file:
                        out_file.write(response.read())
                    print(f"Successfully downloaded {filename}.")
                    downloaded = True
                    break
                except Exception as e:
                    print(f"Mirror failed ({url}): {e}")
            if not downloaded:
                print(f"Could not download {filename} from any mirror. Defaulting to system sans-serif.")
                
        if os.path.exists(filename):
            try:
                font_manager.fontManager.addfont(filename)
            except Exception as e:
                print(f"Error registering font {filename}: {e}")

    # Verify if registered successfully
    available_fonts = [f.name for f in font_manager.fontManager.ttflist]
    return font_name if font_name in available_fonts else 'sans-serif'


# ==========================================
# 2. Curated 10-City Grid
# ==========================================
MAP_LABELS_REDUCED = {
    'AMARILLO': (35.2219, -101.8313, 80),
    'ODESSA-MIDLAND': (31.9973, -102.0779, 84),  # Combined Odessa-Midland hub
    'EL PASO': (31.7619, -106.4850, 91),
    'DEL RIO': (29.3627, -100.8968, 93),
    'WICHITA FALLS': (33.9137, -98.4934, 91),
    'DFW': (32.7767, -96.9970, 91),
    'AUSTIN': (30.2672, -97.7431, 91),
    'HOUSTON': (29.7604, -95.3698, 86),
    'CORPUS CHRISTI': (27.8003, -97.3964, 84),
    'BROWNSVILLE': (25.9017, -97.4975, 91)
}


# ==========================================
# 3. Meteorological Synthetic Grid Model
# ==========================================
def get_synthetic_meteorological_grid(lon, lat):
    """
    Computes a physically-realistic continuous temperature field for Texas.
    Incorporates latitude heating, high elevation cooling (Alpine), desert heat (Presidio),
    and maritime sea-breeze mitigation near the Gulf Coast.
    """
    t_base = 94.0 - (lat - 25.0) * (18.0 / 11.5)
    dist_alpine = np.sqrt((lon - (-103.6))**2 + (lat - 30.3)**2)
    cooling_alpine = 10.0 * np.exp(-dist_alpine**2 / 1.5)
    dist_presidio = np.sqrt((lon - (-104.3))**2 + (lat - 29.5)**2)
    heat_presidio = 12.0 * np.exp(-dist_presidio**2 / 0.5)
    dist_gulf = np.sqrt((lon - (-94.0))**2 + (lat - 26.0)**2)
    cooling_gulf = 8.0 * np.exp(-dist_gulf**2 / 4.0)
    temp = t_base - cooling_alpine + heat_presidio - cooling_gulf
    temp += 1.5 * np.sin(lon / 2.0) * np.cos(lat / 2.0)
    return temp


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
    Falls back to a meteorological grid model with smooth residual adjustments to
    perfectly preserve city observations.
    """
    grid_lon, grid_lat, grid_temp = None, None, None
    map_label_temps = {k: v[2] for k, v in MAP_LABELS_REDUCED.items()}
    model_name = "Observation Fallback"
    data_proj = ccrs.PlateCarree()
    
    # Priority sequence list of Unidata THREDDS datasets
    endpoints = [
        {
            "name": "NDFD",
            "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NDFD/NWS/CONUS/CONDUIT/Best",
            "temp_candidates": [
                "maximum_temperature_height_above_ground",
                "temperature_height_above_ground"
            ]
        },
        {
            "name": "HRRR (2.5km)",
            "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/HRRR/CONUS_2p5km/Best",
            "temp_candidates": ["temperature_height_above_ground"]
        },
        {
            "name": "NAM (12km)",
            "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NAM/CONUS_12km/Best",
            "temp_candidates": ["temperature_height_above_ground"]
        },
        {
            "name": "GFS (0.25deg)",
            "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/GFS/Global_0p25deg/Best",
            "temp_candidates": ["temperature_height_above_ground"]
        }
    ]
    
    # If a specific model is forced from Streamlit sidebar, prioritize it first
    if target_model:
        endpoints = [ep for ep in endpoints if target_model in ep["name"]] + [ep for ep in endpoints if target_model not in ep["name"]]
        
    has_xr = False
    try:
        import xarray as xr
        import metpy
        has_xr = True
    except ImportError:
        print("xarray or metpy is not installed. Falling back directly to the blended meteorological model.")
        
    if has_xr:
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
                
                if is_projected:
                    # Projected Grid (NAM, HRRR, NDFD)
                    x_dim = [d for d in temp_dims if d.lower() == 'x'][0]
                    y_dim = [d for d in temp_dims if d.lower() == 'y'][0]
                    
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
                
                # Match values to stations
                for city, (lat, lon, _) in MAP_LABELS_REDUCED.items():
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
                
    # Final fallback to synthetic blending
    print("\nAll live THREDDS endpoints failed or xarray is missing.")
    print("Blending physical meteorological baseline with target observations...")
    
    lons = np.linspace(-112.44, -87.56, 300)
    lats = np.linspace(24.0, 38.0, 300)
    grid_lon, grid_lat = np.meshgrid(lons, lats)
    
    grid_synthetic = get_synthetic_meteorological_grid(grid_lon, grid_lat)
    
    points = []
    residuals = []
    for city, (lat, lon, target) in MAP_LABELS_REDUCED.items():
        points.append([lon, lat])
        synth_val = get_synthetic_meteorological_grid(lon, lat)
        residuals.append(target - synth_val)
        
    grid_res = griddata(points, residuals, (grid_lon, grid_lat), method='cubic')
    grid_res_nearest = griddata(points, residuals, (grid_lon, grid_lat), method='nearest')
    grid_res = np.where(np.isnan(grid_res), grid_res_nearest, grid_res)
    
    grid_temp = grid_synthetic + grid_res
    model_name = "Observation Fallback"
    data_proj = ccrs.PlateCarree()
    
    return grid_lon, grid_lat, grid_temp, map_label_temps, model_name, data_proj


# ==========================================
# 4. Map Generation & Styling
# ==========================================
def generate_map(target_model=None, uploaded_logo_file=None):
    font_family = setup_fonts()
    grid_lon, grid_lat, grid_temp, map_label_temps, model_name, data_proj = get_model_data(target_model)
    
    # 1920x1080 canvas
    fig = plt.figure(figsize=(19.2, 10.8), facecolor='#0d1117')
    
    # ------------------------------------------
    # FULL BLEED MAP
    # ------------------------------------------
    ax_map = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax_map.set_facecolor('#151c24')
    
    # Exact 16:9 aspect ratio bounding coordinates preventing gaps or stretching
    ax_map.set_position([0, 0, 1, 1])
    ax_map.set_extent([-112.44, -87.56, 24.0, 38.0], crs=ccrs.PlateCarree())
    
    # Custom color table definitions (Replicating input_file_5 with custom neon-sky blue)
    vmin = -40
    vmax = 120
    
    color_points = [
        (-40, '#ff00ff'),  # Magenta
        (-30, '#8b008b'),  # Dark Magenta / Purple
        (-20, '#4b0082'),  # Indigo
        (-10, '#00008b'),  # Dark Blue
        (0,   '#0033cc'),  # Pure Blue
        (10,  '#0077ff'),  # Light Blue
        (20,  '#00aaff'),  # Neon Sky Blue (not too bright)
        (32,  '#00ccd6'),  # Deep Cyan/Sky Blue
        (40,  '#4eb38a'),  # Minty Green
        (50,  '#2ca25f'),  # Medium Green
        (60,  '#addd8e'),  # Lime Yellow-Green
        (70,  '#fec44f'),  # Yellow-Orange
        (80,  '#fe9929'),  # Bright Orange
        (90,  '#cc1111'),  # Pure Red
        (100, '#660011'),  # Dark Red
        (110, '#d47a85'),  # Dusty Rose
        (120, '#999999'),  # Grey
    ]
    color_list = []
    for val, color in color_points:
        pos = (val + 40.0) / 160.0
        color_list.append((pos, color))
    custom_cmap = mcolors.LinearSegmentedColormap.from_list('impulse_temp_scale', color_list)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    
    levels = np.linspace(vmin, vmax, 161)
    cf = ax_map.contourf(grid_lon, grid_lat, grid_temp, levels=levels, cmap=custom_cmap, norm=norm,
                         transform=data_proj, extend='both', zorder=1)
    
    # County outlines (linewidth and alpha increased for prominent visibility)
    try:
        counties_shp = shapereader.natural_earth(resolution='10m', category='cultural', name='admin_2_counties')
        counties_reader = shapereader.Reader(counties_shp)
        counties_feature = cfeature.ShapelyFeature(counties_reader.geometries(), ccrs.PlateCarree())
        ax_map.add_feature(counties_feature, facecolor='none', edgecolor='white', linewidth=0.45, alpha=0.35, zorder=2)
    except Exception as e:
        print(f"Could not load county outlines using standard Cartopy reader: {e}")
    
    states_shp = shapereader.natural_earth(resolution='50m', category='cultural', name='admin_1_states_provinces')
    reader = shapereader.Reader(states_shp)
    tx_geom = None
    for record in reader.records():
        if record.attributes['name'] == 'Texas':
            tx_geom = record.geometry
            break
            
    if tx_geom is not None:
        from shapely.geometry import box
        map_box = box(-115, 20, -85, 45)
        tx_negative_mask = map_box.difference(tx_geom)
        
        ax_map.add_geometries([tx_negative_mask], crs=ccrs.PlateCarree(), 
                               facecolor='#151c24', edgecolor='none', zorder=3)
        
        ax_map.add_geometries([tx_geom], crs=ccrs.PlateCarree(), 
                               facecolor='none', edgecolor='white', linewidth=1.5, zorder=5)
        
    ax_map.add_feature(cfeature.STATES.with_scale('50m'), facecolor='none', edgecolor='white', linewidth=0.5, alpha=0.2, zorder=4)
    ax_map.add_feature(cfeature.BORDERS.with_scale('50m'), facecolor='none', edgecolor='white', linewidth=0.5, alpha=0.2, zorder=4)
    
    # ------------------------------------------
    # MAP STATION LABELS RENDERING
    # ------------------------------------------
    shadow_offset_lon = 0.04
    shadow_offset_lat = -0.04
    path_effects = [withStroke(linewidth=3, foreground='#151c24')]
    
    for city, (lat, lon, _) in MAP_LABELS_REDUCED.items():
        temp_val = map_label_temps.get(city, 90)
        
        # Temperature Text Drop Shadow (offset black text layer)
        ax_map.text(lon + shadow_offset_lon, lat + 0.22 + shadow_offset_lat, f"{temp_val}°", color='black', alpha=0.5,
                    fontsize=48, fontweight='bold', family=font_family,
                    ha='center', va='center', transform=ccrs.PlateCarree(), zorder=6)
        
        # Temperature Text Main Layer (white, slightly reduced to 48pt)
        ax_map.text(lon, lat + 0.22, f"{temp_val}°", color='white',
                    fontsize=48, fontweight='bold', family=font_family,
                    ha='center', va='center', transform=ccrs.PlateCarree(), zorder=7)
        
        # City Label Pill (colored #020617, slightly reduced to 22pt & shifted down to -0.32)
        ax_map.text(lon, lat - 0.32, city, color='white', fontsize=22, fontweight='bold',
                    ha='center', va='center', transform=ccrs.PlateCarree(), family=font_family, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.22", fc="#020617", ec="none"))
        
    for spine in ax_map.spines.values():
        spine.set_visible(False)
        
    # ------------------------------------------
    # CLEAN FLOATING HUD HEADER (TOP LEFT)
    # ------------------------------------------
    ax_header_card = fig.add_axes([0.105, 0.82, 0.45, 0.14])
    ax_header_card.axis('off')
    
    # Reconstructed Blue Circle Badge with White Outline (No Stretching)
    logo_drawn = False
    
    # Check for direct Streamlit web upload first, then fallback to local path
    active_logo_source = None
    if uploaded_logo_file is not None:
        active_logo_source = uploaded_logo_file
    elif os.path.exists("ImpulseWXLogo.png"):
        active_logo_source = "ImpulseWXLogo.png"
        
    if active_logo_source is not None:
        try:
            from PIL import Image
            from matplotlib.patches import Circle
            img = Image.open(active_logo_source)
            width, height = img.size
            # Reduced horizontal crop to preserve badge dimensions
            left = int(width * 0.10)
            top = int(height * 0.20)
            right = int(width * 0.90)
            bottom = int(height * 0.80)
            cropped_img = img.crop((left, top, right, bottom))
            
            # Sub-axes for the circular logo badge (perfect 1:1 aspect square coordinates)
            ax_logo = fig.add_axes([0.02, 0.825, 0.065, 0.11555], facecolor='none')
            ax_logo.axis('off')
            ax_logo.set_aspect('equal')
            ax_logo.set_xlim(0, 1)
            ax_logo.set_ylim(0, 1)
            
            # Backing badge circle colored #020617 with white outline
            circle = Circle((0.5, 0.5), 0.46, facecolor='#020617', edgecolor='white', linewidth=2.5, transform=ax_logo.transAxes, zorder=1)
            ax_logo.add_patch(circle)
            
            # Draw logo inside axes and clip to a perfect circular mask to prevent stretching
            img_w, img_h = cropped_img.size
            aspect = img_w / img_h
            if aspect > 1.0:
                x_start, x_end = 0.0, 1.0
                y_h = 1.0 / aspect
                y_start = (1.0 - y_h) / 2.0
                y_end = y_start + y_h
            else:
                y_start, y_end = 0.0, 1.0
                x_w = aspect
                x_start = (1.0 - x_w) / 2.0
                x_end = x_start + x_w
                
            im = ax_logo.imshow(cropped_img, extent=[x_start, x_end, y_start, y_end], aspect='equal', zorder=2)
            clip_circle = Circle((0.5, 0.5), 0.44, transform=ax_logo.transAxes)
            im.set_clip_path(clip_circle)
            logo_drawn = True
        except Exception as e:
            print(f"Could not load or crop logo: {e}")
            
    title_x = 0.01
    capsule_x = 0.01
    
    # Drop shadow text for the headline title (shifted down to 0.64)
    ax_header_card.text(title_x + 0.003, 0.64 - 0.015, "Statewide Forecast", color='black', alpha=0.6,
                        fontsize=36, fontweight='bold', family=font_family, va='center')
    ax_header_card.text(title_x, 0.64, "Statewide Forecast", color='white', 
                        fontsize=36, fontweight='bold', family=font_family, va='center')
    
    # Pill shaped model subtitle capsule colored #020617 with no outline (raised to 0.35)
    forecast_day = datetime.date.today().strftime("%A").upper()
    ax_header_card.text(capsule_x, 0.35, f" {model_name.upper()} MODEL - {forecast_day} OUTLOOK ", color='white', fontsize=20, 
                        fontweight='bold', family=font_family, va='center',
                        bbox=dict(boxstyle="round,pad=0.35", fc="#020617", ec="none"))

    # ------------------------------------------
    # CLEAN HORIZONTAL COLORBAR (TOP RIGHT)
    # ------------------------------------------
    # Horizontal colorbar extending from top middle (0.60) to top right (0.96), leaving a slight gap at the end (1.00)
    cax = fig.add_axes([0.60, 0.89, 0.36, 0.015])
    cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=custom_cmap), cax=cax, orientation='horizontal')
    
    # Scale labels with offset drop shadow
    fig.text(0.58, 0.897, '°F', color='white', fontsize=12, fontweight='bold', family=font_family, va='center', ha='right', path_effects=path_effects)
    cb.ax.tick_params(labelsize=10, colors='white', labelbottom=True)
    cb.set_ticks([-40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120])
    
    # Overlay black outlines on scale ticks for maximum legibility over heat contours
    for label in cb.ax.get_xticklabels():
        label.set_path_effects(path_effects)
        label.set_family(font_family)
        
    cb.outline.set_visible(False)

    output_filename = 'texas_forecast_highs.png'
    plt.savefig(output_filename, dpi=100)
    plt.close()

# ==========================================
# 5. Execution Block (Unified Dual Mode)
# ==========================================
if __name__ == '__main__':
    if is_streamlit:
        st.title("Impulse Weather Map Dashboard")
        st.write("Configure your options on the sidebar and click **Generate Map**.")
        
        # 1. Model Selector on Streamlit Sidebar
        selected_model = st.sidebar.selectbox(
            "Select Numerical Model:",
            ["NDFD", "HRRR (2.5km)", "NAM (12km)", "GFS (0.25deg)"],
            index=3  # Default to GFS
        )
        
        # 2. Interactive Logo Uploader
        uploaded_logo = st.sidebar.file_uploader("Upload Brand Logo (Optional):", type=["png"])
        
        if st.sidebar.button("Generate Map", type="primary"):
            with st.spinner("Connecting to servers and generating map..."):
                try:
                    # Run generation
                    generate_map(target_model=selected_model, uploaded_logo_file=uploaded_logo)
                    
                    st.success("Map generated successfully!")
                    st.image("texas_forecast_highs.png", use_container_width=True)
                    
                    # Provide direct download link
                    with open("texas_forecast_highs.png", "rb") as file:
                        st.download_button(
                            label="Download High-Resolution Map",
                            data=file,
                            file_name="texas_forecast_highs.png",
                            mime="image/png"
                        )
                except Exception as e:
                    st.error(f"Failed to generate map: {e}")
    else:
        # Standard CLI local execution mode
        generate_map()
        print("Map successfully saved to texas_forecast_highs.png")
