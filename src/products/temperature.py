# src/products/temperature.py
import numpy as np
from src.products.base import BaseProduct

class TemperatureProduct(BaseProduct):
    def __init__(self):
        self._vmin = -40
        self._vmax = 120
        self._color_points = [
            (-40, '#ff00ff'), (-30, '#8b008b'), (-20, '#4b0082'), (-10, '#00008b'),
            (0,   '#0033cc'), (10,  '#0077ff'), (20,  '#00aaff'), (32,  '#00ccd6'),
            (40,  '#4eb38a'), (50,  '#2ca25f'), (60,  '#addd8e'), (70,  '#fec44f'),
            (80,  '#fe9929'), (90,  '#cc1111'), (100, '#660011'), (110, '#d47a85'),
            (120, '#999999')
        ]
        self._ticks = [-40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]

    @property
    def name(self) -> str: return "Temperature"
    @property
    def unit_label(self) -> str: return "°F"
    @property
    def val_suffix(self) -> str: return "°"
    @property
    def colormap_ticks(self) -> list: return self._ticks
    @property
    def color_points(self) -> list: return self._color_points
    @property
    def vmin(self) -> float: return self._vmin
    @property
    def vmax(self) -> float: return self._vmax

    def get_candidates(self, model_endpoint: dict, map_type: str) -> list:
        if "High" in map_type:
            return model_endpoint.get("highs_candidates", ["temperature_height_above_ground"])
        return model_endpoint.get("lows_candidates", ["temperature_height_above_ground"])

    def process_units(self, subset_data, raw_unit_string: str):
        units = raw_unit_string.lower()
        sample_val = float(np.atleast_1d(subset_data.values).flat[0])
        if 'k' in units or sample_val > 150:
            return (subset_data - 273.15) * 1.8 + 32
        elif 'c' in units or sample_val < 50:
            return subset_data * 1.8 + 32
        return subset_data

    def aggregate_time(self, subset_day, time_dim: str, map_type: str):
        if "High" in map_type:
            return subset_day.max(dim=time_dim).squeeze().load()
        return subset_day.min(dim=time_dim).squeeze().load()
