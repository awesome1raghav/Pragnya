"""Creates (or with --reset, recreates) the isolated browser-test database nextron_e2e and prints its URL.

Used by Scripts/Testing/StartE2EStack.ps1. It only ever touches the database named nextron_e2e.
"""

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from Backend.App.Config import get_settings

NAME = "nextron_e2e"
server = make_url(get_settings().DATABASE_URL)
admin = create_engine(server.set(database="postgres"), isolation_level="AUTOCOMMIT")
with admin.connect() as c:
    if "--reset" in sys.argv:
        c.execute(text(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)"))
    if not c.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": NAME}).first():
        c.execute(text(f"CREATE DATABASE {NAME}"))
admin.dispose()
print(server.set(database=NAME).render_as_string(hide_password=False))
