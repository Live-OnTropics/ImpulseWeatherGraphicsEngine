# src/products/base.py
from abc import ABC, abstractmethod

class BaseProduct(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def unit_label(self) -> str: pass

    @property
    @abstractmethod
    def val_suffix(self) -> str: pass

    @property
    @abstractmethod
    def colormap_ticks(self) -> list: pass

    @property
    @abstractmethod
    def color_points(self) -> list: pass

    @property
    @abstractmethod
    def vmin(self) -> float: pass

    @property
    @abstractmethod
    def vmax(self) -> float: pass

    @abstractmethod
    def get_candidates(self, model_endpoint: dict, map_type: str) -> list:
        """Determines variable candidates to extract from the THREDDS schema."""
        pass

    @abstractmethod
    def process_units(self, subset_data, raw_unit_string: str):
        """Converts units (e.g., Kelvin/Celsius to Fahrenheit)."""
        pass

    @abstractmethod
    def aggregate_time(self, subset_day, time_dim: str, map_type: str):
        """Processes calculations over the time dimension (min, max, or sum)."""
        pass
