#!/usr/bin/env python3
"""Embed outputs/latest/site_data.json into site/index.html -> outputs/latest/site.html (the page to publish)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.teams import ROOT

LATEST = os.path.join(ROOT, "outputs", "latest")

if __name__ == "__main__":
    tpl = open(os.path.join(ROOT, "site", "index.html"), encoding="utf-8").read()
    data = open(os.path.join(LATEST, "site_data.json"), encoding="utf-8").read()
    assert "/*__DATA__*/" in tpl, "template placeholder missing"
    html = tpl.replace("/*__DATA__*/", "window.DATA=" + data.replace("</", "<\\/") + ";")
    out = os.path.join(LATEST, "site.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"build_site: {out} ({os.path.getsize(out)//1024} KB)")
