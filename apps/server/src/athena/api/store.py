"""The app store: browse catalogs and install apps. All routes need a session."""

import asyncio
import re
import shutil
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field
from sqlmodel import select

from athena import audit
from athena.api.apps import deploy_new_app
from athena.api.containers import RuntimeDep
from athena.apps.store import APP_NAME, AppStore
from athena.auth.deps import Authed, DbSession
from athena.catalog import remote
from athena.catalog.loader import (
    InstallValueError,
    env_file,
    form_defaults,
    resolve_values,
)
from athena.catalog.model import APP_ID, CATEGORY_LABELS, CatalogApp, EnvField, FieldType
from athena.catalog.registry import BUILTIN, CatalogRegistry
from athena.db.models import App, Catalog
from athena.jobs import Job, JobManager, JobOut

router = APIRouter(prefix="/store", tags=["store"])

CatalogName = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")]
AppId = Annotated[str, Path(pattern=APP_ID)]


class Category(BaseModel):
    id: str
    label: str
    count: int


class StoreApp(BaseModel):
    catalog: str
    catalog_name: str
    id: str
    title: str
    description: str
    category: str
    icon: str | None
    installed: list[str]
    """Names of Athena apps installed from this catalog app."""


class FormField(BaseModel):
    key: str
    label: str
    description: str | None
    type: FieldType
    default: str
    """Resolved default for the suggested app name (passwords: empty, generated on install)."""
    required: bool
    options: list[str] | None
    generated: bool
    advanced: bool


class StoreAppDetail(StoreApp):
    homepage: str | None
    notes: str | None
    platforms: list[str]
    images: list[str]
    web_port: str | int | None
    suggested_name: str
    fields: list[FormField]
    compose: str


class InstallIn(BaseModel):
    name: str = Field(pattern=APP_NAME, max_length=63)
    values: dict[str, str] = Field(default_factory=dict)


def _registry(request: Request) -> CatalogRegistry:
    return request.app.state.catalogs


def _get(request: Request, catalog: str, app_id: str) -> CatalogApp:
    app = _registry(request).get(catalog, app_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No store app {catalog}/{app_id}")
    return app


def _installed(db: DbSession) -> dict[str, list[str]]:
    by_catalog_id: dict[str, list[str]] = {}
    for app in db.exec(select(App).where(App.catalog_id.is_not(None))).all():  # type: ignore[union-attr]
        by_catalog_id.setdefault(app.catalog_id or "", []).append(app.name)
    return by_catalog_id


def _catalog_names(db: DbSession) -> dict[str, str]:
    return {BUILTIN: "Athena", **{c.id: c.name for c in db.exec(select(Catalog)).all()}}


def _summary(
    app: CatalogApp, installed: dict[str, list[str]], names: dict[str, str] | None = None
) -> StoreApp:
    return StoreApp(
        catalog=app.catalog,
        catalog_name=(names or {}).get(app.catalog, app.catalog),
        id=app.id,
        title=app.meta.title,
        description=app.meta.description,
        category=app.meta.category,
        icon=app.meta.icon,
        installed=sorted(installed.get(f"{app.catalog}/{app.id}", [])),
    )


def _field(f: EnvField, default: str) -> FormField:
    return FormField(
        key=f.key,
        label=f.label,
        description=f.description,
        type=f.type,
        default="" if f.generate == "secret" else default,
        required=f.required and f.generate != "secret",
        options=f.options,
        generated=f.generate == "secret",
        advanced=f.advanced,
    )


@router.get("/categories", operation_id="listStoreCategories")
def categories(request: Request) -> list[Category]:
    counts: dict[str, int] = {}
    for app in _registry(request).all():
        counts[app.meta.category] = counts.get(app.meta.category, 0) + 1
    return [
        Category(id=cat, label=label, count=counts[cat])
        for cat, label in CATEGORY_LABELS.items()
        if counts.get(cat)
    ]


@router.get("/apps", operation_id="listStoreApps")
def list_store_apps(
    request: Request,
    db: DbSession,
    q: Annotated[str, Query(max_length=100)] = "",
    category: Annotated[str | None, Query(max_length=32)] = None,
) -> list[StoreApp]:
    needle = q.strip().lower()
    installed = _installed(db)
    names = _catalog_names(db)
    return [
        _summary(app, installed, names)
        for app in _registry(request).all()
        if (category is None or app.meta.category == category)
        and (
            not needle
            or needle in app.meta.title.lower()
            or needle in app.meta.description.lower()
            or needle in app.id
        )
    ]


@router.get("/apps/{catalog}/{app_id}", operation_id="getStoreApp")
def get_store_app(
    catalog: CatalogName, app_id: AppId, request: Request, db: DbSession
) -> StoreAppDetail:
    app = _get(request, catalog, app_id)
    taken = {a.name for a in db.exec(select(App)).all()}
    name, n = app.id, 2
    while name in taken:
        name, n = f"{app.id}-{n}", n + 1
    data_dir = AppStore(request.app.state.settings.data_dir).dir(name) / "data"
    defaults = form_defaults(app, data_dir)
    return StoreAppDetail(
        **_summary(app, _installed(db), _catalog_names(db)).model_dump(),
        homepage=app.meta.homepage,
        notes=app.meta.notes,
        platforms=app.meta.platforms,
        images=app.images,
        web_port=app.meta.web_port,
        suggested_name=name,
        fields=[_field(f, defaults[f.key]) for f in app.meta.env],
        compose=app.compose,
    )


@router.post(
    "/apps/{catalog}/{app_id}/install",
    operation_id="installStoreApp",
    status_code=status.HTTP_202_ACCEPTED,
    responses={422: {"description": "Invalid values: detail.errors maps field keys to messages"}},
)
async def install(
    catalog: CatalogName,
    app_id: AppId,
    body: InstallIn,
    request: Request,
    runtime: RuntimeDep,
    user: Authed,
    db: DbSession,
) -> JobOut:
    """Write compose.yaml and .env from the install form, then deploy as a job."""
    app = _get(request, catalog, app_id)
    data_dir = AppStore(request.app.state.settings.data_dir).dir(body.name) / "data"
    try:
        values = resolve_values(app, body.values, data_dir)
    except InstallValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": "Some values need fixing", "errors": exc.errors},
        ) from exc
    return deploy_new_app(
        request,
        runtime,
        user,
        db,
        name=body.name,
        compose_text=app.compose,
        source="catalog",
        env_text=env_file(values),
        catalog_id=f"{app.catalog}/{app.id}",
    )


