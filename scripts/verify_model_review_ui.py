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
    page.set_default_timeout(120_000)
    page.goto("http://127.0.0.1:5173", wait_until="domcontentloaded", timeout=120_000)
    page.locator(".part-item").nth(28).wait_for(state="visible")
    page.locator(".viewer-loading").wait_for(state="hidden", timeout=180_000)
    buttons = page.locator(".part-item")
    result = {
        "title": page.title(),
        "component_cards": buttons.count(),
        "explosion_disabled": page.locator(".explosion-control input[type=range]").is_disabled(),
        "selected_cards": page.locator(".part-item.selected").count(),
        "quote_controls": page.locator("[data-quote-component]").count(),
        "warnings": page.locator(".model-warning").all_inner_texts(),
        "console_errors": errors,
    }
    assembled_screenshot = ROOT / "outputs" / "ui-model-review-assembled.png"
    page.screenshot(path=str(assembled_screenshot), full_page=True)
    result["assembled_screenshot"] = str(assembled_screenshot)
    if buttons.count() > 0:
        buttons.nth(buttons.count() - 1).click()
        result["selected_after_click"] = page.locator(".part-item.selected").count()
        result["selected_mesh_label"] = page.locator(".selection-chip strong").inner_text()
        result["locked_component_id"] = page.locator(".part-item.selected").get_attribute("data-quote-component")
    if page.locator(".explosion-control input[type=range]").count():
        page.locator(".explosion-control input[type=range]").fill("0.6")
        page.wait_for_timeout(500)
        result["exploded_mode"] = "EXPLODED" in page.locator(".viewer-hud.top-left").inner_text()
    screenshot = ROOT / "outputs" / "ui-model-review-verification.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshot), full_page=True)
    result["screenshot"] = str(screenshot)
    print(json.dumps(result, ensure_ascii=False))
    assert result["component_cards"] == 29, "full-arm GLB must expose all 29 real meshes"
    assert result["explosion_disabled"] is False
    assert result.get("exploded_mode") is True
    assert result.get("selected_after_click") == 1
    assert not result["console_errors"]
    browser.close()
