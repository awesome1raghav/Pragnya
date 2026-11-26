"""FastAPI dependencies shared by route modules."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from Backend.App.Config import Settings
from Backend.App.Storage.LocalStorage import LocalStorage


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.settings


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_db_session(request: Request) -> Iterator[Session]:
    """One session per request; services commit explicitly, anything uncommitted rolls back."""
    with request.app.state.session_factory() as session:
        yield session


def get_storage(request: Request) -> LocalStorage:
    return request.app.state.storage


def get_actor(request: Request) -> str:
    """The acting operator. Comes from server configuration, never from the request body."""
    return request.app.state.settings.OPERATOR_NAME
