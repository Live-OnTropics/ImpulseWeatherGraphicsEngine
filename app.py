# app.py
import os
import datetime
import zoneinfo
import streamlit as st

# Custom modular backends
from src.config.models import MODEL_ENDPOINTS
from src.config.regions import REGIONS, TexasRegion
from src.products.temperature import TemperatureProduct
from src.core.data_fetcher import get_model_data
from src.core.map_renderer import render_map

import streamlit.runtime as st_runtime
is_streamlit = st_runtime.exists()

def execute_pipeline(target_model, map_type, forecast_setting, forecast_setting_str, selected_region_name):
    try:
        is_spc = "Convective Outlook" in map_type
        
        region_class = REGIONS.get(selected_region_name, TexasRegion)
        region = region_class()

        if is_spc:
            # 1. Instantiate the SPC outlook product configuration
            from src.products.convective_outlook import ConvectiveOutlookProduct
            day_num = int(forecast_setting)
            product = ConvectiveOutlookProduct(day=day_num)
            
            # 2. Programmatically fetch vector polygons from SPC
            features = product.fetch_geojson()
            
            # 3. Assess severe risk boundaries for every coordinate point
            from shapely.geometry import Point, shape
            map_label_values = {city: "" for city in region.cities.keys()}
            
            RISK_ORDER = {"TSTM": 1, "MRGL": 2, "SLGT": 3, "ENH": 4, "MDT": 5, "HIGH": 6}
            features_sorted = sorted(features, key=lambda f: RISK_ORDER.get(f["properties"].get("LABEL2", ""), 0))
            
            for f in features_sorted:
                label2 = f["properties"].get("LABEL2", "")
                if not label2:
                    continue
                try:
                    geom = shape(f["geometry"])
                    for city, (lat, lon) in region.cities.items():
                        if geom.contains(Point(lon, lat)):
                            map_label_values[city] = label2
                except Exception as e:
                    print(f"Error checking coordinates for {city}: {e}")
            
            # Package metadata for rendering canvas
            import cartopy.crs as ccrs
            data_proj = ccrs.PlateCarree()
            model_name = "NOAA/SPC"
            run_cycle_str = ""
            grid_lon, grid_lat = None, None
            grid_values = features
        else:
            # Standard temperature models extraction
            product = TemperatureProduct()
            grid_lon, grid_lat, grid_values, map_label_values, model_name, data_proj, run_cycle_str = get_model_data(
                target_model, map_type, forecast_setting, product, region
            )
        
        # 4. Render output graphics canvas
        fig = render_map(
            grid_lon, grid_lat, grid_values, map_label_values, 
            model_name, data_proj, map_type, forecast_setting_str, 
            run_cycle_str, product, region, uploaded_logo_file=None
        )
        
        output_filename = 'texas_forecast_highs.png'
        fig.savefig(output_filename, dpi=100, facecolor=fig.get_facecolor(), edgecolor='none')
        
        return True, output_filename
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)


if __name__ == '__main__':
    if is_streamlit:
        st.title("Impulse Weather Map Dashboard")
        st.write("Configure your options on the sidebar and click **Generate Map**.")
        
        # 1. High-level category switch (hides/shows model toggles)
        selected_category = st.sidebar.selectbox(
            "Select Map Category:",
            ["Numerical Forecast Models", "SPC Convective Outlooks"]
        )
        
        # 2. Map Region Selection
        selected_region_name = st.sidebar.selectbox(
            "Select Map Region:",
            list(REGIONS.keys())
        )
        
        region_class = REGIONS.get(selected_region_name, TexasRegion)
        local_tz = zoneinfo.ZoneInfo(region_class.timezone_str)
        today_date = datetime.datetime.now(local_tz).date()
        
        if selected_category == "Numerical Forecast Models":
            # Show options for temperature models
            selected_model = st.sidebar.selectbox(
                "Select Numerical Model:",
                ["NDFD", "HRRR (2.5km)", "NAM (12km)", "GFS"],
                index=3
            )
            
            selected_map_type = st.sidebar.selectbox(
                "Select Map Type:",
                ["Forecast High Temperatures", "Forecast Low Temperatures"]
            )
            
            selected_ep = None
            for ep in MODEL_ENDPOINTS:
                ep_name_lower = ep["name"].lower()
                sel_model_lower = selected_model.lower()
                if sel_model_lower in ep_name_lower or ep_name_lower in sel_model_lower:
                    selected_ep = ep
                    break
                    
            if selected_ep is None:
                selected_ep = MODEL_ENDPOINTS[0]
                
            max_days = selected_ep.get("max_days", 5)
            
            day_options = []
            day_mapping = {}
            for i in range(max_days):
                day_date = today_date + datetime.timedelta(days=i)
                day_label = day_date.strftime("%A, %b %d")
                day_options.append(day_label)
                day_mapping[day_label] = i
                
            selected_day_label = st.sidebar.selectbox("Select Forecast Day:", day_options)
            forecast_setting = day_mapping[selected_day_label]
            forecast_setting_str = (today_date + datetime.timedelta(days=forecast_setting)).strftime("%A").upper()
        else:
            # Show convective outlook parameters (Bypasses model select entirely)
            selected_map_type = st.sidebar.selectbox(
                "Select Outlook Day:",
                ["Day 1 Convective Outlook", "Day 2 Convective Outlook", "Day 3 Convective Outlook"]
            )
            selected_model = "SPC"
            forecast_setting = int(selected_map_type.split()[1])
            outlook_date = today_date + datetime.timedelta(days=forecast_setting - 1)
            forecast_setting_str = outlook_date.strftime("%A").upper()
        
        if st.sidebar.button("Generate Map", type="primary"):
            with st.spinner("Compiling map assets..."):
                success, result = execute_pipeline(
                    selected_model, selected_map_type, 
                    forecast_setting, forecast_setting_str, 
                    selected_region_name
                )
                
                if success:
                    st.success("Map generated successfully!")
                    st.image(result, width='stretch')
                    
                    with open(result, "rb") as file:
                        st.download_button(
                            label="Download High-Resolution Map",
                            data=file,
                            file_name="forecast_map_1080p.png",
                            mime="image/png"
                        )
                else:
                    st.error(f"Failed to generate map: {result}")
            st.write(f"Refreshed: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("Executing local weather generation pipeline...")
        success, result = execute_pipeline("GFS", "Forecast High Temperatures", 0, "TODAY", "Texas")
        if success:
            print(f"Map successfully saved to {result}")
        else:
            print(f"Error during execution: {result}")
