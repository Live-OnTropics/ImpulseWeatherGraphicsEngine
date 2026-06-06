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
from src.core.map_renderer import render_map, get_risk_code

import streamlit.runtime as st_runtime
is_streamlit = st_runtime.exists()

def execute_pipeline(target_model, map_type, forecast_setting, forecast_setting_str, selected_region_name):
    try:
        is_spc = "Convective Outlook" in map_type
        is_wpc = "Excessive Rainfall" in map_type
        is_vector = is_spc or is_wpc
        is_precip = "Precipitation" in map_type
        is_radar = "Future Radar" in map_type
        
        region_class = REGIONS.get(selected_region_name, TexasRegion)
        region = region_class()

        if is_vector:
            # 1. Instantiate vector products
            if is_spc:
                from src.products.convective_outlook import ConvectiveOutlookProduct
                day_num = int(forecast_setting)
                product = ConvectiveOutlookProduct(day=day_num)
            else:
                from src.products.excessive_rainfall import ExcessiveRainfallProduct
                day_num = int(forecast_setting)
                product = ExcessiveRainfallProduct(day=day_num)
            
            # 2. Fetch GeoJSON features
            features = product.fetch_geojson()
            
            # 3. Assess spatial risk intersections
            from shapely.geometry import Point, shape
            map_label_values = {city: "" for city in region.cities.keys()}
            
            for f in features:
                risk_code = get_risk_code(f)
                if not risk_code:
                    continue
                try:
                    geom = shape(f["geometry"])
                    for city, (lat, lon) in region.cities.items():
                        if geom.contains(Point(lon, lat)):
                            map_label_values[city] = risk_code
                except Exception as e:
                    print(f"Error checking coordinates for {city}: {e}")
            
            import cartopy.crs as ccrs
            data_proj = ccrs.PlateCarree()
            model_name = "NOAA/SPC" if is_spc else "NOAA/WPC"
            run_cycle_str = ""
            grid_lon, grid_lat = None, None
            grid_values = features
        else:
            # Gridded products loading (Temperature vs Precipitation vs Radar)
            if is_precip:
                from src.products.precipitation import PrecipitationProduct
                product = PrecipitationProduct()
            elif is_radar:
                from src.products.radar import FutureRadarProduct
                product = FutureRadarProduct()
            else:
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
            ["Numerical Forecast Models", "SPC Convective Outlooks", "WPC Excessive Rainfall Outlooks"]
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
            selected_map_type = st.sidebar.selectbox(
                "Select Map Type:",
                ["Forecast High Temperatures", "Forecast Low Temperatures", "Total Precipitation", "Future Radar"]
            )
            
            if selected_map_type == "Total Precipitation":
                # Only HRRR is currently eligible for precipitation
                selected_model = st.sidebar.selectbox(
                    "Select Numerical Model:",
                    ["HRRR (2.5km)"]
                )
            elif selected_map_type == "Future Radar":
                # Both HRRR and GFS are eligible for Future Radar [input_file_0.py]
                selected_model = st.sidebar.selectbox(
                    "Select Numerical Model:",
                    ["HRRR (2.5km)", "GFS"]
                )
            else:
                # Temperature models
                selected_model = st.sidebar.selectbox(
                    "Select Numerical Model:",
                    ["NDFD", "HRRR (2.5km)", "NAM (12km)", "GFS"],
                    index=3
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
                
            if selected_map_type in ["Total Precipitation", "Future Radar"]:
                if "hrrr" in selected_model.lower():
                    max_hours, step = 48, 1
                else:  # GFS [input_file_0.py]
                    max_hours, step = 384, 3
                
                # Retrieve current synoptic cycle initialization in UTC to align frames
                now_utc = datetime.datetime.now(zoneinfo.ZoneInfo("UTC"))
                if "hrrr" in selected_model.lower():
                    run_utc = now_utc.replace(minute=0, second=0, microsecond=0) - datetime.timedelta(hours=2)
                else:
                    cycle_hour = (now_utc.hour // 6) * 6
                    run_utc = now_utc.replace(hour=cycle_hour, minute=0, second=0, microsecond=0) - datetime.timedelta(hours=6)
                
                # Convert synchronization hour to localized Texas (Central) base time
                base_time_local = run_utc.astimezone(local_tz)
                
                min_val = 1 if "hrrr" in selected_model.lower() else 3
                selected_hour = st.sidebar.slider(
                    "Select Forecast Hour:",
                    min_value=min_val,
                    max_value=max_hours,
                    value=min_val,
                    step=step
                )
                
                valid_time = base_time_local + datetime.timedelta(hours=selected_hour)
                valid_time_str = valid_time.strftime("%A, %b %d @ %I:%M %p")
                st.sidebar.caption(f"Valid: {valid_time_str}")
                
                forecast_setting = selected_hour
                if selected_map_type == "Total Precipitation":
                    forecast_setting_str = f"{selected_hour}H ACCUMULATED"
                else:
                    forecast_setting_str = f"HOUR {selected_hour} FORECAST"
            else:
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
        elif selected_category == "SPC Convective Outlooks":
            # Show convective parameters for Days 1 to 8 (Bypasses model select entirely)
            selected_map_type = st.sidebar.selectbox(
                "Select Outlook Day:",
                [
                    "Day 1 Convective Outlook", "Day 2 Convective Outlook", "Day 3 Convective Outlook",
                    "Day 4 Convective Outlook", "Day 5 Convective Outlook", "Day 6 Convective Outlook",
                    "Day 7 Convective Outlook", "Day 8 Convective Outlook"
                ]
            )
            selected_model = "SPC"
            forecast_setting = int(selected_map_type.split()[1])
            outlook_date = today_date + datetime.timedelta(days=forecast_setting - 1)
            forecast_setting_str = outlook_date.strftime("%A").upper()
        else:
            # Show excessive rainfall parameters for Days 1 to 5 (Bypasses model select entirely)
            selected_map_type = st.sidebar.selectbox(
                "Select Outlook Day:",
                [
                    "Day 1 Excessive Rainfall Outlook", "Day 2 Excessive Rainfall Outlook", "Day 3 Excessive Rainfall Outlook",
                    "Day 4 Excessive Rainfall Outlook", "Day 5 Excessive Rainfall Outlook"
                ]
            )
            selected_model = "WPC"
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
