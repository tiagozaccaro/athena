#!/usr/bin/env bash
# Athena installer for Linux and macOS.
#
#   curl -fsSL https://github.com/tiagozaccaro/athena/releases/latest/download/install.sh | bash
#   curl -fsSL …/install.sh | bash -s -- --version 0.2.0
#
# What it does:
#   1. Linux: installs Docker Engine if missing (skip with --no-runtime).
#      macOS: installs Colima + Docker CLI + Compose with Homebrew if missing.
#   2. Installs uv (https://github.com/astral-sh/uv) if missing.
#   3. Installs the Athena server from the GitHub release with `uv tool install`.
#   4. Registers Athena as a service: systemd on Linux (as root), launchd on macOS (as you).
#
# Windows: use install.ps1 instead.

set -euo pipefail

REPO="tiagozaccaro/athena"
PORT=8420

VERSION=""
DRY_RUN=0
NO_RUNTIME=0
UNINSTALL=0
PURGE=0

usage() {
  cat <<EOF
Athena installer (Linux / macOS)

Usage: install.sh [options]

Options:
  --version <x.y.z>  Install a specific version (default: latest release)
  --no-runtime       Don't install a container runtime (Docker Engine / Colima)
  --dry-run          Print what would be done without changing anything
  --uninstall        Remove Athena (keeps data unless --purge is given)
  --purge            With --uninstall, also delete Athena's data directory
  -h, --help         Show this help
EOF
}

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
has()  { command -v "$1" >/dev/null 2>&1; }

# Runs a command, or only prints it with --dry-run.
run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --version) [ $# -ge 2 ] || die "--version needs a value"; VERSION="${2#v}"; shift 2 ;;
      --no-runtime) NO_RUNTIME=1; shift ;;
      --dry-run) DRY_RUN=1; shift ;;
      --uninstall) UNINSTALL=1; shift ;;
      --purge) PURGE=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1 (see --help)" ;;
    esac
  done
}

detect_platform() {
  OS="$(uname -s)"
  ARCH="$(uname -m)"
  case "$OS" in
    Linux)
      OS=linux
      DISTRO="unknown"
      if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        DISTRO="$(. /etc/os-release && echo "${ID:-unknown}")"
      fi
      INSTALL_ROOT="/opt/athena"
      DATA_DIR="/var/lib/athena"
      BIN_DIR="/usr/local/bin"
      ;;
    Darwin)
      OS=darwin
      DISTRO="macos-$(sw_vers -productVersion 2>/dev/null || echo unknown)"
      INSTALL_ROOT="$HOME/.local/share/athena"
      DATA_DIR="$HOME/Library/Application Support/Athena"
      BIN_DIR="$HOME/.local/bin"
      ;;
    *) die "unsupported OS: $OS. On Windows use install.ps1." ;;
  esac
  case "$ARCH" in
    x86_64|amd64) ARCH=amd64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) die "unsupported architecture: $ARCH (amd64 and arm64 are supported)" ;;
  esac
  say "Platform: $OS/$ARCH ($DISTRO)"
}

# Linux runs Athena as a root service; macOS runs it as the logged-in user.
check_privileges() {
  if [ "$OS" = linux ] && [ "$(id -u)" -ne 0 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      warn "not root: a real install on Linux needs root (re-run with sudo)"
    else
      die "on Linux the installer must run as root: curl -fsSL … | sudo bash"
    fi
  fi
  if [ "$OS" = darwin ] && [ "$(id -u)" -eq 0 ]; then
    die "on macOS run the installer as your normal user, not root (Homebrew and Colima are per-user)"
  fi
}

resolve_version() {
  if [ -n "$VERSION" ]; then return; fi
  say "Looking up the latest Athena release"
  has curl || die "curl is required"
  VERSION="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
    | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -n1)" || true
  [ -n "$VERSION" ] || die "no Athena release found yet at https://github.com/$REPO/releases"
}

install_runtime_linux() {
  if has docker; then
    say "Docker found: $(docker --version 2>/dev/null || echo unknown version)"
    return
  fi
  say "Installing Docker Engine"
  case "$DISTRO" in
    ubuntu|debian|raspbian|fedora|centos|rhel|rocky|almalinux)
      # Docker's official convenience script (Moby, Apache-2.0); installs Engine + Compose v2.
      if [ "$DRY_RUN" -eq 1 ]; then
        printf '  [dry-run] curl -fsSL https://get.docker.com | sh\n'
      else
        curl -fsSL https://get.docker.com | sh
      fi
      ;;
    arch|manjaro|endeavouros) run pacman -Sy --noconfirm --needed docker docker-compose ;;
    opensuse*|sles) run zypper --non-interactive install docker docker-compose ;;
    alpine) run apk add --no-cache docker docker-cli-compose ;;
    *) warn "don't know how to install Docker on '$DISTRO'. Install Docker Engine or Podman yourself; Athena will detect it."; return ;;
  esac
  if has systemctl; then
    run systemctl enable --now docker
  elif has rc-update; then
    run rc-update add docker default
    run service docker start
  fi
}

