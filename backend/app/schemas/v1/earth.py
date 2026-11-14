from pydantic import BaseModel


class EarthCell(BaseModel):
    lat: float
    lon: float
    distance_km: float
    elevation_m: float | None
    slope_deg: float
    roughness_m: float
    tmin_c: float | None
    ice_thickness_m: float
    rock: str


class SearchPoint(BaseModel):
    lat: float
    lon: float
    closeness: float
    rock: str


class SearchQuery(BaseModel):
    slope: float
    roughness: float
    tmin: float
    ice: float
    rock: float
    precision: str


class SearchResponse(BaseModel):
    returned: float
    min_closeness: float
    closest: float | None
    loosest: float | None
    temperature_mode: str
    points: list[SearchPoint]