# ---------------------------------------------------------------- catalogs

CatalogKind = Literal["auto", "athena", "casaos"]


class CatalogOut(BaseModel):
    id: str
    name: str
    url: str | None
    kind: str
    builtin: bool
    app_count: int
    refreshed_at: datetime | None
    error: str | None


class NewCatalog(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=500)
    kind: CatalogKind = "auto"


def _catalog_dir(request: Request, catalog_id: str):
    return request.app.state.settings.data_dir / "catalogs" / catalog_id


def _slug(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "catalog"
    if base == BUILTIN:
        base = "builtin-2"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


def _catalog_out(row: Catalog) -> CatalogOut:
    return CatalogOut(
        id=row.id,
        name=row.name,
        url=row.url,
        kind=row.kind,
        builtin=False,
        app_count=row.app_count,
        refreshed_at=row.refreshed_at,
        error=row.error,
    )


def _refresh_job(request: Request, row: Catalog) -> JobOut:
    jobs: JobManager = request.app.state.jobs
    registry = _registry(request)
    database = request.app.state.db
    dest = _catalog_dir(request, row.id)
    catalog_id, url, kind = row.id, row.url, row.kind

    async def body(job: Job) -> None:
        loop = asyncio.get_running_loop()

        def log(line: str) -> None:
            asyncio.run_coroutine_threadsafe(job.log(line), loop)

        error: str | None = None
        count = 0
        try:
            count = await asyncio.to_thread(remote.refresh, url, kind, catalog_id, dest, log)
        except (remote.CatalogFetchError, ValueError) as exc:
            error = str(exc)
        registry.reload()
        with database.engine.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE catalogs SET app_count = ?, refreshed_at = ?, error = ? WHERE id = ?",
                (registry.count(catalog_id), datetime.now(UTC).isoformat(), error, catalog_id),
            )
        if error:
            raise RuntimeError(error)
        await job.log(f"Store now lists {count} apps from {catalog_id}")

    return jobs.start(f"Refresh catalog {row.name}", body).out()


@router.get("/catalogs", operation_id="listCatalogs")
def list_catalogs(request: Request, db: DbSession) -> list[CatalogOut]:
    builtin = CatalogOut(
        id=BUILTIN,
        name="Athena",
        url=None,
        kind="athena",
        builtin=True,
        app_count=_registry(request).count(BUILTIN),
        refreshed_at=None,
        error=None,
    )
    rows = db.exec(select(Catalog).order_by(Catalog.created_at)).all()
    return [builtin, *(_catalog_out(r) for r in rows)]


@router.post("/catalogs", operation_id="addCatalog", status_code=status.HTTP_202_ACCEPTED)
async def add_catalog(body: NewCatalog, request: Request, user: Authed, db: DbSession) -> JobOut:
    """Add a remote catalog and download it (a job). GitHub, Codeberg and GitLab repository
    URLs work, as do direct .tar.gz/.zip links. Format: Athena or CasaOS AppStore."""
    try:
        remote.archive_url(body.url)
    except remote.CatalogFetchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if db.exec(select(Catalog).where(Catalog.url == body.url.strip())).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That catalog is already added")
    taken = {c.id for c in db.exec(select(Catalog)).all()}
    row = Catalog(
        id=_slug(body.name, taken), name=body.name.strip(), url=body.url.strip(), kind=body.kind
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit.record(db, user.user.username, "catalog.add", row.id, row.url)
    return _refresh_job(request, row)


@router.post(
    "/catalogs/{catalog_id}/refresh",
    operation_id="refreshCatalog",
    status_code=status.HTTP_202_ACCEPTED,
)
async def refresh_catalog(
    catalog_id: CatalogName, request: Request, user: Authed, db: DbSession
) -> JobOut:
    row = db.get(Catalog, catalog_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such catalog")
    audit.record(db, user.user.username, "catalog.refresh", row.id)
    return _refresh_job(request, row)


@router.delete(
    "/catalogs/{catalog_id}", operation_id="removeCatalog", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_catalog(
    catalog_id: CatalogName, request: Request, user: Authed, db: DbSession
) -> None:
    """Forget a catalog. Apps already installed from it keep running."""
    row = db.get(Catalog, catalog_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such catalog")
    db.delete(row)
    db.commit()
    shutil.rmtree(_catalog_dir(request, catalog_id), ignore_errors=True)
    _registry(request).reload()
    audit.record(db, user.user.username, "catalog.remove", catalog_id)
