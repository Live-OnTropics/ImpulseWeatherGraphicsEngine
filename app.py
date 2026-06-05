# app.py
import os
import streamlit as st

# Import custom modular backend elements
from src.data_fetcher import get_model_data
from src.map_renderer import render_texas_map

# Detect if running in Streamlit runtime environment
import streamlit.runtime as st_runtime
is_streamlit = st_runtime.exists()

def execute_pipeline(target_model, map_type, forecast_setting, forecast_setting_str, uploaded_logo):
    try:
        # 1. Fetch live coordinates safely (Raises ConnectionError if server is offline)
        grid_lon, grid_lat, grid_temp, map_label_temps, model_name, data_proj = get_model_data(
            target_model, map_type, forecast_setting
        )
        
        # 2. Render map canvas
        fig = render_texas_map(
            grid_lon, grid_lat, grid_temp, map_label_temps, 
            model_name, data_proj, map_type, forecast_setting_str, 
            uploaded_logo_file=uploaded_logo
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
        
        # 1. Model Selection
        selected_model = st.sidebar.selectbox(
            "Select Numerical Model:",
            ["NDFD", "HRRR (2.5km)", "NAM (12km)", "GFS (0.25deg)"],
            index=3  # Default GFS
        )
        
        # 2. Map Type Selection (Temperatures Only)
        selected_map_type = st.sidebar.selectbox(
            "Select Map Type:",
            ["Forecast High Temperatures", "Forecast Low Temperatures"]
        )
        
        # 3. Forecast Day Selection
        day_mapping = {"Today": 0, "Tomorrow": 1, "Day 3": 2, "Day 4": 3, "Day 5": 4}
        selected_day_label = st.sidebar.selectbox("Select Forecast Day:", list(day_mapping.keys()))
        forecast_setting = day_mapping[selected_day_label]
        forecast_setting_str = selected_day_label.upper()
            
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
                    st.image(result, use_container_width=True)
                    
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
        success, result = execute_pipeline("GFS (0.25deg)", "Forecast High Temperatures", 0, "TODAY", None)
        if success:
            print(f"Map successfully saved to {result}")
        else:
            print(f"Error during execution: {result}")
