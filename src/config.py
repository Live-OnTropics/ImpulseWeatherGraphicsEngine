# src/config.py
import numpy as np

# Coordinates ONLY for the 10 curated cities
MAP_LABELS_REDUCED = {
    'AMARILLO': (35.2219, -101.8313),
    'ODESSA-MIDLAND': (31.9973, -102.0779),  # Combined Odessa-Midland hub
    'EL PASO': (31.7619, -106.4850),
    'DEL RIO': (29.3627, -100.8968),
    'WICHITA FALLS': (33.9137, -98.4934),
    'DFW': (32.7767, -96.9970),
    'AUSTIN': (30.2672, -97.7431),
    'HOUSTON': (29.7604, -95.3698),
    'CORPUS CHRISTI': (27.8003, -97.3964),
    'BROWNSVILLE': (25.9017, -97.4975)
}

# Locked temperature scale endpoints (from -40°F to 120°F)
TEMP_VMIN = -40
TEMP_VMAX = 120
TEMP_COLOR_POINTS = [
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
TEMP_COLORBAR_TICKS = [-40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]

# Rain scale boundaries (0.00 inches to 18.00 inches)
RAIN_VMIN = 0.0
RAIN_VMAX = 18.0

# Rebuilt Rain Scale matching your exact specifications and opacity limits
RAIN_COLOR_POINTS = [
    (0.0,   '#151c24', 0.0),  # 0 in: Transparent (matches background)
    (0.005, '#d3d3d3', 0.5),  # Fades in
    (0.01,  '#d3d3d3', 1.0),  # 0.01 in: Light Gray
    (0.09,  '#808080', 1.0),  # 0.09 in: Gray
    (0.10,  '#90ee90', 1.0),  # 0.10 in: Light Green
    (0.49,  '#1b6e1b', 1.0),  # 0.49 in: Darker Green
    (0.50,  '#1d70b8', 1.0),  # 0.50 in: Dark Sky Blue
    (0.99,  '#87cefa', 1.0),  # 0.99 in: Light Sky Blue
    (1.00,  '#ffd300', 1.0),  # 1.00 in: Yellow
    (1.99,  '#ffaa00', 1.0),  # 1.99 in: Orangeish Yellow
    (2.00,  '#f37021', 1.0),  # 2.00 in: Orange
    (3.99,  '#800010', 1.0),  # 3.99 in: Dark Red
    (4.00,  '#d81b60', 1.0),  # 4.00 in: Dark Pink/Red
    (6.0,   '#e1bee7', 1.0),  # 6.0 in: Pale Purple
    (8.0,   '#80deea', 1.0),  # 8.0 in: Soft Cyan
    (10.0,  '#29b6f6', 1.0),  # 10.0 in: Sky Blue
    (12.0,  '#0288d1', 1.0),  # 12.0 in: Medium Blue
    (14.0,  '#006064', 1.0),  # 14.0 in: Dark Blue/Teal
    (16.0,  '#004d40', 1.0),  # 16.0 in: Green-Teal
    (18.0,  '#1b5e20', 1.0),  # 18.0 in: Forest Green
]
RAIN_COLORBAR_TICKS = [0.01, 2, 4, 6, 8, 10, 12, 14, 16, 18]

# Priority sequence list of Unidata THREDDS datasets
MODEL_ENDPOINTS = [
    {
        "name": "NDFD",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NDFD/NWS/CONUS/CONDUIT/Best",
        "highs_candidates": ["maximum_temperature_height_above_ground_Mixed_intervals_Maximum", "maximum_temperature_height_above_ground"],
        "lows_candidates": ["minimum_temperature_height_above_ground_Mixed_intervals_Minimum", "minimum_temperature_height_above_ground"],
        "rain_candidates": ["total_precipitation_surface_accumulation", "total_precipitation_surface", "total_precipitation_surface_6_hour_accumulation"]
    },
    {
        "name": "HRRR (2.5km)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/HRRR/CONUS_2p5km/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "rain_candidates": ["total_precipitation_surface_accumulation", "total_precipitation_surface", "total_precipitation_surface_1_hour_accumulation"]
    },
    {
        "name": "NAM (12km)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NAM/CONUS_12km/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "rain_candidates": ["total_precipitation_surface_accumulation", "total_precipitation_surface", "total_precipitation_surface_3_hour_accumulation"]
    },
    {
        "name": "GFS (0.25deg)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/GFS/Global_0p25deg/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "rain_candidates": ["total_precipitation_surface_accumulation", "total_precipitation_surface", "total_precipitation_surface_mixed_intervals_accumulation"]
    }
]
