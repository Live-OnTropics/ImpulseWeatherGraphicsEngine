# src/products/radar.py
from src.products.base import BaseProduct

class FutureRadarProduct(BaseProduct):
    def __init__(self):
        self._vmin = 10.0
        self._vmax = 75.0
        # Continuous reflectivity scale from target legend
        self._color_points = [
            (10, '#244a34'),  # Deep forest green
            (20, '#55aa55'),  # Medium grass green
            (30, '#ffe066'),  # Yellow
            (40, '#ff9933'),  # Orange
            (50, '#cc1111'),  # Red
            (60, '#e500e5'),  # Magenta / Hot Pink
            (70, '#ffaaff'),  # Light Lavender Pink
            (75, '#ffffff')   # White
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
        return subset_day.squeeze().load()
