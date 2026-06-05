# src/core/map_renderer.py
import os
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

def setup_fonts():
    os.makedirs('assets/fonts', exist_ok=True)
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
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for filename, urls in font_files.items():
        save_path = os.path.join('assets/fonts', filename)
        if not os.path.exists(save_path):
            downloaded = False
            for url in urls:
                try:
                    print(f"Downloading {filename}...")
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req) as response, open(save_path, 'wb') as out_file:
                        out_file.write(response.read())
                    downloaded = True
                    break
                except Exception as e:
                    print(f"Mirror failed ({url}): {e}")
            if not downloaded:
                print(f"Using standard fallback for {filename}.")
                
        if os.path.exists(save_path):
            try:
                font_manager.fontManager.addfont(save_path)
            except Exception as e:
                print(f"Registration error: {e}")

    available_fonts = [f.name for f in font_manager.fontManager.ttflist]
    return font_name if font_name in available_fonts else 'sans-serif'


def render_map(grid_lon, grid_lat, grid_values, map_label_values, model_name, data_proj, map_type, forecast_setting_str, run_cycle_str, product, region, uploaded_logo_file=None):
    font_family = setup_fonts()
    
    fig = plt.figure(figsize=(19.2, 10.8), facecolor='#0d1117')
    
    ax_map = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax_map.set_facecolor('#151c24')
    ax_map.set_position([0, 0, 1, 1])
    ax_map.set_extent(region.extent, crs=ccrs.PlateCarree())
    
    vmin, vmax = product.vmin, product.vmax
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    color_range = float(vmax - vmin)
    color_list = [((val - vmin) / color_range, color) for val, color in product.color_points]
    custom_cmap = mcolors.LinearSegmentedColormap.from_list('impulse_product_scale', color_list)
    ticks = product.colormap_ticks
    unit_label = product.unit_label
    val_suffix = product.val_suffix
        
    levels = np.linspace(vmin, vmax, 161)
    cf = ax_map.contourf(grid_lon, grid_lat, grid_values, levels=levels, cmap=custom_cmap, norm=norm,
                         transform=data_proj, extend='both', zorder=1)
    
    try:
        counties_shp = shapereader.natural_earth(resolution='10m', category='cultural', name='admin_2_counties')
        counties_reader = shapereader.Reader(counties_shp)
        counties_feature = cfeature.ShapelyFeature(counties_reader.geometries(), ccrs.PlateCarree())
        ax_map.add_feature(counties_feature, facecolor='none', edgecolor='white', linewidth=0.45, alpha=0.35, zorder=2)
    except:
        pass
    
    # Regional clipping configurations
    if hasattr(region, 'mask_state') and region.mask_state is not None:
        try:
            states_shp = shapereader.natural_earth(resolution='50m', category='cultural', name='admin_1_states_provinces')
            reader = shapereader.Reader(states_shp)
            state_geom = None
            for record in reader.records():
                if record.attributes['name'] == region.mask_state:
                    state_geom = record.geometry
                    break
                    
            if state_geom is not None:
                from shapely.geometry import box
                map_box = box(region.extent[0]-3, region.extent[2]-3, region.extent[1]+3, region.extent[3]+3)
                state_negative_mask = map_box.difference(state_geom)
                
                ax_map.add_geometries([state_negative_mask], crs=ccrs.PlateCarree(), facecolor='#151c24', edgecolor='none', zorder=3)
                ax_map.add_geometries([state_geom], crs=ccrs.PlateCarree(), facecolor='none', edgecolor='white', linewidth=1.5, zorder=5)
        except Exception as ex:
            print(f"Skipping geometry mask operations: {ex}")
    else:
        # If no mask is applied, still draw a crisp, bold border around Texas to preserve regional focus
        try:
            states_shp = shapereader.natural_earth(resolution='50m', category='cultural', name='admin_1_states_provinces')
            reader = shapereader.Reader(states_shp)
            tx_geom = None
            for record in reader.records():
                if record.attributes['name'] == 'Texas':
                    tx_geom = record.geometry
                    break
            if tx_geom is not None:
                ax_map.add_geometries([tx_geom], crs=ccrs.PlateCarree(), facecolor='none', edgecolor='white', linewidth=1.5, zorder=5)
        except Exception as ex:
            print(f"Skipping Texas highlight border: {ex}")
            
    ax_map.add_feature(cfeature.STATES.with_scale('50m'), facecolor='none', edgecolor='white', linewidth=0.5, alpha=0.2, zorder=4)
    ax_map.add_feature(cfeature.BORDERS.with_scale('50m'), facecolor='none', edgecolor='white', linewidth=0.5, alpha=0.2, zorder=4)
    
    # Dynamic offsets (scaled proportionally to the region's dimensional span)
    lon_span = region.extent[1] - region.extent[0]
    lat_span = region.extent[3] - region.extent[2]
    
    temp_offset = lat_span * 0.016
    city_offset = -lat_span * 0.023
    
    shadow_offset_lon = lon_span * 0.0016
    shadow_offset_lat = -lat_span * 0.0028
    path_effects = [withStroke(linewidth=3, foreground='#151c24')]
    
    for city, (lat, lon) in region.cities.items():
        val = map_label_values.get(city)
        if val is None:
            continue
        
        # Temperature Text Drop Shadow
        ax_map.text(lon + shadow_offset_lon, lat + temp_offset + shadow_offset_lat, f"{val}{val_suffix}", color='black', alpha=0.5,
                    fontsize=48, fontweight='bold', family=font_family,
                    ha='center', va='center', transform=ccrs.PlateCarree(), zorder=6)
        
        # Temperature Text Main Layer
        ax_map.text(lon, lat + temp_offset, f"{val}{val_suffix}", color='white',
                    fontsize=48, fontweight='bold', family=font_family,
                    ha='center', va='center', transform=ccrs.PlateCarree(), zorder=7)
        
        # City Label Pill (centered cleanly below temperature metrics)
        ax_map.text(lon, lat + city_offset, city, color='white', fontsize=22, fontweight='bold',
                    ha='center', va='center', transform=ccrs.PlateCarree(), family=font_family, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.22", fc="#020617", ec="none"))
        
    for spine in ax_map.spines.values():
        spine.set_visible(False)
        
    # Floating header HUD (top-left)
    ax_header_card = fig.add_axes([0.105, 0.82, 0.45, 0.14])
    ax_header_card.axis('off')
    ax_header_card.patch.set_facecolor('none')
    
    active_logo_source = None
    if uploaded_logo_file is not None:
        active_logo_source = uploaded_logo_file
    elif os.path.exists("assets/logos/ImpulseWXLogo.png"):
        active_logo_source = "assets/logos/ImpulseWXLogo.png"
        
    if active_logo_source is not None:
        try:
            from PIL import Image
            img = Image.open(active_logo_source)
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
        except Exception as e:
            print(f"Could not render custom logo frame: {e}")
            
    title_x = 0.01
    capsule_x = 0.01
    
    ax_header_card.text(title_x + 0.003, 0.64 - 0.015, map_type, color='black', alpha=0.6,
                        fontsize=36, fontweight='bold', family=font_family, va='center')
    ax_header_card.text(title_x, 0.64, map_type, color='white', 
                        fontsize=36, fontweight='bold', family=font_family, va='center')
    
    ax_header_card.text(capsule_x, 0.35, f" {model_name.upper()}{run_cycle_str} - {forecast_setting_str} OUTLOOK ", color='white', fontsize=20, 
                        fontweight='bold', family=font_family, va='center',
                        bbox=dict(boxstyle="round,pad=0.35", fc="#020617", ec="none"))

    # Floating Colorbar (top-right)
    cax = fig.add_axes([0.60, 0.89, 0.36, 0.015])
    cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=custom_cmap), cax=cax, orientation='horizontal')
    
    fig.text(0.58, 0.897, unit_label, color='white', fontsize=12, fontweight='bold', family=font_family, va='center', ha='right', path_effects=path_effects)
    cb.ax.tick_params(labelsize=10, colors='white', labelbottom=True)
    cb.set_ticks(ticks)
    
    for label in cb.ax.get_xticklabels():
        label.set_path_effects(path_effects)
        label.set_family(font_family)
        
    cb.outline.set_visible(False)
    
    return fig
