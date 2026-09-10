from safetour.modules.geo.models import SqlAlchemyGeoReadRepository
from safetour.shared.dependencies import DbSession


def get_geo_repository(db: DbSession) -> SqlAlchemyGeoReadRepository:
    return SqlAlchemyGeoReadRepository(db)