install_runtime_macos() {
  if has colima && has docker; then
    local colima_version
    colima_version="$(colima version 2>/dev/null || true)"
    say "Colima found: ${colima_version%%$'\n'*}"
  else
    has brew || die "Homebrew is required to install Colima: see https://brew.sh, then re-run this installer (or use --no-runtime)"
    say "Installing Colima, Docker CLI and Docker Compose with Homebrew"
    run brew install colima docker docker-compose
    # Make `docker compose` (plugin form) find Homebrew's compose binary.
    run mkdir -p "$HOME/.docker/cli-plugins"
    run ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" "$HOME/.docker/cli-plugins/docker-compose"
  fi
  if has colima && colima status >/dev/null 2>&1; then
    say "Colima is running"
  else
    say "Starting Colima"
    run colima start
  fi
}

install_uv() {
  if has uv; then
    UV="$(command -v uv)"
    say "uv found: $("$UV" --version)"
    return
  fi
  say "Installing uv"
  run mkdir -p "$INSTALL_ROOT/bin"
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  [dry-run] curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=%s UV_NO_MODIFY_PATH=1 sh\n' "$INSTALL_ROOT/bin"
  else
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$INSTALL_ROOT/bin" UV_NO_MODIFY_PATH=1 sh
  fi
  UV="$INSTALL_ROOT/bin/uv"
}

# Keeps Athena's Python, tools and entry point in Athena-owned directories.
uv_env() {
  export UV_TOOL_DIR="$INSTALL_ROOT/tools"
  export UV_TOOL_BIN_DIR="$BIN_DIR"
  export UV_PYTHON_INSTALL_DIR="$INSTALL_ROOT/python"
}

install_athena() {
  local wheel="athena_server-$VERSION-py3-none-any.whl"
  local url="https://github.com/$REPO/releases/download/v$VERSION/$wheel"
  say "Installing Athena $VERSION"
  uv_env
  run mkdir -p "$BIN_DIR" "$DATA_DIR"
  run "$UV" tool install --force --python 3.13 "athena-server @ $url"
  say "Registering the Athena service"
  run "$BIN_DIR/athena" service install --data-dir "$DATA_DIR" --port "$PORT"
}

uninstall_athena() {
  say "Uninstalling Athena"
  uv_env
  if [ -x "$BIN_DIR/athena" ] || [ "$DRY_RUN" -eq 1 ]; then
    run "$BIN_DIR/athena" service uninstall || true
  fi
  if has uv || [ -x "$INSTALL_ROOT/bin/uv" ]; then
    UV="$(command -v uv || echo "$INSTALL_ROOT/bin/uv")"
    run "$UV" tool uninstall athena-server || true
  fi
  run rm -rf "$INSTALL_ROOT"
  if [ "$PURGE" -eq 1 ]; then
    say "Deleting data in $DATA_DIR"
    run rm -rf "$DATA_DIR"
  else
    say "Kept your data in $DATA_DIR (use --uninstall --purge to delete it)"
  fi
  say "Athena was removed. The container runtime was left installed."
}

print_done() {
  local ip=""
  if [ "$OS" = linux ]; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')" || true
  else
    ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    say "Dry run finished. Athena $VERSION would be served at http://${ip:-localhost}:$PORT"
    return
  fi
  say "Athena $VERSION is installed."
  printf '\n  Open: http://%s:%s\n\n' "${ip:-localhost}" "$PORT"
}

main() {
  parse_args "$@"
  detect_platform
  check_privileges
  if [ "$DRY_RUN" -eq 1 ]; then say "Dry run: nothing will be changed"; fi
  if [ "$UNINSTALL" -eq 1 ]; then
    uninstall_athena
    return
  fi
  resolve_version
  if [ "$NO_RUNTIME" -eq 0 ]; then
    if [ "$OS" = linux ]; then install_runtime_linux; else install_runtime_macos; fi
  fi
  install_uv
  install_athena
  print_done
}

# Everything is inside main so a partially downloaded script never runs half-way.
main "$@"
