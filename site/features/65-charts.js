// Charts. One renderer for every chart file: line and point series, one y axis per panel, bands and markers.
// Panels of one figure share the x axis and stack (small multiples), never two y axes on one chart.
// Pointer and keyboard show a crosshair and the value; the tables and the CSV file are the text version.
const MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];
const SVG = "http://www.w3.org/2000/svg";
function svg(tag, attrs, parent) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  parent?.append(el);
  return el;
}
// Unicode minus, isolated left to right, so "-441.53" never shows as "441.53-" inside Hebrew text.
const num = (v, digits = 0) => `⁦${v < 0 ? "−" : ""}${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })}⁩`;
const digitsFor = (step) => Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
// Round ticks. A tight axis keeps the data extent as its ends (x); otherwise the ends round out to a tick (y).
function niceTicks(lo, hi, target, tight = false) {
  const raw = (hi - lo) / target || 1;
  const p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].find((m) => m * p >= raw) * p;
  const first = tight ? Math.ceil(lo / step) * step : Math.floor(lo / step) * step;
  const last = tight ? Math.floor(hi / step) * step : Math.ceil(hi / step) * step;
  const ticks = [];
  for (let v = first; v <= last + step / 1e6; v += step) ticks.push(Number(v.toFixed(10)));
  return { ticks, step, lo: tight ? lo : first, hi: tight ? hi : last };
}
const dateToYear = (d) => {
  const [y, m, day] = d.split("-").map(Number);
  return y + (Date.UTC(y, m - 1, day) - Date.UTC(y, 0, 1)) / (365.25 * 864e5);
};
function prepare(panel) {
  const xOf = panel.x.type === "date" ? dateToYear : (x) => x;
  return { ...panel, series: panel.series.map((s) => ({ ...s, pts: s.points.map(([x, y]) => ({ x: xOf(x), y, raw: x })) })) };
}
function formatX(panel, p, step) {
  if (panel.x.type === "date") { const [y, m] = p.raw.split("-"); return `${MONTHS[Number(m) - 1]} ${y}`; }
  if (panel.x.type === "year") return String(p.raw);
  return `${num(p.raw, Number.isInteger(p.raw) ? 0 : Math.min(2, digitsFor(step) + 1))}${panel.x.unit ? ` ${panel.x.unit}` : ""}`;
}
function markerList(markers) {
  const list = document.createElement("ol");
  list.className = "chart-markers";
  markers.forEach((m) => {
    const li = document.createElement("li");
    // A label may end with the ID of the paragraph that states it, in brackets: link it.
    const open = m.label.lastIndexOf("(");
    const id = m.label.endsWith(")") && open >= 0 ? m.label.slice(open + 1, -1) : "";
    if (id && document.getElementById(id)) {
      const a = document.createElement("a");
      a.href = `#${id}`;
      a.textContent = "בספר";
      a.addEventListener("click", (e) => { e.preventDefault(); goTo(id); });
      li.append(m.label.slice(0, open).trim(), " (", a, ")");
    } else {
      li.textContent = m.label;
    }
    list.append(li);
  });
  return list;
}
function drawFigureChart(area, panels, width) {
  const shared = panels.length > 1;
  const allX = panels.flatMap((p) => p.series.flatMap((s) => s.pts.map((pt) => pt.x)));
  const xt = niceTicks(Math.min(...allX), Math.max(...allX), width < 480 ? 4 : 7, true);
  const W = Math.max(280, width);
  const M = { top: 14, right: 16, bottom: 30, left: 58 };
  const x = (v) => M.left + ((v - xt.lo) / (xt.hi - xt.lo)) * (W - M.left - M.right);
  const views = [];
  const nodes = [];
  panels.forEach((panel, pi) => {
    const H = Math.round(Math.min(shared ? 260 : 360, Math.max(shared ? 170 : 220, W * (shared ? 0.34 : 0.5))));
    const allY = panel.series.flatMap((s) => s.pts.map((pt) => pt.y)).concat(panel.markers.filter((m) => m.axis === "y").map((m) => m.at));
    const yt = niceTicks(Math.min(...allY), Math.max(...allY), 5);
    const y = (v) => M.top + ((yt.hi - v) / (yt.hi - yt.lo)) * (H - M.top - M.bottom);
    const head = document.createElement("div");
    head.className = "chart-head";
    const title = document.createElement("p");
    title.className = "chart-axis-title";
    title.textContent = `${panel.y.label}${panel.y.unit ? ` (${panel.y.unit})` : ""}`;
    head.append(title);
    if (panel.series.length > 1) {
      const legend = document.createElement("ul");
      legend.className = "chart-legend";
      panel.series.forEach((s, si) => {
        const li = document.createElement("li");
        li.innerHTML = `<i class="key s${si + 1} ${s.kind}"></i>`;
        li.append(s.name);
        legend.append(li);
      });
      head.append(legend);
    }
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", tabindex: "0", dir: "ltr" });
    const first = panel.series[0].pts;
    root.setAttribute("aria-label", `${panel.title}. ${panel.series.length} סדרות, ${first.length} נקודות בראשונה. החצים עוברים בין הנקודות.`);
    for (const b of panel.bands) {
      const [a, z] = b.axis === "x" ? [x(b.from), x(b.to)] : [y(b.to), y(b.from)];
      const rect = b.axis === "x" ? { x: a, width: z - a, y: M.top, height: H - M.top - M.bottom } : { y: a, height: z - a, x: M.left, width: W - M.left - M.right };
      svg("rect", { ...rect, class: "band" }, root);
      if (b.axis === "x") svg("text", { x: (a + z) / 2, y: M.top + 14, class: "band-label", "text-anchor": "middle" }, root).textContent = b.label;
    }
    for (const v of yt.ticks) {
      svg("line", { x1: M.left, x2: W - M.right, y1: y(v), y2: y(v), class: "grid" }, root);
      svg("text", { x: M.left - 8, y: y(v), class: "tick", "text-anchor": "end", "dominant-baseline": "middle" }, root).textContent = num(v, digitsFor(yt.step));
    }
    if (!shared || pi === panels.length - 1) {
      for (const v of xt.ticks) svg("text", { x: x(v), y: H - 8, class: "tick", "text-anchor": "middle" }, root).textContent = panel.x.type === "number" ? num(v, digitsFor(xt.step)) : String(v);
    }
    panel.markers.forEach((m, mi) => {
      const line = m.axis === "x" ? { x1: x(m.at), x2: x(m.at), y1: M.top, y2: H - M.bottom } : { x1: M.left, x2: W - M.right, y1: y(m.at), y2: y(m.at) };
      svg("line", { ...line, class: "marker" }, root);
      const at = m.axis === "x" ? { cx: x(m.at), cy: H - M.bottom - 9 } : { cx: W - M.right - 8, cy: y(m.at) };
      svg("circle", { ...at, r: 9, class: "marker-badge" }, root);
      svg("text", { x: at.cx, y: at.cy, class: "marker-n", "text-anchor": "middle", "dominant-baseline": "central" }, root).textContent = mi + 1;
    });
    panel.series.forEach((s, si) => {
      if (s.kind === "line") {
        svg("path", { d: s.pts.map((p, i) => `${i ? "L" : "M"}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`).join(""), class: `line s${si + 1}${area.dataset.drawn ? "" : " draw-in"}`, pathLength: 1 }, root);
      } else {
        for (const p of s.pts) svg("circle", { cx: x(p.x).toFixed(1), cy: y(p.y).toFixed(1), r: 2.6, class: `pt s${si + 1}` }, root);
      }
    });
    // Direct labels at the end of each line when there is more than one series.
    if (panel.series.length > 1) {
      panel.series.forEach((s, si) => {
        if (s.kind !== "line") return;
        const last = s.pts.at(-1);
        svg("text", { x: Math.min(x(last.x), W - M.right) - 4, y: y(last.y) - 8, class: `direct s${si + 1}`, "text-anchor": "end" }, root).textContent = s.name;
      });
    }
    const cross = svg("line", { y1: M.top, y2: H - M.bottom, class: "cross", visibility: "hidden" }, root);
    const dot = svg("circle", { r: 5, class: "dot", visibility: "hidden" }, root);
    const box = document.createElement("div");
    box.className = "chart-panel";
    const plot = document.createElement("div");
    plot.className = "chart-plot";
    const tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    tip.setAttribute("aria-live", "polite");
    plot.append(root, tip);
    box.append(head, plot);
    if (!shared || pi === panels.length - 1) {
      const xl = document.createElement("p");
      xl.className = "chart-x-title";
      xl.textContent = `${panel.x.label}${panel.x.unit ? ` (${panel.x.unit})` : ""}`;
      box.append(xl);
    }
    if (panel.markers.length) box.append(markerList(panel.markers));
    nodes.push(box);
    views.push({ panel, root, tip, cross, dot, x, y, W, H, xt });
  });
  // Hover and keyboard. Small multiples follow the pointer's x in every panel; a single panel takes the nearest point.
  let current = { si: 0, i: views[0].panel.series[0].pts.length - 1 };
  const showPoint = (v, si, i) => {
    const s = v.panel.series[si], p = s.pts[i];
    for (const el of [v.cross, v.dot]) el.setAttribute("visibility", "visible");
    v.cross.setAttribute("x1", v.x(p.x)); v.cross.setAttribute("x2", v.x(p.x));
    v.dot.setAttribute("cx", v.x(p.x)); v.dot.setAttribute("cy", v.y(p.y));
    v.dot.setAttribute("class", `dot s${si + 1}`);
    const unit = v.panel.y.unit ? ` ${v.panel.y.unit}` : "";
    const digits = s.pts.every((q) => Number.isInteger(q.y)) ? 0 : Math.abs(p.y) < 10 ? 2 : 1;
    v.tip.textContent = `${v.panel.series.length > 1 ? `${s.name}: ` : ""}${formatX(v.panel, p, v.xt.step)} · ${num(p.y, digits)}${unit}`;
    v.tip.hidden = false;
    const r = v.root.getBoundingClientRect();
    v.tip.style.left = `${(v.x(p.x) / v.W) * r.width}px`;
    v.tip.style.top = `${(v.y(p.y) / v.H) * r.height}px`;
  };
  const hideAll = () => { for (const v of views) { for (const el of [v.cross, v.dot]) el.setAttribute("visibility", "hidden"); v.tip.hidden = true; } };
  const nearestByX = (pts, xv) => pts.reduce((b, p, i) => (Math.abs(p.x - xv) < Math.abs(pts[b].x - xv) ? i : b), 0);
  views.forEach((v) => {
    v.root.addEventListener("pointermove", (e) => {
      const r = v.root.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * v.W, py = ((e.clientY - r.top) / r.height) * v.H;
      if (shared) {
        const xv = v.xt.lo + ((px - v.x(v.xt.lo)) / (v.x(v.xt.hi) - v.x(v.xt.lo))) * (v.xt.hi - v.xt.lo);
        for (const w of views) showPoint(w, 0, nearestByX(w.panel.series[0].pts, xv));
        return;
      }
      let best = null;
      v.panel.series.forEach((s, si) => s.pts.forEach((p, i) => {
        const d = Math.hypot(v.x(p.x) - px, v.y(p.y) - py);
        if (!best || d < best.d) best = { d, si, i };
      }));
      current = best;
      showPoint(v, best.si, best.i);
    });
    v.root.addEventListener("pointerleave", hideAll);
    v.root.addEventListener("focus", () => showPoint(v, Math.min(current.si, v.panel.series.length - 1), Math.min(current.i, v.panel.series[Math.min(current.si, v.panel.series.length - 1)].pts.length - 1)));
    v.root.addEventListener("blur", hideAll);
    v.root.addEventListener("keydown", (e) => {
      const n = v.panel.series.length;
      let { si, i } = current;
      si = Math.min(si, n - 1);
      const len = v.panel.series[si].pts.length;
      const big = Math.max(1, Math.round(len / 20));
      const moves = { ArrowLeft: -1, ArrowRight: 1, PageDown: -big, PageUp: big };
      if (e.key in moves) i += moves[e.key];
      else if (e.key === "Home") i = 0;
      else if (e.key === "End") i = len - 1;
      else if (e.key === "ArrowUp" || e.key === "ArrowDown") { si = (si + (e.key === "ArrowUp" ? 1 : n - 1)) % n; i = Math.min(i, v.panel.series[si].pts.length - 1); }
      else return;
      e.preventDefault();
      current = { si, i: Math.max(0, Math.min(v.panel.series[si].pts.length - 1, i)) };
      showPoint(v, current.si, current.i);
    });
  });
  area.replaceChildren(...nodes);
  area.dataset.drawn = ""; // Lines draw in only the first time; a redraw for a new width shows them at once.
}
async function setUpChart(figure) {
  const box = figure.querySelector(".chart-box");
  const response = await fetch(box.dataset.chart);
  if (!response.ok) throw new Error(`${box.dataset.chart}: HTTP ${response.status}`);
  const panels = (await response.json()).panels.map(prepare);
  const area = box.querySelector(".chart-area");
  area.hidden = false;
  // Draw at the real width, so labels keep their size on a phone; redraw when the width changes.
  let width = 0;
  new ResizeObserver(() => {
    if (area.clientWidth === width || area.clientWidth === 0) return;
    width = area.clientWidth;
    drawFigureChart(area, panels, width);
  }).observe(area);
}
// Toggle between the interactive chart and the printed image. The chart shows first.
for (const figure of reading.querySelectorAll("figure.has-chart")) {
  const img = figure.querySelector(":scope > img");
  const group = document.createElement("div");
  group.className = "view-toggle";
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "תצוגת האיור");
  const make = (label, chart) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.addEventListener("click", () => setView(chart));
    group.append(b);
    return b;
  };
  const chartButton = make("גרף אינטראקטיבי", true);
  const printButton = make("האיור המודפס", false);
  const setView = (chart) => {
    chartButton.setAttribute("aria-pressed", String(chart));
    printButton.setAttribute("aria-pressed", String(!chart));
    figure.querySelector(".chart-box").hidden = !chart;
    if (img) img.hidden = chart;
  };
  figure.prepend(group);
  setView(true);
  onNear(figure, () => setUpChart(figure).catch((err) => { setView(false); group.remove(); console.error(err); }));
}

