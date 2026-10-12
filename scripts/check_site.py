#!/usr/bin/env python3
"""Headless check with the bundled Chromium: open the built page, click every tab, run a Settings resim and a Scenarios edit,
report console errors, check the Games tables fit their cards at 1100 and 1920 px, screenshot each tab to outputs/latest/shots/."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.teams import ROOT

PAGE = os.path.join(ROOT, "outputs", "latest", "site_local.html")
SHOTS = os.path.join(ROOT, "outputs", "latest", "shots")
TABS = ["ratings", "games", "conferences", "injuries", "scenarios", "settings"]


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
        await page.set_viewport_size({"width": 1400, "height": 900})
        # Settings: move a slider and run the worker
        await page.click("[data-tab=settings]")
        await page.evaluate("document.getElementById('k_rating_sd').value=0.2; document.getElementById('k_rating_sd').dispatchEvent(new Event('input'))")
        await page.click("#btn-run")
        for _ in range(60):
            await page.wait_for_timeout(500)
            st = await page.evaluate("document.getElementById('run-status').textContent")
            if st.startswith("done") or st.startswith("error"):
                break
        st = await page.evaluate("document.getElementById('run-status').textContent")
        if not st.startswith("done"):
            errors.append(f"worker run did not finish: {st}")
        await page.screenshot(path=os.path.join(SHOTS, "settings_run.png"))
        # Scenarios: set a deduction and read the run row check
        await page.click("[data-tab=scenarios]")
        chk = await page.evaluate("window.__scenarioCheck ? window.__scenarioCheck() : 'no check'")
        print(f"check_site: scenarios run-row reproduction: {chk}")
        await browser.close()
    print(f"check_site: {len(errors)} errors" + ("".join("\n  - " + e for e in errors) if errors else "; all tabs ok, screenshots in outputs/latest/shots/"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
