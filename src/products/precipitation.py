# src/products/precipitation.py
import numpy as np
from src.products.base import BaseProduct

class PrecipitationProduct(BaseProduct):
    def __init__(self):
        self._vmin = 0.01
        self._vmax = 20.0
        # Muted, professional weather-engine color transitions
        self._color_points = [
            (0.01, '#1c3445'),  # Deep dark slate-teal (transitions softly from #1b2432)
            (0.10, '#244d5c'),  # Dark slate-blue
            (0.25, '#2b6973'),  # Deep teal
            (0.50, '#358a8a'),  # Muted seafoam
            (0.75, '#41a695'),  # Minty teal-green
            (1.00, '#52be80'),  # Soft grass green
            (1.25, '#7dcd5b'),  # Light lime green
            (1.50, '#bade4c'),  # Bright yellow-green
            (1.75, '#f4d03f'),  # Warm yellow
            (2.00, '#f39c12'),  # Warm orange
            (2.50, '#d35400'),  # Burnt orange/red-orange
            (3.00, '#c0392b'),  # Muted red
            (4.00, '#900c3f'),  # Dark crimson red
            (5.00, '#581845'),  # Deep dark wine/maroon
            (7.00, '#8e44ad'),  # Purple
            (10.00, '#732c91'), # Dark purple
            (15.00, '#af7ac5'), # Lavender purple
            (20.00, '#d7bde2')  # Light pastel orchid/pink
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
        if 'mm' in units or 'kg' in units:
            return subset_data / 25.4  # Millimeters or kg/m^2 to inches
        elif 'meter' in units or units == 'm':
            return subset_data * 39.3701  # Meters to inches
        elif 'inch' in units or 'in' in units:
            return subset_data
        else:
            max_raw = float(subset_data.max().values)
            if max_raw < 0.5 and max_raw > 0.001:
                return subset_data * 39.3701  # Assumed meters
            elif max_raw > 1.0 and max_raw < 500.0:
                return subset_data / 25.4  # Assumed millimeters
            return subset_data

    def aggregate_time(self, subset_day, time_dim: str, map_type: str):
        # If the time slice contains multiple steps (for HRRR/NAM/RAP), sum them automatically
        if time_dim in subset_day.dims and subset_day[time_dim].size > 1:
            return subset_day.sum(dim=time_dim).load()
        return subset_day.squeeze().load()
