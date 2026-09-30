"""
儀表板的靜態資源 / The dashboard's stylesheet, served from ``/static/app.css``.

Kept as a Python string so the package needs no package-data entry, and served
from the same origin because the pages' CSP (``default-src 'self'``) blocks inline
styles.
"""

BASE_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif;
       margin: 0; background: #f5f5f7; color: #1d1d1f; }
nav  { background: #1d1d1f; color: #fff; padding: 12px 24px; }
nav a { color: #fff; margin-right: 16px; text-decoration: none; }
nav a:hover { text-decoration: underline; }
main { padding: 24px; max-width: 1200px; margin: 0 auto; }
h1   { margin-top: 0; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
         gap: 16px; margin-bottom: 32px; }
.card  { background: #fff; padding: 16px; border-radius: 8px;
         box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.card .label { color: #6e6e73; font-size: 12px; text-transform: uppercase; }
.card .value { font-size: 28px; font-weight: 600; margin-top: 4px; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #f0f0f3; }
th { background: #fafafa; font-size: 13px; color: #6e6e73; }
tr:last-child td { border-bottom: none; }
.bad   { color: #c9302c; font-weight: 600; }
.good  { color: #1d8348; font-weight: 600; }
.muted { color: #6e6e73; }
.empty { color: #6e6e73; padding: 32px; text-align: center; }
code   { background: #f0f0f3; padding: 2px 6px; border-radius: 4px;
         font-family: 'SF Mono', Consolas, monospace; font-size: 12px; }
"""
