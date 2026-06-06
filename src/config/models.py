# src/config/models.py

MODEL_ENDPOINTS = [
    {
        "name": "NDFD",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NDFD/NWS/CONUS/CONDUIT/Best",
        "highs_candidates": ["maximum_temperature_height_above_ground_Mixed_intervals_Maximum", "maximum_temperature_height_above_ground"],
        "lows_candidates": ["minimum_temperature_height_above_ground_Mixed_intervals_Minimum", "minimum_temperature_height_above_ground"],
        "max_days": 7
    },
    {
        "name": "HRRR (2.5km)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/HRRR/CONUS_2p5km/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "precip_candidates": ["Total_precipitation_surface_1_Hour_Accumulation"],
        "max_days": 2
    },
    {
        "name": "NAM (12km)",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NAM/CONUS_12km/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "max_days": 4
    },
    {
        "name": "GFS",
        "url": "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/GFS/Global_0p25deg/Best",
        "highs_candidates": ["temperature_height_above_ground"],
        "lows_candidates": ["temperature_height_above_ground"],
        "max_days": 16
    }
]
