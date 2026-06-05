# src/products/precipitation.py
import numpy as np
from src.products.base import BaseProduct

class PrecipitationProduct(BaseProduct):
    def __init__(self):
        self._vmin = 0.01
        self._vmax = 20.0
        # Replicated high-precision color scale from target graphic
        self._color_points = [
            (0.01, '#c2e5e9'),  # Light ice blue
            (0.10, '#9dfc44'),  # Bright lime green
            (0.25, '#2ca02c'),  # Medium grass green
            (0.50, '#006600'),  # Dark forest green
            (0.75, '#1f4e79'),  # Deep steel blue
            (1.00, '#0077ff'),  # Vibrant blue
            (1.25, '#33ccff'),  # Light sky blue
            (1.50, '#7fffd4'),  # Aquamarine
            (1.75, '#b39ddb'),  # Pale lavender
            (2.00, '#9933cc'),  # Purple
            (2.50, '#4a148c'),  # Dark grape purple
            (3.00, '#800000'),  # Maroon
            (4.00, '#ff0000'),  # Red
            (5.00, '#ff6600'),  # Orange
            (7.00, '#ffa500'),  # Gold-orange
            (10.00, '#b8860b'), # Olive gold
            (15.00, '#ffff00'), # Yellow
            (20.00, '#ffb6c1')  # Pastel pink
        ]
        self._ticks = [0.01, 0.10, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00, 2.50, 3.00, 4.00, 5.00, 7.00, 10.00, 15.00, 20.00]

    @property
    def name(self) -> str: return "Total Precipitation"
    @property
    def unit_label(self) -> str: return "in"
    @property
    def val_suffix(self) -> str: return '"'
    @property
    def colormap_ticks(self) -> list: return self._ticks
    @property
    def color_points(self) -> list: return self._color_points
    @property
    def vmin(self) -> float: return self._vmin
    @property
    def vmax(self) -> float: return self._vmax

    def get_candidates(self, model_endpoint: dict, map_type: str) -> list:
        return model_endpoint.get("precip_candidates", ["Total_precipitation_surface_Mixed_intervals_Accumulation"])

    def process_units(self, subset_data, raw_unit_string: str):
        units = raw_unit_string.lower()
        # Convert mm, m, or kg/m^2 to inches
        if 'm' in units and 'mm' not in units:
            return subset_data * 39.3701
        return subset_data / 25.4

    def aggregate_time(self, subset_day, time_dim: str, map_type: str):
        return subset_day.squeeze().load()
