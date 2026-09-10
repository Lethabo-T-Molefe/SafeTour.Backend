from safetour.modules.users.models import SqlAlchemyProfileRepository
from safetour.modules.users.service import ProfileService
from safetour.shared.dependencies import DbSession


def get_profile_service(db: DbSession) -> ProfileService:
    return ProfileService(profiles=SqlAlchemyProfileRepository(db))
