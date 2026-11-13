"""All catalogs Athena knows about. M3 part A: the built-in catalog only."""

import logging

from athena.catalog.loader import builtin_catalog_dir, load_catalog
from athena.catalog.model import CatalogApp

log = logging.getLogger(__name__)


class CatalogRegistry:
    def __init__(self, apps: list[CatalogApp] | None = None) -> None:
        self._apps: dict[tuple[str, str], CatalogApp] = {}
        self.errors: list[str] = []
        if apps is not None:
            self._apps = {(a.catalog, a.id): a for a in apps}
            return
        root = builtin_catalog_dir()
        if root is None:
            log.warning("built-in catalog not found; the store will be empty")
            return
        loaded, self.errors = load_catalog(root, "builtin")
        self._apps = {(a.catalog, a.id): a for a in loaded}
        log.info("loaded %d catalog apps", len(self._apps))

    def all(self) -> list[CatalogApp]:
        return sorted(self._apps.values(), key=lambda a: a.meta.title.lower())

    def get(self, catalog: str, app_id: str) -> CatalogApp | None:
        return self._apps.get((catalog, app_id))
