# src/config.py
import numpy as np

# Coordinates ONLY for the 10 curated cities (No hardcoded fake temperatures)
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

# Rain scale definitions matching input_file_8
RAIN_VMIN = 0.0
RAIN_VMAX = 18.0
RAIN_COLOR_POINTS = [
    (0.0,   '#151c24', 0.0),  # 0 in: Fully transparent, matches map background
    (0.005, '#ffeb3b', 0.5),  # 0.005 in: Fading semi-transparent yellow
    (0.01,  '#ffeb3b', 1.0),  # 0.01 in: Fully opaque yellow
    (0.5,   '#ff9800', 1.0),  # Orange
    (1.0,   '#e53935', 1.0),  # Red
    (2.0,   '#880e4f', 1.0),  # Dark Red / Magenta
    (4.0,   '#7b1fa2', 1.0),  # Purple
    (6.0,   '#e1bee7', 1.0),  # Pale Purple
    (8.0,   '#80deea', 1.0),  # Soft Cyan
    (10.0,  '#29b6f6', 1.0),  # Sky Blue
    (12.0,  '#0288d1', 1.0),  # Medium Blue
    (14.0,  '#006064', 1.0),  # Dark Blue/Teal
    (16.0,  '#004d40', 1.0),  # Green-Teal
    (18.0,  '#1b5e20', 1.0),  # Forest Green
]
RAIN_COLORBAR_TICKS = [0.01, 2, 4, 6, 8, 10, 12, 14, 16, 18]

# Priority sequence list of Unidata THREDDS datasets
MODEL_ENDPOINTS = [
    {
        "name": "NDFD",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NDFD/NWS/CONUS/CONDUIT/Best",
        "highs_candidates": ["maximum_temperature_height_above_ground_Mixed_intervals_Maximum", "maximum_temperature_height_above_ground"],
        "lows_candidates": ["minimum_temperature_height_above_ground_Mixed_intervals_Minimum", "minimum_temperature_height_above_ground"],
        "rain_candidates": ["total_precipitation_surface_6_Hour_Accumulation", "total_precipitation_surface"]
    },
    {
        "name": "HRRR (2.5km)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/HRRR/CONUS_2p5km/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "rain_candidates": ["total_precipitation_surface_1_Hour_Accumulation", "total_precipitation_surface"]
    },
    {
        "name": "NAM (12km)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NAM/CONUS_12km/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "rain_candidates": ["total_precipitation_surface_3_Hour_Accumulation", "total_precipitation_surface"]
    },
    {
        "name": "GFS (0.25deg)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/GFS/Global_0p25deg/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "rain_candidates": ["total_precipitation_surface_Mixed_intervals_Accumulation", "total_precipitation_surface"]
    }
]
