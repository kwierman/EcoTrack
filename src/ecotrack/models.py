from dataclasses import dataclass
from typing import Optional


@dataclass
class CountryProfile:
    country: str
    country_code: str
    region: str
    population: int
    gdp_per_capita: float


@dataclass
class WasteMetric:
    country_code: str
    year: int
    total_waste_kg_cap: Optional[float]
    msw_kg_cap: Optional[float]
    industrial_waste_kt: Optional[float]
    hazardous_waste_kt: Optional[float]
    e_waste_kg_cap: Optional[float]
    food_waste_kg_cap: Optional[float]


@dataclass
class RecyclingRate:
    country_code: str
    year: int
    overall_rate: Optional[float]
    paper_rate: Optional[float]
    plastic_rate: Optional[float]
    glass_rate: Optional[float]
    metal_rate: Optional[float]
    organic_rate: Optional[float]
    e_waste_rate: Optional[float]


@dataclass
class MaterialFlow:
    country_code: str
    year: int
    material: str
    generated_kt: Optional[float]
    recycled_kt: Optional[float]
    landfilled_kt: Optional[float]
    incinerated_kt: Optional[float]
    composted_kt: Optional[float]


@dataclass
class DataSource:
    name: str
    url: str
    description: str
