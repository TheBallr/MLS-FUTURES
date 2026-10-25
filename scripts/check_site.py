#!/usr/bin/env python3
"""Headless check with the bundled Chromium: open the built page, click every tab, report console errors, check the Games
tables fit their cards at 1100-1920 px and the Morning tab at 400 and 1400 px, check that a Ratings-tab Run with no edit moves
nothing (the page engine runs the run's ratings and the edited ones on one seed), and screenshot each tab to
outputs/latest/shots/ (not committed). Edges, Risk, Settings, History and Injuries tabs went 2026-10-23 (Zac); History and Injuries live in the club drawer."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.teams import ROOT

PAGE = os.path.join(ROOT, "outputs", "latest", "site_local.html")
SHOTS = os.path.join(ROOT, "outputs", "latest", "shots")
TABS = ["morning", "ratings", "games", "bracket"]


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
        # Bracket tab: slots rendered, nothing wider than its card
        await page.click("[data-tab=bracket]"); await page.wait_for_timeout(200)
        if await page.evaluate("document.querySelectorAll('#brRow .slot').length") < 10:
            errors.append("bracket tab: slots missing (no bracket distribution in markets.json?)")
        if await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"):
            errors.append("bracket tab: the page scrolls sideways at 1400px")
        # Bracket what-if: pin a seed from the slot menu, the page engine reruns and marks the pin; Clear drops it
        await page.click('#brRow .slot[data-key="0|seed|2"]'); await page.wait_for_timeout(200)
        items = await page.query_selector_all("#brMenu .cm-i")
        if len(items) < 2:
            errors.append("bracket tab: the seed menu did not open")
        else:
            await items[1].click()
            try:
                await page.wait_for_function("document.querySelector('#brStatus').textContent.includes('seasons') && !document.querySelector('#brRun').disabled", timeout=60000)
            except Exception:
                errors.append("bracket tab: the what-if run did not finish")
            if await page.evaluate("document.querySelectorAll('#tab-bracket .slot.pin').length") < 1:
                errors.append("bracket tab: the pinned seed is not marked")
            await page.screenshot(path=os.path.join(SHOTS, "bracket_whatif.png"))
            await page.click("#brClear"); await page.wait_for_timeout(800)
            if await page.evaluate("document.querySelectorAll('#tab-bracket .slot.pin').length"):
                errors.append("bracket tab: Clear left a pin")
        # Club drawer: a Ratings row opens it with the rating chart drawn; Escape closes it
        await page.click("[data-tab=ratings]"); await page.click("#ratingEast tr.team-row td.num"); await page.wait_for_timeout(300)
        if await page.evaluate("document.getElementById('drawer').hidden || !document.querySelector('#hxChart svg')"):
            errors.append("club drawer did not open with its chart")
        await page.screenshot(path=os.path.join(SHOTS, "drawer.png"))
        await page.keyboard.press("Escape"); await page.wait_for_timeout(100)
        if not await page.evaluate("document.getElementById('drawer').hidden"):
            errors.append("club drawer did not close on Escape")
        # Ratings: a Run with no edit must move nothing (paired baseline in the page worker)
        await page.click("[data-tab=ratings]"); await page.click("#hand-run")
        for _ in range(80):
            await page.wait_for_timeout(250)
            st = await page.evaluate("document.getElementById('hand-status').textContent")
            if "seasons in" in st or st.startswith("error"):
                break
        moved = await page.evaluate("document.querySelectorAll('#ratingEast .d, #ratingWest .d').length")
        if "seasons in" not in st or moved:
            errors.append(f"ratings Run with no edit: status '{st[:40]}', {moved} cells moved (expected 0)")
        await browser.close()
    print(f"check_site: {len(errors)} errors" + ("".join("\n  - " + e for e in errors) if errors else "; all tabs ok, screenshots in outputs/latest/shots/"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
