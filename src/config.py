# src/config.py
import numpy as np

# Coordinates ONLY for the 10 curated cities (No fake target temperatures)
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

# Locked temperature scale endpoints (from -40F to 120F)
VMIN = -40
VMAX = 120

# Color intervals mapped precisely to replicate input_file_5 with custom neon-sky blue transitions
COLOR_POINTS = [
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

# Scale intervals in clean 10-degree steps
COLORBAR_TICKS = [-40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]

# Priority sequence list of Unidata THREDDS datasets
MODEL_ENDPOINTS = [
    {
        "name": "NDFD",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NDFD/NWS/CONUS/CONDUIT/Best",
        "temp_candidates": [
            "maximum_temperature_height_above_ground",
            "temperature_height_above_ground"
        ]
    },
    {
        "name": "HRRR (2.5km)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/HRRR/CONUS_2p5km/Best",
        "temp_candidates": ["temperature_height_above_ground"]
    },
    {
        "name": "NAM (12km)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NAM/CONUS_12km/Best",
        "temp_candidates": ["temperature_height_above_ground"]
    },
    {
        "name": "GFS (0.25deg)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/GFS/Global_0p25deg/Best",
        "temp_candidates": ["temperature_height_above_ground"]
    }
]
