# src/products/radar.py
from src.products.base import BaseProduct

class FutureRadarProduct(BaseProduct):
    def __init__(self):
        self._vmin = 10.0
        self._vmax = 70.0  # Upper scale boundary set to 70.0 dBZ
        # Binned color table with sharp transition at 35.0 dBZ [input_file_2.py]
        self._color_points = [
            (10.0, '#76EE76'),     # Light Green
            (22.5, '#45C145'),     # Medium Green
            (35.0, '#1B7A1B'),     # Dark Green (upper boundary of green)
            (35.001, '#FFF033'),   # Warm Yellow (sharp jump at 35.0 dBZ!) [input_file_2.py]
            (45.0, '#FF8000'),     # Orange
            (50.0, '#FF0000'),     # Red
            (55.0, '#A00000'),     # Dark Red
            (65.0, '#FF00FF'),     # Magenta
            (70.0, '#FFFFFF')      # White
        ]

    @property
    def name(self) -> str: return "Future Radar"
    @property
    def unit_label(self) -> str: return "dBZ"
    @property
    def val_suffix(self) -> str: return ""
    @property
    def colormap_ticks(self) -> list: return []
    @property
    def color_points(self) -> list: return self._color_points
    @property
    def vmin(self) -> float: return self._vmin
    @property
    def vmax(self) -> float: return self._vmax

    def get_candidates(self, model_endpoint: dict, map_type: str) -> list:
        return model_endpoint.get("radar_candidates", ["Composite_reflectivity_entire_atmosphere", "Composite_reflectivity", "REFC"])

    def process_units(self, subset_data, raw_unit_string: str):
        # Reflectivity coordinates on THREDDS are distributed in dB/dBZ directly
        return subset_data

    def aggregate_time(self, subset_day, time_dim: str, map_type: str):
        return subset_day
