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
    # the publish tool wraps the fragment in its own skeleton; the local headless check needs the same wrapper
    wrapped = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
               '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style>'
               '</head><body>' + html + '</body></html>')
    open(os.path.join(LATEST, "site_local.html"), "w", encoding="utf-8").write(wrapped)
    print(f"build_site: {out} ({os.path.getsize(out)//1024} KB) + site_local.html for the headless check")
