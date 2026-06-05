# app.py
import os
import datetime
import zoneinfo
import streamlit as st

# Import custom modular backend elements
from src.config import MODEL_ENDPOINTS
from src.data_fetcher import get_model_data
from src.map_renderer import render_texas_map

# Detect if running in Streamlit runtime environment
import streamlit.runtime as st_runtime
is_streamlit = st_runtime.exists()

def execute_pipeline(target_model, map_type, forecast_setting, forecast_setting_str, uploaded_logo):
    try:
        # 1. Fetch live coordinates safely (Raises ConnectionError if server is offline)
        grid_lon, grid_lat, grid_temp, map_label_temps, model_name, data_proj, run_cycle_str = get_model_data(
            target_model, map_type, forecast_setting
        )
        
        # 2. Render map canvas
        fig = render_texas_map(
            grid_lon, grid_lat, grid_temp, map_label_temps, 
            model_name, data_proj, map_type, forecast_setting_str, 
            run_cycle_str, uploaded_logo_file=uploaded_logo
        )
        
        # 3. Save map image thread-safely
        output_filename = 'texas_forecast_highs.png'
        fig.savefig(output_filename, dpi=100, facecolor=fig.get_facecolor(), edgecolor='none')
        
        return True, output_filename
    except Exception as e:
        return False, str(e)


if __name__ == '__main__':
    if is_streamlit:
        st.title("Impulse Weather Map Dashboard")
        st.write("Configure your options on the sidebar and click **Generate Map**.")
        
        # 1. Model Selection (GFS is now labeled cleanly)
        selected_model = st.sidebar.selectbox(
            "Select Numerical Model:",
            ["NDFD", "HRRR (2.5km)", "NAM (12km)", "GFS"],
            index=3  # Default GFS
        )
        
        # 2. Map Type Selection
        selected_map_type = st.sidebar.selectbox(
            "Select Map Type:",
            ["Forecast High Temperatures", "Forecast Low Temperatures"]
        )
        
        # 3. Dynamic Forecast Day depth limits based on selected model's forecast duration
        # Resilient, case-insensitive substring scanner (prevents any configuration IndexError)
        selected_ep = None
        for ep in MODEL_ENDPOINTS:
            ep_name_lower = ep["name"].lower()
            sel_model_lower = selected_model.lower()
            if sel_model_lower in ep_name_lower or ep_name_lower in sel_model_lower:
                selected_ep = ep
                break
                
        # Safe fallback default in case of any unexpected naming mismatches
        if selected_ep is None:
            selected_ep = MODEL_ENDPOINTS[0]
            
        max_days = selected_ep.get("max_days", 5)
        
        # Establish real calendar dates relative to Austin (Central) Time
        austin_tz = zoneinfo.ZoneInfo("America/Chicago")
        today_date = datetime.datetime.now(austin_tz).date()
        
        day_options = []
        day_mapping = {}
        for i in range(max_days):
            day_date = today_date + datetime.timedelta(days=i)
            # Create readable labels like "Friday, Jun 05"
            day_label = day_date.strftime("%A, %b %d")
            day_options.append(day_label)
            day_mapping[day_label] = i
            
        selected_day_label = st.sidebar.selectbox("Select Forecast Day:", day_options)
        forecast_setting = day_mapping[selected_day_label]
        
        # Extract name of day (e.g. "FRIDAY")
        forecast_setting_str = (today_date + datetime.timedelta(days=forecast_setting)).strftime("%A").upper()
            
        # 4. Brand Logo Uploader
        uploaded_logo = st.sidebar.file_uploader("Upload Brand Logo (Optional):", type=["png"])
        
        if st.sidebar.button("Generate Map", type="primary"):
            with st.spinner("Connecting to NCEP servers and compiling map..."):
                success, result = execute_pipeline(
                    selected_model, selected_map_type, 
                    forecast_setting, forecast_setting_str, uploaded_logo
                )
                
                if success:
                    st.success("Map generated successfully!")
                    st.image(result, width='stretch')  # Resolved: use width='stretch' to prevent deprecation warning
                    
                    # File downloader widget
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
        # Local terminal execution mode
        print("Executing local weather generation pipeline...")
        success, result = execute_pipeline("GFS", "Forecast High Temperatures", 0, "TODAY", None)
        if success:
            print(f"Map successfully saved to {result}")
        else:
            print(f"Error during execution: {result}")
