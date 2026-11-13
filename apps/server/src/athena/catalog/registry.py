"""All catalogs Athena knows about: the built-in one plus downloaded remote catalogs."""

import logging
from pathlib import Path

from athena.catalog.loader import builtin_catalog_dir, load_catalog
from athena.catalog.model import CatalogApp

log = logging.getLogger(__name__)

BUILTIN = "builtin"


class CatalogRegistry:
    def __init__(
        self, apps: list[CatalogApp] | None = None, remote_root: Path | None = None
    ) -> None:
        self.remote_root = remote_root
        self._fixed = apps
        self._apps: dict[tuple[str, str], CatalogApp] = {}
        self.errors: dict[str, list[str]] = {}
        self.reload()

    def reload(self) -> None:
        """(Re)load the built-in catalog and every downloaded catalog folder."""
        if self._fixed is not None:
            self._apps = {(a.catalog, a.id): a for a in self._fixed}
            return
        apps: list[CatalogApp] = []
        root = builtin_catalog_dir()
        if root is None:
            log.warning("built-in catalog not found")
        else:
            loaded, self.errors[BUILTIN] = load_catalog(root, BUILTIN)
            apps += loaded
        if self.remote_root and self.remote_root.is_dir():
            for folder in sorted(self.remote_root.iterdir()):
                if folder.is_dir() and not folder.name.startswith("."):
                    loaded, self.errors[folder.name] = load_catalog(folder, folder.name)
                    apps += loaded
        self._apps = {(a.catalog, a.id): a for a in apps}
        log.info("loaded %d catalog apps", len(self._apps))

    def all(self) -> list[CatalogApp]:
        return sorted(self._apps.values(), key=lambda a: (a.meta.title.lower(), a.catalog))

    def get(self, catalog: str, app_id: str) -> CatalogApp | None:
        return self._apps.get((catalog, app_id))

    def count(self, catalog: str) -> int:
        return sum(1 for (c, _) in self._apps if c == catalog)
