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
    Path(args.data_dir).mkdir(parents=True, exist_ok=True)
    uvicorn.run(
        "athena.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _openapi(args: argparse.Namespace) -> int:
    from athena.main import create_app

    schema = json.dumps(create_app().openapi(), indent=2) + "\n"
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

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
