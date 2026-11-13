"""The `athena` command."""

import argparse
import json
import os
import sys
from pathlib import Path

from athena import __version__
from athena.config import DEFAULT_PORT, default_data_dir


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    # Settings are read from the environment so they also reach the --reload worker.
    os.environ["ATHENA_HOST"] = args.host
    os.environ["ATHENA_PORT"] = str(args.port)
    os.environ["ATHENA_DATA_DIR"] = str(args.data_dir)
    os.environ["ATHENA_LOG_TO_FILE"] = "1"
    Path(args.data_dir).mkdir(parents=True, exist_ok=True)
    uvicorn.run(
        "athena.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,  # athena.logging_setup configures logging in create_app
    )
    return 0


def _openapi(args: argparse.Namespace) -> int:
    import tempfile

    from athena.config import Settings
    from athena.main import create_app

    # Exporting the schema must not touch the real data dir (e.g. /var/lib/athena,
    # which needs root), so build the app against a throwaway one.
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(data_dir=Path(tmp)))
        schema = json.dumps(app.openapi(), indent=2) + "\n"
        app.state.db.engine.dispose()  # release the SQLite file so Windows can delete it
    if args.output:
        Path(args.output).write_text(schema, encoding="utf-8")
    else:
        sys.stdout.write(schema)
    return 0


def _service(args: argparse.Namespace) -> int:
    from athena.service import ServiceSpec, build_install, build_status, build_uninstall, execute
    from athena.service.platforms import UnsupportedPlatformError

    try:
        if args.service_command == "install":
            if sys.platform.startswith("linux") and os.geteuid() != 0 and not args.dry_run:  # type: ignore[attr-defined]
                print(
                    "error: on Linux the Athena service is installed as root (use sudo)",
                    file=sys.stderr,
                )
                return 1
            spec = ServiceSpec(
                python=Path(sys.executable), data_dir=Path(args.data_dir), port=args.port
            )
            plan = build_install(spec)
        elif args.service_command == "uninstall":
            plan = build_uninstall()
        else:
            plan = build_status()
    except UnsupportedPlatformError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return execute(plan, dry_run=getattr(args, "dry_run", False))


def _read_new_password(args: argparse.Namespace) -> str | None:
    if args.password_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    import getpass

    first = getpass.getpass("New password: ")
    if first != getpass.getpass("Repeat password: "):
        print("error: passwords don't match", file=sys.stderr)
        return None
    return first


def _reset_password(args: argparse.Namespace) -> int:
    """Recovery for a forgotten admin password. Runs on the server, as the service's user."""
    from sqlalchemy.exc import OperationalError
    from sqlmodel import Session, select

    from athena.auth.service import MIN_PASSWORD_LENGTH, set_password
    from athena.db import Database, User

    db_path = Path(args.data_dir) / "athena.db"
    if not db_path.is_file():
        print(
            f"error: no Athena database at {db_path}. Pass --data-dir, or finish setup "
            "in the web UI first.",
            file=sys.stderr,
        )
        return 1
    database = Database(db_path)
    try:
        database.migrate()
        with Session(database.engine) as db:
            users = db.exec(select(User)).all()
            if args.username:
                user = next((u for u in users if u.username == args.username), None)
            elif len(users) == 1:
                user = users[0]
            else:
                names = ", ".join(u.username for u in users) or "none"
                print(f"error: pass --username (accounts: {names})", file=sys.stderr)
                return 1
            if user is None:
                print(f"error: no account named {args.username!r}", file=sys.stderr)
                return 1
            password = _read_new_password(args)
            if password is None:
                return 1
            if len(password) < MIN_PASSWORD_LENGTH:
                print(
                    f"error: password must be at least {MIN_PASSWORD_LENGTH} characters",
                    file=sys.stderr,
                )
                return 1
            set_password(db, user, password)
            print(f"Password for {user.username!r} reset. All of its sessions were signed out.")
            return 0
    except (OperationalError, PermissionError) as exc:
        hint = " (run it with sudo, as the service runs as root)" if os.name == "posix" else ""
        print(f"error: can't open {db_path}: {exc}{hint}", file=sys.stderr)
        return 1
    finally:
        database.engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="athena", description="Athena home server")
    parser.add_argument("--version", action="version", version=f"athena {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.add_argument("--data-dir", type=Path, default=default_data_dir())
    serve.add_argument("--reload", action="store_true", help="reload on code changes (development)")
    serve.set_defaults(func=_serve)

    openapi = sub.add_parser("openapi", help="print or write the OpenAPI schema")
    openapi.add_argument("--output", "-o", type=Path)
    openapi.set_defaults(func=_openapi)

    service = sub.add_parser("service", help="manage the Athena system service")
    service_sub = service.add_subparsers(dest="service_command", required=True)
    install = service_sub.add_parser("install", help="register Athena to start automatically")
    install.add_argument("--data-dir", type=Path, default=default_data_dir())
    install.add_argument("--port", type=int, default=DEFAULT_PORT)
    install.add_argument("--dry-run", action="store_true")
    uninstall = service_sub.add_parser("uninstall", help="remove the registration")
    uninstall.add_argument("--dry-run", action="store_true")
    service_sub.add_parser("status", help="show service status")
    service.set_defaults(func=_service)

    admin = sub.add_parser("admin", help="account recovery")
    admin_sub = admin.add_subparsers(dest="admin_command", required=True)
    reset = admin_sub.add_parser(
        "reset-password",
        help="set a new password for an account (signs it out everywhere)",
    )
    reset.add_argument("--data-dir", type=Path, default=default_data_dir())
    reset.add_argument("--username", help="needed only when there's more than one account")
    reset.add_argument(
        "--password-stdin", action="store_true", help="read the new password from stdin"
    )
    reset.set_defaults(func=_reset_password)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
