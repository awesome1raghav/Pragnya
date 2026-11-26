"""Preferences API (Step 8): the operator's settings, applied by the backend, with optimistic concurrency."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Dependencies import get_db_session, get_settings_dependency
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Services import Preferences

router = APIRouter(tags=["Preferences"])


class PreferencesPatch(BaseModel):
    version: int = Field(ge=0, description="The version this change is based on (from GET /preferences)")
    preferences: dict = Field(description="Only the sections and fields to change, e.g. {\"notifications\": {\"runs_completed\": false}}")


@router.get("/preferences", response_model=SuccessEnvelope[Preferences.PreferencesRead], summary="The operator's preferences")
def get_preferences(session: Session = Depends(get_db_session), settings: Settings = Depends(get_settings_dependency)):
    return envelope(Preferences.read(session, settings), "Preferences retrieved successfully")


@router.patch("/preferences", response_model=SuccessEnvelope[Preferences.PreferencesRead],
              responses={409: {"model": ErrorEnvelope, "description": "PREFERENCES_CONFLICT: changed since `version`"},
                         422: {"model": ErrorEnvelope, "description": "Unknown or invalid preference"}},
              summary="Change preferences (refused if they changed since `version`)")
def patch_preferences(body: PreferencesPatch, session: Session = Depends(get_db_session), settings: Settings = Depends(get_settings_dependency)):
    result = Preferences.update(session, settings, expected_version=body.version, patch=body.preferences)
    return envelope(result, f"Preferences saved (version {result.version})")
