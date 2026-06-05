# src/config/regions.py

class TexasRegion:
    name = "Texas"
    # Longitude boundaries, Latitude boundaries
    extent = [-112.44, -87.56, 24.0, 38.0]
    mask_state = "Texas"  # Clips background mapping to this state
    timezone_str = "America/Chicago"
    
    cities = {
        'AMARILLO': (35.2219, -101.8313),
        'ODESSA-MIDLAND': (31.9973, -102.0779),
        'EL PASO': (31.7619, -106.4850),
        'DEL RIO': (29.3627, -100.8968),
        'WICHITA FALLS': (33.9137, -98.4934),
        'DFW': (32.7767, -96.9970),
        'AUSTIN': (30.2672, -97.7431),
        'HOUSTON': (29.7604, -95.3698),
        'CORPUS CHRISTI': (27.8003, -97.3964),
        'BROWNSVILLE': (25.9017, -97.4975)
    }
