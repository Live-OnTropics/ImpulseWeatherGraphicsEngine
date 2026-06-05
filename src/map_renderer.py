# src/map_renderer.py
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
from src.config import TEMP_COLOR_POINTS, TEMP_COLORBAR_TICKS, RAIN_COLOR_POINTS, RAIN_COLORBAR_TICKS, TEMP_VMIN, TEMP_VMAX, RAIN_VMIN, RAIN_VMAX, MAP_LABELS_REDUCED

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


def render_texas_map(grid_lon, grid_lat, grid_temp, map_label_temps, model_name, data_proj, map_type, forecast_setting_str, uploaded_logo_file=None):
    """Renders the 1080p canvas with coordinate dimensions, fonts, and clean HUD overlays."""
    font_family = setup_fonts()
    
    fig = plt.figure(figsize=(19.2, 10.8), facecolor='#0d1117')
    
    # ------------------------------------------
    # FULL BLEED MAP
    # ------------------------------------------
    ax_map = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax_map.set_facecolor('#151c24')
    ax_map.set_position([0, 0, 1, 1])
    ax_map.set_extent([-112.44, -87.56, 24.0, 38.0], crs=ccrs.PlateCarree())
    
    # Map Type scale definitions
    is_rain = "Rain" in map_type
    
    if is_rain:
        vmin, vmax = RAIN_VMIN, RAIN_VMAX
        # Custom rain colormap with opacity gradient matching input_file_8
        rgba_list = []
        for val, hex_color, alpha in RAIN_COLOR_POINTS:
            pos = val / 18.0
            rgb = mcolors.to_rgb(hex_color)
            rgba = (rgb[0], rgb[1], rgb[2], alpha)
            rgba_list.append((pos, rgba))
        custom_cmap = mcolors.LinearSegmentedColormap.from_list('impulse_rain_scale', rgba_list)
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        ticks = RAIN_COLORBAR_TICKS
        unit_label = "inches"
        val_suffix = '"'
    else:
        vmin, vmax = TEMP_VMIN, TEMP_VMAX
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        color_list = [( (val + 40.0) / 160.0, color ) for val, color in TEMP_COLOR_POINTS]
        custom_cmap = mcolors.LinearSegmentedColormap.from_list('impulse_temp_scale', color_list)
        ticks = TEMP_COLORBAR_TICKS
        unit_label = "°F"
        val_suffix = "°"
        
    levels = np.linspace(vmin, vmax, 161)
    cf = ax_map.contourf(grid_lon, grid_lat, grid_temp, levels=levels, cmap=custom_cmap, norm=norm,
                         transform=data_proj, extend='both', zorder=1)
    
    # County outlines (linewidth and alpha increased for prominent visibility)
    try:
        counties_shp = shapereader.natural_earth(resolution='10m', category='cultural', name='admin_2_counties')
        counties_reader = shapereader.Reader(counties_shp)
        counties_feature = cfeature.ShapelyFeature(counties_reader.geometries(), ccrs.PlateCarree())
        ax_map.add_feature(counties_feature, facecolor='none', edgecolor='white', linewidth=0.45, alpha=0.35, zorder=2)
    except:
        pass
    
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
        
        ax_map.add_geometries([tx_negative_mask], crs=ccrs.PlateCarree(), facecolor='#151c24', edgecolor='none', zorder=3)
        ax_map.add_geometries([tx_geom], crs=ccrs.PlateCarree(), facecolor='none', edgecolor='white', linewidth=1.5, zorder=5)
        
    ax_map.add_feature(cfeature.STATES.with_scale('50m'), facecolor='none', edgecolor='white', linewidth=0.5, alpha=0.2, zorder=4)
    ax_map.add_feature(cfeature.BORDERS.with_scale('50m'), facecolor='none', edgecolor='white', linewidth=0.5, alpha=0.2, zorder=4)
    
    # ------------------------------------------
    # MAP STATION LABELS RENDERING
    # ------------------------------------------
    shadow_offset_lon = 0.04
    shadow_offset_lat = -0.04
    path_effects = [withStroke(linewidth=3, foreground='#151c24')]
    
    for city, (lat, lon) in MAP_LABELS_REDUCED.items():
        temp_val = map_label_temps.get(city)
        if temp_val is None:
            continue
        
        # Temperature Text Drop Shadow (offset black text layer)
        ax_map.text(lon + shadow_offset_lon, lat + 0.22 + shadow_offset_lat, f"{temp_val}{val_suffix}", color='black', alpha=0.5,
                    fontsize=48, fontweight='bold', family=font_family,
                    ha='center', va='center', transform=ccrs.PlateCarree(), zorder=6)
        
        # Temperature Text Main Layer (white, 48pt)
        ax_map.text(lon, lat + 0.22, f"{temp_val}{val_suffix}", color='white',
                    fontsize=48, fontweight='bold', family=font_family,
                    ha='center', va='center', transform=ccrs.PlateCarree(), zorder=7)
        
        # City Label Pill (colored #020617, 22pt & shifted down to -0.32)
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
    ax_header_card.patch.set_facecolor('none')  # Corrected: 100% transparent header card background
    
    # Reconstructed Blue Circle Badge with White Outline (No Stretching)
    logo_drawn = False
    active_logo_source = None
    if uploaded_logo_file is not None:
        active_logo_source = uploaded_logo_file
    elif os.path.exists("ImpulseWXLogo.png"):
        active_logo_source = "ImpulseWXLogo.png"
        
    if active_logo_source is not None:
        try:
            from PIL import Image
            img = Image.open(active_logo_source)
            width, height = img.size
            # Reduced horizontal crop to preserve badge dimensions
            left, top, right, bottom = int(width * 0.10), int(height * 0.20), int(width * 0.90), int(height * 0.80)
            cropped_img = img.crop((left, top, right, bottom))
            
            # Sub-axes for the circular logo badge (exact square coordinates, made 13% smaller)
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
            
            # Safe 0.65 scale constraint to fit logo comfortably inside badge circle boundaries
            scale = 0.65
            if aspect > 1.0:
                x_w = scale
                x_start = 0.5 - x_w / 2.0
                x_end = 0.5 + x_w / 2.0
                y_h = scale / aspect
                y_start = 0.5 - y_h / 2.0
                y_end = 0.5 + y_h / 2.0
            else:
                y_h = scale
                y_start = 0.5 - y_h / 2.0
                y_end = 0.5 + y_h / 2.0
                x_w = scale * aspect
                x_start = 0.5 - x_w / 2.0
                x_end = 0.5 + x_w / 2.0
                
            im = ax_logo.imshow(cropped_img, extent=[x_start, x_end, y_start, y_end], aspect='equal', zorder=2)
            clip_circle = Circle((0.5, 0.5), 0.44, transform=ax_logo.transAxes)
            im.set_clip_path(clip_circle)
            logo_drawn = True
        except Exception as e:
            print(f"Could not load or crop logo: {e}")
            
    title_x = 0.01
    capsule_x = 0.01
    
    # Drop shadow text for the headline title (shifted down to 0.64)
    ax_header_card.text(title_x + 0.003, 0.64 - 0.015, map_type, color='black', alpha=0.6,
                        fontsize=36, fontweight='bold', family=font_family, va='center')
    ax_header_card.text(title_x, 0.64, map_type, color='white', 
                        fontsize=36, fontweight='bold', family=font_family, va='center')
    
    # Pill shaped model subtitle capsule colored #020617 with no outline (raised to 0.35)
    ax_header_card.text(capsule_x, 0.35, f" {model_name.upper()} MODEL - {forecast_setting_str} OUTLOOK ", color='white', fontsize=20, 
                        fontweight='bold', family=font_family, va='center',
                        bbox=dict(boxstyle="round,pad=0.35", fc="#020617", ec="none"))

    # ------------------------------------------
    # CLEAN HORIZONTAL COLORBAR (TOP RIGHT)
    # ------------------------------------------
    # Horizontal colorbar extending from top middle (0.60) to top right (0.96), leaving a slight gap at the end (1.00)
    cax = fig.add_axes([0.60, 0.89, 0.36, 0.015])
    cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=custom_cmap), cax=cax, orientation='horizontal')
    
    # Scale labels with offset drop shadow
    fig.text(0.58, 0.897, unit_label, color='white', fontsize=12, fontweight='bold', family=font_family, va='center', ha='right', path_effects=path_effects)
    cb.ax.tick_params(labelsize=10, colors='white', labelbottom=True)
    cb.set_ticks(ticks)
    
    # Overlay black outlines on scale ticks for maximum legibility over heat contours
    for label in cb.ax.get_xticklabels():
        label.set_path_effects(path_effects)
        label.set_family(font_family)
        
    cb.outline.set_visible(False)
    
    return fig
