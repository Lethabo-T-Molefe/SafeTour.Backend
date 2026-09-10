from typing import Annotated

from fastapi import Depends

from safetour.modules.assistant.service import AssistantService
from safetour.modules.itineraries.dependencies import get_itinerary_service
from safetour.modules.itineraries.service import ItineraryService


def get_assistant_service(
    itineraries: Annotated[ItineraryService, Depends(get_itinerary_service)],
) -> AssistantService:
    return AssistantService(itineraries=itineraries)
