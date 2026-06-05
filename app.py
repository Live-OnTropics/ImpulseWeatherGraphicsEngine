# app.py
import os
import streamlit as st

# Import the modular custom backend scripts
from src.data_fetcher import get_model_data
from src.map_renderer import render_texas_map

# Detect if we are running inside a Streamlit Web environment
import streamlit.runtime as st_runtime
is_streamlit = st_runtime.exists()

def execute_pipeline(target_model, uploaded_logo):
    try:
        # 1. Fetch live model arrays safely
        grid_lon, grid_lat, grid_temp, map_label_temps, model_name, data_proj = get_model_data(target_model)
        
        # 2. Render the canvas natively
        fig = render_texas_map(
            grid_lon, grid_lat, grid_temp, map_label_temps, 
            model_name, data_proj, uploaded_logo_file=uploaded_logo
        )
        
        # 3. Save the exact 1080p canvas thread-safely
        output_filename = 'texas_forecast_highs.png'
        fig.savefig(output_filename, dpi=100, facecolor=fig.get_facecolor(), edgecolor='none')
        
        return True, output_filename
    except Exception as e:
        return False, str(e)


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
                success, result = execute_pipeline(selected_model, uploaded_logo)
                
                if success:
                    st.success("Map generated successfully!")
                    st.image(result, use_container_width=True)
                    
                    # Provide direct download link
                    with open(result, "rb") as file:
                        st.download_button(
                            label="Download High-Resolution Map",
                            data=file,
                            file_name="texas_forecast_highs.png",
                            mime="image/png"
                        )
                else:
                    st.error(f"Failed to generate map: {result}")
    else:
        # Standard CLI local execution mode
        print("Executing local weather generation pipeline...")
        success, result = execute_pipeline(None, None)
        if success:
            print(f"Map successfully saved to {result}")
        else:
            print(f"Error during execution: {result}")
