from pathlib import Path

from alembic.config import Config

from alembic import command
from app.core.config import Settings


def run_migrations(settings: Settings) -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_ini = backend_dir / "alembic.ini"
    alembic_dir = backend_dir / "alembic"

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
