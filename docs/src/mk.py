import sys, os
from playwright.sync_api import sync_playwright
src,out=sys.argv[1],sys.argv[2]
with sync_playwright() as p:
    b=p.chromium.launch(args=['--no-sandbox']); pg=b.new_page()
    pg.goto('file://'+os.path.abspath(src)); pg.wait_for_load_state('networkidle'); pg.wait_for_timeout(800)
    pg.pdf(path=out, print_background=True, prefer_css_page_size=True)
    b.close()
