# src/config/regions.py

class TexasRegion:
    name = "Texas"
    extent = [-112.44, -87.56, 24.0, 38.0]
    mask_state = "Texas"
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

class PanhandleRegion:
    name = "Panhandle"
    extent = [-105.44, -96.56, 31.9, 36.9]
    mask_state = "Texas"  # Re-enabled Texas cutout masking
    timezone_str = "America/Chicago"
    cities = {
        'AMARILLO': (35.2219, -101.8313),
        'CHILDRESS': (34.4262, -100.2040),
        'LUBBOCK': (33.5779, -101.8552),
        'HASKELL': (33.1584, -99.7331),
        'WICHITA FALLS': (33.9137, -98.4934)
    }

class WestTexasRegion:
    name = "West Texas"
    extent = [-107.89, -99.01, 28.8, 33.8]
    mask_state = "Texas"  # Re-enabled Texas cutout masking
    timezone_str = "America/Chicago"
    cities = {
        'EL PASO': (31.7619, -106.4850),
        'VAN HORN': (31.0407, -104.8308),
        'FT. STOCKTON': (30.8874, -102.8793),
        'ALPINE': (30.3585, -103.6611),
        'SANDERSON': (30.1422, -102.3975),
        'OZONA': (30.7088, -101.2051),
        'DEL RIO': (29.3627, -100.8968),
        'ODESSA-MIDLAND': (31.9973, -102.0779),
        'SAN ANGELO': (31.4638, -100.4370)
    }

class TriangleTexasRegion:
    name = "The Triangle Texas"
    extent = [-101.04, -92.16, 29.1, 34.1]
    mask_state = "Texas"  # Re-enabled Texas cutout masking
    timezone_str = "America/Chicago"
    cities = {
        'TEXARKANA': (33.4251, -94.0477),
        'TYLER': (32.3513, -95.3011),
        'LUFKIN': (31.3382, -94.7291),
        'HOUSTON': (29.7604, -95.3698),
        'DFW': (32.7767, -96.9970),
        'WACO': (31.5497, -97.1467),
        'BRYAN': (30.6744, -96.3700),
        'AUSTIN': (30.2672, -97.7431),
        'LLANO': (30.7510, -98.6750),
        'KERRVILLE': (30.0474, -99.1403),
        'BROWNWOOD': (31.7093, -98.9912)
    }

class SouthTexasRegion:
    name = "South Texas"
    extent = [-102.94, -94.06, 24.9, 29.9]
    mask_state = "Texas"  # Re-enabled Texas cutout masking
    timezone_str = "America/Chicago"
    cities = {
        'EAGLE PASS': (28.7086, -100.4903),
        'ZAPATA': (26.9076, -99.2718),
        'BROWNSVILLE': (25.9017, -97.4975),
        'CORPUS CHRISTI': (27.8003, -97.3964),
        'VICTORIA': (28.8052, -97.0036),
        'JOURDANTON': (28.9247, -98.5451)
    }

REGIONS = {
    "Texas": TexasRegion,
    "Panhandle": PanhandleRegion,
    "West Texas": WestTexasRegion,
    "The Triangle Texas": TriangleTexasRegion,
    "South Texas": SouthTexasRegion
}
