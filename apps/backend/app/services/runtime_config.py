from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AppConfig


@dataclass
class EffectiveRuntimeConfig:
    notion_token: str
    notion_root_page_id: str
    notion_use_fixtures: bool
    notion_fixture_path: str

    @property
    def has_minimum_sync_config(self) -> bool:
        if not self.notion_root_page_id:
            return False
        if self.notion_use_fixtures:
            return bool(self.notion_fixture_path)
        return bool(self.notion_token)


@dataclass
class AdminRuntimeConfig:
    notion_root_page_id: str
    has_notion_token: bool
    notion_use_fixtures: bool
    notion_fixture_path: str
    configured_via_db: bool


class RuntimeConfigService:
    SINGLETON_ID = 1

    def get_effective_config(self, session: Session, settings: Settings) -> EffectiveRuntimeConfig:
        row = session.get(AppConfig, self.SINGLETON_ID)

        notion_token = ((row.notion_token if row else "") or settings.notion_token or "").strip()
        notion_root_page_id = (
            (row.notion_root_page_id if row else "") or settings.notion_root_page_id or ""
        ).strip()

        if row and row.notion_use_fixtures is not None:
            notion_use_fixtures = row.notion_use_fixtures
        else:
            notion_use_fixtures = settings.notion_use_fixtures

        notion_fixture_path = (
            (row.notion_fixture_path if row else "") or settings.notion_fixture_path or ""
        ).strip()

        return EffectiveRuntimeConfig(
            notion_token=notion_token,
            notion_root_page_id=notion_root_page_id,
            notion_use_fixtures=notion_use_fixtures,
            notion_fixture_path=notion_fixture_path,
        )

    def get_admin_config(self, session: Session, settings: Settings) -> AdminRuntimeConfig:
        row = session.get(AppConfig, self.SINGLETON_ID)
        effective = self.get_effective_config(session, settings)
        configured_via_db = row is not None and any(
            [
                bool(row.notion_token),
                bool(row.notion_root_page_id),
                row.notion_use_fixtures is not None,
                bool(row.notion_fixture_path),
            ]
        )

        return AdminRuntimeConfig(
            notion_root_page_id=effective.notion_root_page_id,
            has_notion_token=bool(effective.notion_token),
            notion_use_fixtures=effective.notion_use_fixtures,
            notion_fixture_path=effective.notion_fixture_path,
            configured_via_db=configured_via_db,
        )

    def update_admin_config(
        self,
        session: Session,
        *,
        notion_token: str | None,
        notion_root_page_id: str | None,
        notion_use_fixtures: bool | None,
        notion_fixture_path: str | None,
        clear_notion_token: bool,
    ) -> AppConfig:
        row = session.get(AppConfig, self.SINGLETON_ID)
        if not row:
            row = AppConfig(id=self.SINGLETON_ID)
            session.add(row)

        if clear_notion_token:
            row.notion_token = None
        elif notion_token is not None:
            cleaned = notion_token.strip()
            row.notion_token = cleaned or None

        if notion_root_page_id is not None:
            cleaned_root = notion_root_page_id.strip()
            row.notion_root_page_id = cleaned_root or None

        if notion_use_fixtures is not None:
            row.notion_use_fixtures = notion_use_fixtures

        if notion_fixture_path is not None:
            cleaned_path = notion_fixture_path.strip()
            row.notion_fixture_path = cleaned_path or None

        session.commit()
        session.refresh(row)
        return row
