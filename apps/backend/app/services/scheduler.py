import asyncio
import logging

from app.core.config import Settings
from app.services.sync import SyncService

logger = logging.getLogger(__name__)


class SyncScheduler:
    def __init__(self, sync_service: SyncService, settings: Settings) -> None:
        self.sync_service = sync_service
        self.settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        await asyncio.to_thread(self.sync_service.run_startup_sync)
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def _run_loop(self) -> None:
        logger.info("Sync scheduler started")
        while not self._stop.is_set():
            await asyncio.to_thread(self.sync_service.ensure_periodic_task)
            processed = await asyncio.to_thread(self.sync_service.process_next_task)
            delay = (
                self.settings.sync_poll_seconds
                if processed
                else max(self.settings.sync_poll_seconds, 10)
            )
            await asyncio.sleep(delay)
