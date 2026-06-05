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
        product = TemperatureProduct()
        
        region_class = REGIONS.get(selected_region_name, TexasRegion)
        region = region_class()

        # 1. Fetch grid coordinates and metrics
        grid_lon, grid_lat, grid_values, map_label_values, model_name, data_proj, run_cycle_str = get_model_data(
            target_model, map_type, forecast_setting, product, region
        )
        
        # 2. Render regionalized visual canvas using static assets
        fig = render_map(
            grid_lon, grid_lat, grid_values, map_label_values, 
            model_name, data_proj, map_type, forecast_setting_str, 
            run_cycle_str, product, region, uploaded_logo_file=None
        )
        
        # 3. Save resulting visualization thread-safely
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
        
        # 1. Model Selection
        selected_model = st.sidebar.selectbox(
            "Select Numerical Model:",
            ["NDFD", "HRRR (2.5km)", "NAM (12km)", "GFS"],
            index=3
        )
        
        # 2. Map Region Selection
        selected_region_name = st.sidebar.selectbox(
            "Select Map Region:",
            list(REGIONS.keys())
        )
        
        # 3. Map Type Selection
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
        
        # Align calendar boundaries to regional local timezones
        region_class = REGIONS.get(selected_region_name, TexasRegion)
        local_tz = zoneinfo.ZoneInfo(region_class.timezone_str)
        today_date = datetime.datetime.now(local_tz).date()
        
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
        
        if st.sidebar.button("Generate Map", type="primary"):
            with st.spinner("Connecting to NCEP servers and compiling map..."):
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
