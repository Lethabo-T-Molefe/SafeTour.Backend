"""Read-only geo reference API: precincts (for the map) and attractions/stops."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from shapely.geometry import mapping

from safetour.modules.geo.dependencies import get_geo_repository
from safetour.modules.geo.domain import AttractionCategory
from safetour.modules.geo.models import SqlAlchemyGeoReadRepository
from safetour.modules.geo.schemas import AttractionResponse, PrecinctResponse

router = APIRouter(prefix="/geo", tags=["geo"])

GeoRepoDep = Annotated[SqlAlchemyGeoReadRepository, Depends(get_geo_repository)]


@router.get("/precincts", response_model=list[PrecinctResponse])
async def list_precincts(repo: GeoRepoDep) -> list[PrecinctResponse]:
    precincts = await repo.list_precincts()
    return [
        PrecinctResponse(
            id=p.id, name=p.name, population=p.population, boundary_geojson=mapping(p.boundary)
        )
        for p in precincts
    ]


@router.get("/precincts/{precinct_id}", response_model=PrecinctResponse)
async def get_precinct(precinct_id: UUID, repo: GeoRepoDep) -> PrecinctResponse:
    precinct = await repo.get_precinct(precinct_id)
    if precinct is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Precinct not found")
    return PrecinctResponse(
        id=precinct.id,
        name=precinct.name,
        population=precinct.population,
        boundary_geojson=mapping(precinct.boundary),
    )


@router.get("/attractions", response_model=list[AttractionResponse])
async def list_attractions(
    repo: GeoRepoDep,
    precinct_id: UUID | None = None,
    category: AttractionCategory | None = None,
    near_lon: float | None = Query(default=None),
    near_lat: float | None = Query(default=None),
    radius_m: float = Query(default=2000.0, gt=0, le=20000),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AttractionResponse]:
    near = (near_lon, near_lat) if near_lon is not None and near_lat is not None else None
    stops = await repo.list_attractions(
        precinct_id=precinct_id, category=category, near=near, radius_m=radius_m, limit=limit
    )
    return [
        AttractionResponse(
            id=s.id,
            name=s.name,
            category=s.category,
            is_transport_stop=s.category.is_transport_stop,
            lon=s.location.x,
            lat=s.location.y,
            precinct_id=s.precinct_id,
            opening_hours=s.opening_hours,
        )
        for s in stops
    ]
