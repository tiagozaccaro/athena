"""Keeps the latest manifest. Detection runs at startup and on refresh, off the event loop."""

import asyncio
import logging
from collections.abc import Callable

from athena.platform.capabilities import CapabilityManifest
from athena.platform.detect import detect

log = logging.getLogger(__name__)


class CapabilityStore:
    def __init__(self, detector: Callable[[], CapabilityManifest] = detect) -> None:
        self._detector = detector
        self._manifest: CapabilityManifest | None = None
        self._lock = asyncio.Lock()

    async def _detect_locked(self) -> CapabilityManifest:
        manifest = await asyncio.to_thread(self._detector)
        self._manifest = manifest
        ready = [c.id for c in manifest.capabilities if c.available]
        log.info("capabilities detected: %s", ", ".join(ready) or "none")
        return manifest

    async def refresh(self) -> CapabilityManifest:
        async with self._lock:
            return await self._detect_locked()

    async def get(self) -> CapabilityManifest:
        if self._manifest is not None:
            return self._manifest
        async with self._lock:
            # Startup detection may have finished while we waited for the lock.
            if self._manifest is not None:
                return self._manifest
            return await self._detect_locked()
