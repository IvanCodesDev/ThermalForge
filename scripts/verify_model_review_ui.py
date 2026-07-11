"""Headless verification for the real GLB model-review interaction."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.goto("http://127.0.0.1:5173", wait_until="networkidle")
    page.wait_for_timeout(2500)
    buttons = page.locator(".component-cards button")
    result = {
        "title": page.title(),
        "component_cards": buttons.count(),
        "explosion_disabled": page.locator("#explosion").is_disabled(),
        "selected_cards": page.locator(".component-cards button.selected").count(),
        "quote_controls": page.get_by_text("报价", exact=False).count(),
        "warnings": page.locator(".model-warning").all_inner_texts(),
        "console_errors": errors,
    }
    if buttons.count() > 0:
        buttons.nth(buttons.count() - 1).click()
        result["selected_after_click"] = page.locator(".component-cards button.selected").count()
        result["selected_mesh_label"] = page.locator(".selection-chip strong").inner_text()
        result["locked_component_id"] = page.locator(".component-cards button.selected").get_attribute("data-quote-component")
    if not result["explosion_disabled"]:
        page.locator("#explosion").fill("0.6")
        page.wait_for_timeout(500)
        result["exploded_mode"] = "EXPLODED GLB" in page.locator(".viewer-hud.top-left").inner_text()
    screenshot = ROOT / "outputs" / "ui-model-review-verification.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshot), full_page=True)
    result["screenshot"] = str(screenshot)
    print(json.dumps(result, ensure_ascii=False))
    browser.close()
