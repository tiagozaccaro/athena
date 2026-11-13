"""Remote catalogs: download an archive over HTTPS, extract it safely, and normalize it
into `<data-dir>/catalogs/<id>/apps/<app>/compose.yaml` (the same layout as catalog/).

No git binary is needed: GitHub, Codeberg and GitLab repository URLs are turned into
their archive download URLs. Only YAML is read from the archive; nothing is executed.
"""

import re
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Literal

from athena.catalog.casaos import import_casaos_tree
from athena.catalog.loader import load_catalog

CatalogKind = Literal["auto", "athena", "casaos"]

MAX_DOWNLOAD = 200 * 1024 * 1024  # bytes
MAX_FILES = 50_000
MAX_EXTRACTED = 1024 * 1024 * 1024
USER_AGENT = "athena-catalog-fetcher"

Log = Callable[[str], None]


class CatalogFetchError(RuntimeError):
    pass


_GITHUB = re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/(.+))?/?$")
_FORGE = re.compile(
    r"^https://(codeberg\.org|gitlab\.com)/([^/]+)/([^/]+?)(?:\.git)?(?:/(?:-/)?(?:src/branch|tree)/(.+))?/?$"
)


def archive_url(url: str) -> str:
    """Turn a repository URL into a tarball URL; archive URLs pass through."""
    url = url.strip()
    if not url.startswith("https://"):
        raise CatalogFetchError("Catalog URLs must use https://")
    if m := _GITHUB.match(url):
        owner, repo, ref = m.groups()
        target = f"refs/heads/{ref}" if ref else "HEAD"
        return f"https://github.com/{owner}/{repo}/archive/{target}.tar.gz"
    if m := _FORGE.match(url):
        host, owner, repo, ref = m.groups()
        branch = ref or "main"
        if host == "gitlab.com":
            return f"https://gitlab.com/{owner}/{repo}/-/archive/{branch}/{repo}-{branch}.tar.gz"
        return f"https://codeberg.org/{owner}/{repo}/archive/{branch}.tar.gz"
    if re.search(r"\.(tar\.gz|tgz|zip)(\?.*)?$", url):
        return url
    raise CatalogFetchError(
        "Use a GitHub, Codeberg or GitLab repository URL, or a direct .tar.gz/.zip link"
    )


def download(url: str, dest: Path, log: Log) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, dest.open("wb") as out:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD:
                    raise CatalogFetchError("The archive is larger than 200 MB")
                out.write(chunk)
    except OSError as exc:  # URLError, HTTPError, timeouts
        raise CatalogFetchError(f"Download failed: {exc}") from exc
    log(f"Downloaded {total / 1024 / 1024:.1f} MB")


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def extract(archive: Path, dest: Path) -> Path:
    """Extract with path, size and file-count limits. Returns the content root."""
    dest.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_FILES:
                raise CatalogFetchError("The archive has too many files")
            if sum(i.file_size for i in infos) > MAX_EXTRACTED:
                raise CatalogFetchError("The archive is too large when extracted")
            for info in infos:
                if not _safe_member(info.filename):
                    raise CatalogFetchError(f"Unsafe path in archive: {info.filename}")
            zf.extractall(dest)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            members = tf.getmembers()
            if len(members) > MAX_FILES:
                raise CatalogFetchError("The archive has too many files")
            if sum(m.size for m in members) > MAX_EXTRACTED:
                raise CatalogFetchError("The archive is too large when extracted")
            # filter="data" rejects absolute paths, "..", links outside dest and devices.
            tf.extractall(dest, filter="data")
    else:
        raise CatalogFetchError("The download isn't a .tar.gz or .zip archive")
    entries = [p for p in dest.iterdir() if not p.name.startswith(".")]
    return entries[0] if len(entries) == 1 and entries[0].is_dir() else dest


def find_root(root: Path, max_depth: int = 8) -> tuple[Literal["athena", "casaos"], Path]:
    """Find the folder holding `apps/` (Athena) or `Apps/` (CasaOS), searching downwards,
    since archives may nest it (CasaOS release zips use build/sysroot/…/Apps)."""
    queue = [(root, 0)]
    while queue:
        folder, depth = queue.pop(0)
        if any((folder / "apps").glob("*/compose.yaml")):
            return "athena", folder
        if any((folder / "Apps").glob("*/docker-compose.yml")):
            return "casaos", folder
        if depth < max_depth:
            queue += [
                (child, depth + 1)
                for child in sorted(folder.iterdir())
                if child.is_dir() and not child.name.startswith(".")
            ]
    raise CatalogFetchError(
        "No apps found: expected apps/<id>/compose.yaml (Athena) or "
        "Apps/<Name>/docker-compose.yml (CasaOS)"
    )


def build(root: Path, kind: CatalogKind, catalog_id: str, out: Path, log: Log) -> int:
    """Normalize an extracted catalog into `out/apps/*/compose.yaml`. Returns the app count."""
    found, root = find_root(root)
    actual = found if kind == "auto" else kind
    log(f"Catalog format: {actual}")
    if actual == "casaos":
        _, errors = import_casaos_tree(root, out, catalog_id)
        for error in errors[:20]:
            log(f"skipped {error}")
        if len(errors) > 20:
            log(f"… and {len(errors) - 20} more skipped")
    else:
        for compose_file in sorted((root / "apps").glob("*/compose.yaml")):
            target = out / "apps" / compose_file.parent.name
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(compose_file, target / "compose.yaml")
    apps, errors = load_catalog(out, catalog_id)
    for error in errors[:20]:
        log(f"skipped {error}")
    return len(apps)


def refresh(url: str, kind: CatalogKind, catalog_id: str, dest: Path, log: Log) -> int:
    """Download, extract, normalize, then atomically replace `dest`. Returns the app count."""
    source = archive_url(url)
    log(f"Downloading {source}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent, prefix=".fetch-") as tmp:
        work = Path(tmp)
        archive = work / "archive"
        download(source, archive, log)
        root = extract(archive, work / "src")
        staged = work / "out"
        count = build(root, kind, catalog_id, staged, log)
        if count == 0:
            raise CatalogFetchError("The catalog has no valid apps")
        old = dest.with_name(dest.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if dest.exists():
            dest.rename(old)
        staged.rename(dest)
        shutil.rmtree(old, ignore_errors=True)
    log(f"{count} apps available")
    return count
