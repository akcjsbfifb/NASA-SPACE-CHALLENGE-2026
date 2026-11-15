from fastapi import APIRouter, Query
from app.schemas.v1 import EarthCell, SearchQuery, SearchResponse

router = APIRouter(prefix="/earth", tags=["earth"])


@router.get("/cell", responseModel=EarthCell)
def cell():
    return {}


@router.get("/search", responseModel=SearchResponse)
def search(params: SearchQuery = Query(0.0, 0.0, 0.0, 0.0, 0.0, "")):
    return {}
