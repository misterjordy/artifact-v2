"""Tests for the three-mode theme system with 508-compliant eyecare default."""

import math
import re
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token
from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.main import app

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "artiFACT" / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "artiFACT" / "static"
CSS_PATH = STATIC_DIR / "theme.css"

REQUIRED_VARIABLES = [
    "--color-bg",
    "--color-bg-card",
    "--color-bg-sidebar",
    "--color-text",
    "--color-text-muted",
    "--color-text-sidebar",
    "--color-accent",
    "--color-accent-gold",
    "--color-success",
    "--color-danger",
    "--color-info",
    "--color-tag",
    "--color-border",
    "--color-header-bg",
]

BANNED_PATTERNS = [
    r"bg-gray-",
    r"bg-slate-",
    r"bg-white\b",
    r"bg-zinc-",
    r"bg-neutral-",
    r"text-gray-",
    r"text-slate-",
    r"text-white\b",
    r"text-zinc-",
    r"text-neutral-",
    r"border-gray-",
    r"border-slate-",
    r"border-zinc-",
    r"border-neutral-",
]


@pytest_asyncio.fixture
async def authed_client(db: AsyncSession, admin_user: FcUser) -> AsyncIterator[AsyncClient]:
    """HTTP client authenticated as admin."""
    session_id = await create_session(admin_user)
    csrf_token = generate_csrf_token()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"session_id": session_id, "csrf_token": csrf_token},
        headers={"x-csrf-token": csrf_token},
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthed_client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP client with no auth."""

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as c:
        yield c
    app.dependency_overrides.clear()


def _parse_css_blocks(css_text: str) -> dict[str, str]:
    """Parse CSS into theme blocks: {'eyecare': '...', 'dark': '...', 'default': '...'}."""
    blocks: dict[str, str] = {}
    for mode in ("eyecare", "dark", "default"):
        pattern = rf"html\.{mode}\s*\{{([^}}]+)\}}"
        m = re.search(pattern, css_text, re.DOTALL)
        if m:
            blocks[mode] = m.group(1)
    return blocks


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color to RGB (0-255)."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _relative_luminance(r: float, g: float, b: float) -> float:
    """WCAG relative luminance."""
    rs, gs, bs = r / 255.0, g / 255.0, b / 255.0

    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(rs) + 0.7152 * linearize(gs) + 0.0722 * linearize(bs)


def _contrast_ratio(hex1: str, hex2: str) -> float:
    """WCAG contrast ratio between two hex colors."""
    l1 = _relative_luminance(*_hex_to_rgb(hex1))
    l2 = _relative_luminance(*_hex_to_rgb(hex2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _extract_var(block: str, var_name: str) -> str | None:
    """Extract a CSS variable value from a block."""
    m = re.search(rf"{re.escape(var_name)}\s*:\s*([^;]+);", block)
    return m.group(1).strip() if m else None


# ── TEST 1: Theme CSS has all three modes with all variables ──


async def test_theme_css_three_modes_with_all_variables() -> None:
    """theme.css must define html.eyecare, html.dark, html.default with all 14 variables."""
    css = CSS_PATH.read_text()

    assert "html.eyecare" in css, "Missing html.eyecare block"
    assert "html.dark" in css, "Missing html.dark block"
    assert "html.default" in css, "Missing html.default block"

    blocks = _parse_css_blocks(css)
    assert len(blocks) == 3, f"Expected 3 blocks, found: {list(blocks.keys())}"

    missing: list[str] = []
    for mode, block in blocks.items():
        for var in REQUIRED_VARIABLES:
            if var not in block:
                missing.append(f"{mode}: {var}")

    assert missing == [], f"Missing CSS variables:\n" + "\n".join(missing)


# ── TEST 2: No hardcoded Tailwind colors in templates ──


async def test_no_hardcoded_tailwind_colors() -> None:
    """No template should use hardcoded Tailwind color classes."""
    violations: list[str] = []
    combined_pattern = re.compile("|".join(BANNED_PATTERNS))

    for html_file in sorted(TEMPLATE_DIR.rglob("*.html")):
        text = html_file.read_text()
        rel = html_file.relative_to(TEMPLATE_DIR)
        for i, line in enumerate(text.splitlines(), 1):
            # Only check inside class="..." attributes
            for class_match in re.finditer(r'class="([^"]*)"', line):
                class_val = class_match.group(1)
                for m in combined_pattern.finditer(class_val):
                    violations.append(f"{rel}:{i}: {m.group(0)} in '{class_val[:80]}'")

    assert violations == [], (
        f"Hardcoded Tailwind colors found ({len(violations)}):\n" + "\n".join(violations)
    )


# ── TEST 3: Theme toggle on settings page ──


async def test_theme_toggle_on_settings(authed_client: AsyncClient) -> None:
    """Settings page must have all three SVG theme icons and Alpine.js theme state."""
    resp = await authed_client.get("/settings")
    assert resp.status_code == 200
    html = resp.text

    # Sun icon (eyecare) — circle r="5"
    assert 'r="5"' in html, "Missing sun icon circle r='5'"

    # Eye icon (default) — path with "M1 12s4-8"
    assert "M1 12s4-8" in html, "Missing eye icon path 'M1 12s4-8'"

    # Moon icon (dark) — path with "M21 12.79"
    assert "M21 12.79" in html, "Missing moon icon path 'M21 12.79'"

    # Alpine.js theme toggle wired up
    assert "x-data" in html, "Missing x-data for theme toggle"
    assert "themeToggle" in html, "Missing themeToggle() reference in x-data"

    # Verify the JS file contains localStorage persistence logic
    settings_js = (STATIC_DIR / "js" / "settings.js").read_text()
    assert "localStorage" in settings_js, "Missing localStorage in settings.js"
    assert "artifact-theme" in settings_js, "Missing 'artifact-theme' key in settings.js"


# ── TEST 4: Settings link in header ──


async def test_settings_link_in_header(authed_client: AsyncClient) -> None:
    """Header must contain a link to /settings; search bar must not be in header."""
    resp = await authed_client.get("/browse")
    assert resp.status_code == 200
    html = resp.text

    # Extract header element
    header_match = re.search(r"<header\b[^>]*>(.*?)</header>", html, re.DOTALL)
    assert header_match is not None, "No <header> element found"
    header_html = header_match.group(1)

    # Settings link present
    assert "/settings" in header_html, "No /settings link in header"

    # No search form in header
    search_form = re.search(r'<form[^>]*action[^>]*search', header_html, re.IGNORECASE)
    assert search_form is None, "Search form should not be in header"

    # Also check no hx-get search form
    htmx_search = re.search(r'hx-get[^"]*search', header_html, re.IGNORECASE)
    assert htmx_search is None, "HTMX search form should not be in header"


# ── TEST 5: FOUC prevention script in head ──


async def test_fouc_prevention_script(unauthed_client: AsyncClient) -> None:
    """Head must contain an inline script that sets theme class before CSS loads."""
    resp = await unauthed_client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Extract <head> content
    head_match = re.search(r"<head>(.*?)</head>", html, re.DOTALL)
    assert head_match is not None, "No <head> element found"
    head_html = head_match.group(1)

    # Script reads localStorage and sets className
    assert "localStorage" in head_html, "No localStorage in head script"
    assert "documentElement.className" in head_html or "documentElement.class" in head_html, (
        "Script must set documentElement.className"
    )

    # Script defaults to 'eyecare'
    assert "'eyecare'" in head_html, "Script must default to 'eyecare'"

    # Script appears BEFORE theme.css link
    script_pos = head_html.find("<script>")
    css_pos = head_html.find("theme.css")
    assert script_pos >= 0, "No inline <script> in head"
    assert css_pos >= 0, "No theme.css link in head"
    assert script_pos < css_pos, "FOUC script must appear BEFORE theme.css link"


# ── TEST 6: Eyecare is the default ──


async def test_eyecare_is_default(unauthed_client: AsyncClient) -> None:
    """FOUC script defaults to 'eyecare'; html tag includes 'eyecare' class."""
    resp = await unauthed_client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Check FOUC script defaults
    head_match = re.search(r"<head>(.*?)</head>", html, re.DOTALL)
    assert head_match is not None
    head_html = head_match.group(1)
    assert "'eyecare'" in head_html, "FOUC script must default to 'eyecare'"

    # Check <html> tag has eyecare class
    html_tag = re.search(r"<html[^>]*>", html)
    assert html_tag is not None
    assert "eyecare" in html_tag.group(0), "<html> tag must include 'eyecare' class"


# ── TEST 7: Focus indicators in CSS ──


async def test_focus_indicators_in_css() -> None:
    """theme.css must have :focus-visible styles with visible indicators."""
    css = CSS_PATH.read_text()

    has_focus = ":focus-visible" in css or ":focus" in css
    assert has_focus, "CSS must contain :focus-visible or :focus styles"

    has_indicator = any(prop in css for prop in ["outline", "box-shadow"])
    assert has_indicator, "Focus styles must include outline or box-shadow"


# ── TEST 8: Eyecare contrast compliance ──


async def test_eyecare_contrast_compliance() -> None:
    """Eyecare mode colors must meet WCAG AA contrast ratios."""
    css = CSS_PATH.read_text()
    blocks = _parse_css_blocks(css)

    eyecare = blocks.get("eyecare")
    assert eyecare is not None, "No eyecare block found"

    text_color = _extract_var(eyecare, "--color-text")
    bg_color = _extract_var(eyecare, "--color-bg")
    sidebar_text = _extract_var(eyecare, "--color-text-sidebar")
    sidebar_bg = _extract_var(eyecare, "--color-bg-sidebar")
    accent = _extract_var(eyecare, "--color-accent")

    assert text_color and bg_color, "Missing --color-text or --color-bg in eyecare"
    assert sidebar_text and sidebar_bg, "Missing sidebar colors in eyecare"
    assert accent, "Missing --color-accent in eyecare"

    # Normal text: 4.5:1 minimum (WCAG AA)
    text_ratio = _contrast_ratio(text_color, bg_color)
    assert text_ratio >= 4.5, (
        f"Text vs bg contrast {text_ratio:.2f} < 4.5 ({text_color} on {bg_color})"
    )

    # Sidebar text: 4.5:1 minimum
    sidebar_ratio = _contrast_ratio(sidebar_text, sidebar_bg)
    assert sidebar_ratio >= 4.5, (
        f"Sidebar text vs bg contrast {sidebar_ratio:.2f} < 4.5 ({sidebar_text} on {sidebar_bg})"
    )

    # Accent (links): 3.0:1 minimum (AA large text)
    accent_ratio = _contrast_ratio(accent, bg_color)
    assert accent_ratio >= 3.0, (
        f"Accent vs bg contrast {accent_ratio:.2f} < 3.0 ({accent} on {bg_color})"
    )
