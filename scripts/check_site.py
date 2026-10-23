#!/usr/bin/env python3
"""Headless check with the bundled Chromium: open the built page, click every tab, report console errors, check the Games
tables fit their cards at 1100-1920 px and the Morning tab at 400 and 1400 px, check that a Ratings-tab Run with no edit moves
nothing (the page engine runs the run's ratings and the edited ones on one seed), and screenshot each tab to
outputs/latest/shots/ (not committed). Edges, Risk and Settings tabs went 2026-10-23 (Zac)."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.teams import ROOT

PAGE = os.path.join(ROOT, "outputs", "latest", "site_local.html")
SHOTS = os.path.join(ROOT, "outputs", "latest", "shots")
TABS = ["morning", "ratings", "games", "conferences", "history", "injuries"]


async def main():
    from playwright.async_api import async_playwright
    errors = []
    os.makedirs(SHOTS, exist_ok=True)
    async with async_playwright() as p:
        exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
        try:
            browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        except Exception:
            browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto("file://" + PAGE)
        await page.wait_for_timeout(500)
        for tab in TABS:
            await page.click(f"[data-tab={tab}]"); await page.wait_for_timeout(300)
            await page.screenshot(path=os.path.join(SHOTS, f"{tab}.png"))
        # Games tables must fit their cards at every width from 1100 to 1920
        for w in (1100, 1300, 1600, 1920):
            await page.set_viewport_size({"width": w, "height": 900}); await page.click("[data-tab=games]"); await page.wait_for_timeout(200)
            over = await page.evaluate("Array.from(document.querySelectorAll('#tab-games .card')).map(c=>c.scrollWidth-c.clientWidth)")
            if any(x > 0 for x in over):
                errors.append(f"games table overflows its card at {w}px: {over}")
        # Morning tab: nothing wider than its card at phone and desktop widths
        await page.click("[data-tab=morning]"); await page.wait_for_timeout(200)
        for w in (400, 1400):
            await page.set_viewport_size({"width": w, "height": 900}); await page.wait_for_timeout(150)
            if await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"):
                errors.append(f"morning tab: the page scrolls sideways at {w}px")
        await page.set_viewport_size({"width": 1400, "height": 900})
        # Ratings: a Run with no edit must move nothing (paired baseline in the page worker)
        await page.click("[data-tab=ratings]"); await page.click("#hand-run")
        for _ in range(80):
            await page.wait_for_timeout(250)
            st = await page.evaluate("document.getElementById('hand-status').textContent")
            if st.startswith("done") or st.startswith("error"):
                break
        moved = await page.evaluate("document.querySelectorAll('#ratingEast .d, #ratingWest .d').length")
        if not st.startswith("done") or moved:
            errors.append(f"ratings Run with no edit: status '{st[:40]}', {moved} cells moved (expected 0)")
        await browser.close()
    print(f"check_site: {len(errors)} errors" + ("".join("\n  - " + e for e in errors) if errors else "; all tabs ok, screenshots in outputs/latest/shots/"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
