"""SQLAlchemy + PostGIS models and read repository for geo reference data."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from geoalchemy2 import Geography, Geometry
from geoalchemy2.elements import WKBElement
from geoalchemy2.functions import ST_Contains, ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from sqlalchemy import ARRAY, ForeignKey, Integer, String, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.geo.domain import AttractionCategory, AttractionStop, Precinct, Segment
from safetour.shared.database import Base


class PrecinctModel(Base):
    __tablename__ = "precincts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    boundary: Mapped[WKBElement] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)


class SegmentModel(Base):
    __tablename__ = "segments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    precinct_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("precincts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    modes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    geometry: Mapped[WKBElement] = mapped_column(Geometry("LINESTRING", srid=4326), nullable=False)


class AttractionStopModel(Base):
    __tablename__ = "attractions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    precinct_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("precincts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    opening_hours: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    location: Mapped[WKBElement] = mapped_column(Geometry("POINT", srid=4326), nullable=False)


def _precinct_entity(row: PrecinctModel) -> Precinct:
    return Precinct(id=row.id, name=row.name, boundary=to_shape(row.boundary), population=row.population)


def _segment_entity(row: SegmentModel) -> Segment:
    return Segment(id=row.id, precinct_id=row.precinct_id, geometry=to_shape(row.geometry), modes=list(row.modes))


def _attraction_entity(row: AttractionStopModel) -> AttractionStop:
    return AttractionStop(
        id=row.id,
        name=row.name,
        category=AttractionCategory(row.category),
        location=cast(Point, to_shape(row.location)),
        precinct_id=row.precinct_id,
        opening_hours=row.opening_hours,
    )


class SqlAlchemyGeoReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_precinct(self, precinct_id: UUID) -> Precinct | None:
        row = await self._session.get(PrecinctModel, precinct_id)
        return _precinct_entity(row) if row else None

    async def list_precincts(self) -> list[Precinct]:
        result = await self._session.execute(select(PrecinctModel))
        return [_precinct_entity(r) for r in result.scalars().all()]

    async def find_precinct_for_point(self, lon: float, lat: float) -> Precinct | None:
        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        result = await self._session.execute(
            select(PrecinctModel).where(ST_Contains(PrecinctModel.boundary, point)).limit(1)
        )
        row = result.scalar_one_or_none()
        return _precinct_entity(row) if row else None

    async def find_nearest_segment(self, lon: float, lat: float, *, mode: str | None = None) -> Segment | None:
        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        query = select(SegmentModel)
        if mode is not None:
            query = query.where(SegmentModel.modes.contains([mode]))
        query = query.order_by(ST_Distance(SegmentModel.geometry, point)).limit(1)
        result = await self._session.execute(query)
        row = result.scalar_one_or_none()
        return _segment_entity(row) if row else None

    async def list_segments_in_precinct(self, precinct_id: UUID) -> list[Segment]:
        result = await self._session.execute(select(SegmentModel).where(SegmentModel.precinct_id == precinct_id))
        return [_segment_entity(r) for r in result.scalars().all()]

    async def list_attractions(
        self,
        *,
        precinct_id: UUID | None = None,
        category: AttractionCategory | None = None,
        near: tuple[float, float] | None = None,
        radius_m: float = 2000.0,
        limit: int = 50,
    ) -> list[AttractionStop]:
        query = select(AttractionStopModel)
        if precinct_id is not None:
            query = query.where(AttractionStopModel.precinct_id == precinct_id)
        if category is not None:
            query = query.where(AttractionStopModel.category == category.value)
        if near is not None:
            lon, lat = near
            point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
            point_geog = sql_cast(point, Geography)
            location_geog = sql_cast(AttractionStopModel.location, Geography)
            query = query.where(ST_DWithin(location_geog, point_geog, radius_m))
            query = query.order_by(ST_Distance(location_geog, point_geog))
        query = query.limit(limit)
        result = await self._session.execute(query)
        return [_attraction_entity(r) for r in result.scalars().all()]

    async def get_attraction(self, attraction_id: UUID) -> AttractionStop | None:
        row = await self._session.get(AttractionStopModel, attraction_id)
        return _attraction_entity(row) if row else None


def shape_to_geometry(shape: BaseGeometry, srid: int = 4326) -> WKBElement:
    """Convert a shapely geometry into a WKBElement for writing to a Geometry column."""
    return from_shape(shape, srid=srid)
