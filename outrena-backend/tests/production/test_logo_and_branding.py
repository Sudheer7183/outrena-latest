"""
test_logo_and_branding.py — Verify brand assets are present and well-formed.

These are pure Python tests (no network/DB required). They verify that:
  1. The brand-assets.ts file exists in the frontend.
  2. It contains all three required base64 exports.
  3. Each export is non-empty and is a valid data URI prefix.
  4. The Outrena lockup component file (OutrenaLogo.tsx) exists and exports
     the expected named exports.
  5. The Sidebar.tsx no longer contains the placeholder "O" text mark.
  6. The LoginPage.tsx imports OutrenaLockup.
"""
from __future__ import annotations

import os
import re

FRONTEND_ROOT = os.path.join(
    os.path.dirname(__file__),
    "..",  # tests/
    "..",  # outrena-backend/
    "..",  # production/
    "outrena-frontend",
    "src",
)


def _read(rel_path: str) -> str:
    full = os.path.normpath(os.path.join(FRONTEND_ROOT, rel_path))
    with open(full) as f:
        return f.read()


def test_brand_assets_file_exists() -> None:
    path = os.path.normpath(os.path.join(FRONTEND_ROOT, "lib", "brand-assets.ts"))
    assert os.path.isfile(path), (
        "brand-assets.ts not found at src/lib/brand-assets.ts. "
        "Run the production hardening step to generate it."
    )


def test_brand_assets_exports_light_logo() -> None:
    content = _read("lib/brand-assets.ts")
    assert "export const LOGO_LIGHT" in content, "LOGO_LIGHT export missing from brand-assets.ts"
    assert 'data:image/png;base64,' in content, "LOGO_LIGHT is not a valid data URI"


def test_brand_assets_exports_dark_logo() -> None:
    content = _read("lib/brand-assets.ts")
    assert "export const LOGO_DARK" in content, "LOGO_DARK export missing from brand-assets.ts"


def test_brand_assets_exports_app_icon() -> None:
    content = _read("lib/brand-assets.ts")
    assert "export const APP_ICON" in content, "APP_ICON export missing from brand-assets.ts"


def test_outrena_logo_component_exists() -> None:
    path = os.path.normpath(
        os.path.join(FRONTEND_ROOT, "components", "OutrenaLogo.tsx")
    )
    assert os.path.isfile(path), "OutrenaLogo.tsx not found in src/components/"


def test_outrena_logo_exports_lockup_and_icon() -> None:
    content = _read("components/OutrenaLogo.tsx")
    assert "export function OutrenaLockup" in content, "OutrenaLockup export missing"
    assert "export function OutrenaIcon" in content, "OutrenaIcon export missing"


def test_sidebar_uses_outrena_lockup() -> None:
    content = _read("components/layout/Sidebar.tsx")
    assert "OutrenaLockup" in content, (
        "Sidebar.tsx should use <OutrenaLockup> not the placeholder 'O' text mark."
    )


def test_sidebar_no_placeholder_text_mark() -> None:
    content = _read("components/layout/Sidebar.tsx")
    # The old placeholder was: <span className="text-sm font-black">O</span>
    assert '>O<' not in content.replace(' ', '').replace('\n', ''), (
        "Sidebar.tsx still contains the placeholder 'O' text mark. Replace with <OutrenaLockup>."
    )


def test_login_page_uses_outrena_lockup() -> None:
    content = _read("features/auth/LoginPage.tsx")
    assert "OutrenaLockup" in content, (
        "LoginPage.tsx should use <OutrenaLockup> for the login card logo."
    )


def test_index_html_uses_real_favicon() -> None:
    frontend_root_dir = os.path.normpath(os.path.join(FRONTEND_ROOT, ".."))
    index_path = os.path.join(frontend_root_dir, "index.html")
    with open(index_path) as f:
        content = f.read()
    assert "favicon.png" in content or "favicon.ico" in content, (
        "index.html does not reference a real favicon."
    )
    # Should NOT still be pointing at the placeholder favicon.svg
    assert "favicon.svg" not in content, (
        "index.html still references placeholder favicon.svg."
    )


def test_index_html_has_noindex_for_alpha() -> None:
    """During alpha, search engines should not index the platform."""
    frontend_root_dir = os.path.normpath(os.path.join(FRONTEND_ROOT, ".."))
    index_path = os.path.join(frontend_root_dir, "index.html")
    with open(index_path) as f:
        content = f.read()
    assert "noindex" in content, (
        "index.html is missing <meta name='robots' content='noindex'>. "
        "Add this before public launch."
    )
