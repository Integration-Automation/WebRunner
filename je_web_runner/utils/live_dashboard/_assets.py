"""
儀表板的靜態資源 / The dashboard's stylesheet, script and icon.

Kept as Python strings so the package needs no package-data entry, and served from
the same origin (``/static/…``) because the pages' CSP, ``default-src 'self'``, blocks
inline styles and scripts. For the same reason no page uses a ``style`` attribute:
bars are ``<meter>`` elements and the chart is SVG with presentation classes.

The script only enhances pages that already work without it: local times, sortable
and filterable tables, and a refresh every 15 seconds that swaps the ``data-live``
regions for the server's fresh copy. It builds nodes with DOM APIs and never uses
``innerHTML``.
"""

STYLESHEET = """
:root {
  color-scheme: light dark;
  --bg: #f4f5f7; --surface: #ffffff; --surface-2: #eef0f3; --text: #1c1f24; --muted: #5f6672;
  --border: #dfe2e7; --accent: #2563d9; --good: #17794a; --warn: #9a5800; --bad: #c42b2b;
  --good-bg: #e3f3ea; --warn-bg: #fcefd8; --bad-bg: #fbe5e5; --top: #14161b; --top-text: #e9ebef;
  --shadow: 0 1px 2px rgba(16, 22, 32, 0.06);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101216; --surface: #191c22; --surface-2: #21252d; --text: #e5e7eb; --muted: #9ba2ae;
    --border: #2b303a; --accent: #7aa7ff; --good: #4fc28a; --warn: #f2b453; --bad: #ff7b7b;
    --good-bg: #15301f; --warn-bg: #33270f; --bad-bg: #3b1c1c; --top: #0a0b0e; --top-text: #e5e7eb;
    --shadow: none;
  }
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--accent); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
header.top { background: var(--top); color: var(--top-text); }
.top-inner { max-width: 1200px; margin: 0 auto; padding: 6px 16px; display: flex; flex-wrap: wrap;
             align-items: center; gap: 6px 20px; min-height: 52px; }
.brand { font-weight: 700; letter-spacing: 0.02em; }
nav { display: flex; flex-wrap: wrap; gap: 2px; flex: 1; }
nav a { color: var(--top-text); opacity: 0.72; text-decoration: none; padding: 6px 10px; border-radius: 6px; }
nav a:hover { opacity: 1; background: rgba(255, 255, 255, 0.08); }
nav a[aria-current="page"] { opacity: 1; background: rgba(255, 255, 255, 0.15); font-weight: 600; }
.live { display: flex; align-items: center; gap: 10px; font-size: 12px; opacity: 0.85; }
.live button { font: inherit; color: var(--top-text); background: transparent; cursor: pointer;
               border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; padding: 3px 10px; }
.live button[aria-pressed="true"] { background: rgba(255, 255, 255, 0.15); }
main { max-width: 1200px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 16px; }
h2 { font-size: 15px; margin: 28px 0 10px; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(165px, 1fr)); gap: 12px; margin-bottom: 8px; }
.card { background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--border);
        border-radius: 8px; padding: 10px 14px; box-shadow: var(--shadow); }
.card.good { border-left-color: var(--good); }
.card.warn { border-left-color: var(--warn); }
.card.bad { border-left-color: var(--bad); }
.card .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
.card .value { font-size: 26px; font-weight: 650; margin-top: 2px; font-variant-numeric: tabular-nums; }
.panel { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
         box-shadow: var(--shadow); overflow-x: auto; }
.panel.padded { padding: 14px 16px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }
th { background: var(--surface-2); color: var(--muted); font-size: 12px; font-weight: 600; white-space: nowrap; }
table[data-sortable] th { cursor: pointer; user-select: none; }
th[aria-sort="ascending"]::after { content: " \\25B2"; }
th[aria-sort="descending"]::after { content: " \\25BC"; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: var(--surface-2); }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.badge { display: inline-block; padding: 0 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.badge.good { color: var(--good); background: var(--good-bg); }
.badge.warn { color: var(--warn); background: var(--warn-bg); }
.badge.bad { color: var(--bad); background: var(--bad-bg); }
.muted { color: var(--muted); }
.empty { color: var(--muted); padding: 28px 16px; text-align: center; background: var(--surface);
         border: 1px dashed var(--border); border-radius: 8px; }
.empty .hint { display: block; font-size: 12px; margin-top: 6px; }
code { font-family: ui-monospace, "SF Mono", Consolas, monospace; font-size: 12px; background: var(--surface-2);
       padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
.toolbar input, .toolbar select { font: inherit; padding: 5px 10px; border: 1px solid var(--border);
                                  border-radius: 6px; background: var(--surface); color: var(--text); }
.toolbar input { min-width: 240px; }
.toolbar .count { color: var(--muted); font-size: 12px; margin-left: auto; }
meter { width: 80px; height: 10px; vertical-align: middle; margin-right: 6px; }
.more { display: inline-block; margin-top: 12px; }
.chart { width: 100%; height: auto; display: block; }
.chart .grid { stroke: var(--border); stroke-width: 1; }
.chart .axis { fill: var(--muted); font-size: 12px; }
.chart .area { fill: var(--accent); opacity: 0.12; }
.chart .line { fill: none; stroke: var(--accent); stroke-width: 2; }
.chart .dot { fill: var(--surface); stroke: var(--accent); stroke-width: 2; }
.chart .fail { fill: var(--bad); opacity: 0.5; }
.legend { display: flex; gap: 16px; font-size: 12px; color: var(--muted); margin-top: 6px; }
.legend .key { display: inline-block; width: 12px; height: 3px; vertical-align: middle; margin-right: 6px; }
.legend .key.line { background: var(--accent); }
.legend .key.fail { background: var(--bad); height: 8px; opacity: 0.5; }
dl.facts { display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: 0; }
dl.facts dt { color: var(--muted); }
dl.facts dd { margin: 0; }
.stack > * + * { margin-top: 12px; }
@media (max-width: 640px) {
  .card .value { font-size: 22px; }
  th, td { padding: 7px 8px; }
  .toolbar input { min-width: 0; flex: 1; }
  dl.facts { grid-template-columns: 1fr; }
  .chart { min-width: 760px; }  /* scroll sideways instead of shrinking the labels */
}
"""

