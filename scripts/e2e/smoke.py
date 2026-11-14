# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.65.2"]
# ///
"""Browser smoke test against an installed Athena (the service, not a dev server).

    uv run scripts/e2e/smoke.py --url http://localhost:8420 --out e2e-out \\
        --expect terminal.host --expect containers

The data dir must be fresh: it creates the admin through /setup. It checks:
- first-run setup, sign-out redirect, a wrong password (error shown) and a real sign-in;
- the capability manifest has every --expect id ready (saved to capabilities.json);
- every sidebar page renders with no console errors and no 5xx responses;
- the host terminal runs a command when terminal.host is ready;
- phone width and dark mode render (screenshots only).

Screenshots and a summary land in --out. Exits non-zero on the first failed check.
Install the browser once with: uv run --with playwright==1.65.2 playwright install chromium
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

USER = "admin"
PASSWORD = "e2e-test-pass-1234"  # throwaway; the data dir is deleted afterwards
PAGES = ["/", "/apps/", "/store/", "/packages/", "/containers/", "/terminal/", "/settings/"]


def wait_healthy(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=5) as r:
                if r.status == 200:
                    print(f"healthy: {r.read().decode()}")
                    return
        except OSError as e:
            last = str(e)
        time.sleep(2)
    sys.exit(f"server at {url} not healthy after {timeout:.0f}s: {last}")


class Checks:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.errors: list[str] = []
        self.console: list[str] = []
        self.server_errors: list[str] = []

    def attach(self, page: Page) -> None:
        page.on(
            "console",
            lambda m: self.console.append(f"{page.url}: {m.text}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: self.console.append(f"{page.url}: {e}"))
        page.on(
            "response",
            lambda r: self.server_errors.append(f"{r.status} {r.request.method} {r.url}")
            if r.status >= 500
            else None,
        )

    def shot(self, page: Page, name: str) -> None:
        page.screenshot(path=self.out / f"{name}.png", full_page=True)

    def step(self, name: str, fn) -> None:
        print(f"--> {name}")
        try:
            fn()
        except Exception as e:
            self.errors.append(f"{name}: {e}")
            print(f"    FAILED: {e}")

    def drain(self, where: str) -> None:
        """Turns console errors and 5xx responses seen so far into failures."""
        for line in self.console:
            self.errors.append(f"{where}: console error: {line}")
        for line in self.server_errors:
            self.errors.append(f"{where}: server error: {line}")
        self.console.clear()
        self.server_errors.clear()


def sign_in(page: Page, password: str) -> None:
    page.get_by_label("Username").fill(USER)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Sign in").click()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8420")
    ap.add_argument("--out", type=Path, default=Path("e2e-out"))
    ap.add_argument("--expect", action="append", default=[], help="capability id that must be ready")
    ap.add_argument("--timeout", type=float, default=120)
    args = ap.parse_args()
    base = args.url.rstrip("/")
    args.out.mkdir(parents=True, exist_ok=True)
    wait_healthy(base, args.timeout)

    c = Checks(args.out)
    manifest: dict = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 860})
        ctx.set_default_timeout(20_000)
        page = ctx.new_page()
        c.attach(page)

        def setup() -> None:
            page.goto(f"{base}/setup/")
            page.get_by_label("Username").fill(USER)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_label("Confirm password").fill(PASSWORD)
            page.get_by_role("button", name="Create account").click()
            page.wait_for_url(f"{base}/")
            expect(page.get_by_role("link", name="Dashboard").first).to_be_visible()

        c.step("first-run setup creates the admin", setup)
        c.drain("setup")

        def capabilities() -> None:
            nonlocal manifest
            r = page.request.get(f"{base}/api/system/capabilities")
            assert r.ok, f"GET capabilities: {r.status}"
            manifest = r.json()
            (args.out / "capabilities.json").write_text(json.dumps(manifest, indent=2))
            print(f"    {manifest['os']} {manifest['os_version']} {manifest['arch']}")
            for cap in manifest["capabilities"]:
                print(f"    {cap['status']:>14}  {cap['id']:<22} {cap.get('provider') or ''}")
            ready = {cap["id"] for cap in manifest["capabilities"] if cap["available"]}
            missing = [i for i in args.expect if i not in ready]
            assert not missing, f"expected ready but aren't: {missing}"

        c.step("capability manifest", capabilities)

        for path in PAGES:
            name = "page" + (path.strip("/").replace("/", "-") and "-" + path.strip("/").replace("/", "-") or "-dashboard")

            def visit(path=path, name=name) -> None:
                page.goto(f"{base}{path}")
                page.wait_for_load_state("networkidle")
                # Every signed-in page shows the sidebar; a crash shows Next's error page.
                expect(page.get_by_role("link", name="Dashboard").first).to_be_visible()
                c.shot(page, name)

            c.step(f"page {path} renders", visit)
            c.drain(path)

        ready = {cap["id"] for cap in manifest.get("capabilities", []) if cap["available"]}
        if "terminal.host" in ready:

            def terminal() -> None:
                page.goto(f"{base}/terminal/")
                expect(page.get_by_text("Connected")).to_be_visible()
                page.locator(".xterm").click()
                # The shell prints 42 only if it really ran the command (the echo of what
                # was typed shows the expression, not the result).
                is_windows = manifest.get("os") == "windows"
                page.keyboard.type("echo athena-e2e-$(6*7)" if is_windows else "echo athena-e2e-$((6*7))")
                page.keyboard.press("Enter")
                expect(page.locator(".xterm-rows")).to_contain_text("athena-e2e-42", timeout=30_000)
                c.shot(page, "terminal-command")

            c.step("host terminal runs a command", terminal)
            c.drain("terminal")

        def phone_and_dark() -> None:
            page.set_viewport_size({"width": 375, "height": 812})
            page.goto(f"{base}/")
            page.wait_for_load_state("networkidle")
            c.shot(page, "phone-dashboard")
            width = page.evaluate("document.documentElement.scrollWidth")
            assert width <= 375, f"horizontal scroll at phone width ({width}px)"
            page.set_viewport_size({"width": 1280, "height": 860})
            page.evaluate("document.documentElement.classList.add('dark')")
            c.shot(page, "dark-dashboard")

        c.step("phone width and dark mode", phone_and_dark)
        c.drain("phone/dark")

        # A fresh browser: signed out, so pages redirect to /login.
        ctx2 = browser.new_context()
        ctx2.set_default_timeout(20_000)
        page2 = ctx2.new_page()
        c.attach(page2)

        def login() -> None:
            page2.goto(f"{base}/apps/")
            page2.wait_for_url(f"{base}/login/**")
            sign_in(page2, "wrong-password-1234")
            # The failure must be shown, not swallowed.
            expect(page2.get_by_role("alert").or_(page2.get_by_text("Invalid"))).to_be_visible()
            c.shot(page2, "login-wrong-password")
            sign_in(page2, PASSWORD)
            page2.wait_for_url(lambda u: "/login" not in u)
            expect(page2.get_by_role("link", name="Dashboard").first).to_be_visible()

        c.step("sign-in rejects a wrong password, accepts the right one", login)
        # The wrong password's 401 is expected; only 5xx and other console errors count.
        c.console = [m for m in c.console if "401" not in m]
        c.drain("login")
        browser.close()

    summary = {"os": manifest.get("os"), "errors": c.errors}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    if c.errors:
        print("\nFAILED:\n  " + "\n  ".join(c.errors))
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