SCRIPT = """
(function () {
  "use strict";
  var REFRESH_MS = 15000;
  var PAUSE_KEY = "webrunner-dashboard-paused";
  var sortState = {};
  var paused = readPaused();

  function readPaused() {
    try { return window.localStorage.getItem(PAUSE_KEY) === "1"; } catch (error) { return false; }
  }

  function writePaused(value) {
    try { window.localStorage.setItem(PAUSE_KEY, value ? "1" : "0"); } catch (error) { /* storage blocked */ }
  }

  function each(list, callback) { Array.prototype.forEach.call(list, callback); }

  function formatTimes(root) {
    each(root.querySelectorAll("time[datetime]"), function (node) {
      var when = new Date(node.getAttribute("datetime"));
      if (!isNaN(when.getTime())) {
        node.textContent = when.toLocaleString();
        node.title = node.getAttribute("datetime");
      }
    });
  }

  function sortKey(row, index) {
    var cell = row.cells[index];
    if (!cell) { return ""; }
    var raw = cell.hasAttribute("data-sort") ? cell.getAttribute("data-sort") : cell.textContent.trim();
    var number = Number(raw);
    return raw !== "" && !isNaN(number) ? number : raw.toLowerCase();
  }

  function compare(a, b) {
    if (typeof a === "number" && typeof b === "number") { return a - b; }
    return String(a).localeCompare(String(b));
  }

  function sortTable(table, index, descending) {
    var body = table.tBodies[0];
    if (!body || !table.tHead) { return; }
    var rows = Array.prototype.slice.call(body.rows);
    rows.sort(function (x, y) {
      var order = compare(sortKey(x, index), sortKey(y, index));
      return descending ? -order : order;
    });
    rows.forEach(function (row) { body.appendChild(row); });
    each(table.tHead.rows[0].cells, function (header, position) {
      if (position === index) {
        header.setAttribute("aria-sort", descending ? "descending" : "ascending");
      } else {
        header.removeAttribute("aria-sort");
      }
    });
  }

  function enableSorting(root) {
    each(root.querySelectorAll("table[data-sortable]"), function (table) {
      if (!table.tHead) { return; }
      each(table.tHead.rows[0].cells, function (header, index) {
        header.tabIndex = 0;
        var activate = function () {
          var state = sortState[table.id];
          var descending = state && state.index === index ? !state.descending : false;
          sortState[table.id] = { index: index, descending: descending };
          sortTable(table, index, descending);
        };
        header.addEventListener("click", activate);
        header.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); }
        });
      });
      var state = sortState[table.id];
      if (state) { sortTable(table, state.index, state.descending); }
    });
  }

  function filterTable(tableId) {
    var table = document.getElementById(tableId);
    if (!table || !table.tBodies[0]) { return; }
    var input = document.querySelector("[data-filter='" + tableId + "']");
    var select = document.querySelector("[data-status-filter='" + tableId + "']");
    var needle = input ? input.value.trim().toLowerCase() : "";
    var status = select ? select.value : "";
    var rows = table.tBodies[0].rows;
    var shown = 0;
    each(rows, function (row) {
      var visible = (!needle || row.textContent.toLowerCase().indexOf(needle) !== -1) &&
        (!status || row.getAttribute("data-status") === status);
      row.hidden = !visible;
      if (visible) { shown += 1; }
    });
    var counter = document.querySelector("[data-count='" + tableId + "']");
    if (counter) { counter.textContent = shown + " of " + rows.length; }
  }

  function enableFilters() {
    each(document.querySelectorAll("[data-filter], [data-status-filter]"), function (control) {
      var tableId = control.getAttribute("data-filter") || control.getAttribute("data-status-filter");
      control.addEventListener("input", function () { filterTable(tableId); });
      control.addEventListener("change", function () { filterTable(tableId); });
    });
  }

  function enhance(root) {
    formatTimes(root);
    enableSorting(root);
    each(root.querySelectorAll("table[id]"), function (table) { filterTable(table.id); });
  }

  function setStatus(text) {
    var status = document.getElementById("live-status");
    if (status) { status.textContent = text; }
  }

  function markUpdated(when) {
    var node = document.getElementById("updated");
    if (!node) { return; }
    node.setAttribute("datetime", when.toISOString());
    node.textContent = when.toLocaleTimeString();
  }

  function swapRegions(fresh) {
    each(document.querySelectorAll("[data-live]"), function (region) {
      var replacement = fresh.getElementById(region.id);
      if (!replacement) { return; }
      var nodes = Array.prototype.map.call(replacement.childNodes, function (node) {
        return document.importNode(node, true);
      });
      region.replaceChildren.apply(region, nodes);
      enhance(region);
    });
  }

  function refresh() {
    if (paused || document.hidden) { return; }
    window.fetch(window.location.href, { cache: "no-store", headers: { "Accept": "text/html" } })
      .then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status); }
        return response.text();
      })
      .then(function (text) {
        swapRegions(new DOMParser().parseFromString(text, "text/html"));
        markUpdated(new Date());
        setStatus("");
      })
      .catch(function () { setStatus("offline"); });
  }

  function enableLiveToggle() {
    var button = document.getElementById("live-toggle");
    if (!button) { return; }
    var render = function () {
      button.textContent = paused ? "Resume" : "Pause";
      button.setAttribute("aria-pressed", paused ? "true" : "false");
      setStatus(paused ? "paused" : "");
    };
    button.hidden = false;
    button.addEventListener("click", function () {
      paused = !paused;
      writePaused(paused);
      render();
      if (!paused) { refresh(); }
    });
    render();
  }

  document.addEventListener("DOMContentLoaded", function () {
    enhance(document);
    enableFilters();
    enableLiveToggle();
    window.setInterval(refresh, REFRESH_MS);
  });
})();
"""

FAVICON = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    "<rect width='32' height='32' rx='7' fill='#2563d9'/>"
    "<polyline points='6,20 12,14 17,18 26,8' fill='none' stroke='#fff' stroke-width='3' "
    "stroke-linecap='round' stroke-linejoin='round'/></svg>"
)
