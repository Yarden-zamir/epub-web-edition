// Interactive explainers inside printed figures (build: tools/web/45_explorables.py).
// Each figure gets a toggle between the explainer and the printed image. The explainer loads when it nears the view.
// One value drives a drawing on a canvas. A native range input holds the value for keyboard, touch and screen
// readers. An HTML handle over the canvas follows the pointer 1:1; keys, marks, reset and the first-view hint move
// the value with a short ease. Per frame: one canvas redraw, one handle transform, one short text. A canvas keeps a
// drag at 60 fps on a phone: SVG attribute changes cost style, pre-paint and layer work on this very long page.
//
// A drawing file (7N-explorable-<kind>.js) registers explorableKit.kinds[kind] = {
//   view: [x, y, width, height]                   drawing units shown in the canvas
//   valueParts(value, spec) -> {num, unit, note} the value as text: a number (fixed decimals), its unit and an
//                                                optional note. Each part sits in a fixed-width slot, so nothing moves.
//   animated?: true                              water and salt move slowly: env.time runs (12 frames a second at most)
//   create(spec, env) -> {                       prepares fixed shapes once
//     draw(ctx, value, env) -> summary string    draws one frame in drawing units
//     handle(value) -> [x, y]                    where the drag handle sits
//     drag(point, start) -> value               value for a pointer at point ({x, y} in drawing units)
//   }
// }
// env: unit (drawing units per CSS pixel), time (seconds, for slow motion), color(token), gradient(key, x0, y0, x1, y1, stops),
//      layer(key, [x, y, w, h], draw) -> a bitmap of draw() for parts that never change (copy it with ctx.drawImage),
//      label(ctx, text, x, y, options), figures(ctx, text, x, y, options) for a number with fixed-width digits.
// All feature scripts share one scope (site/features/README.md): only explorableKit is global here.
const explorableKit = (() => {

// Linear interpolation in a list of [x, y] points sorted by x; clamps at both ends.
function interpolate(points, x) {
  if (!points.length) throw new Error("interpolate: no points");
  if (x <= points[0][0]) return points[0][1];
  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = points[i];
    if (x <= x1) {
      const [x0, y0] = points[i - 1];
      return x1 === x0 ? y1 : y0 + ((y1 - y0) * (x - x0)) / (x1 - x0);
    }
  }
  return points[points.length - 1][1];
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
// 0 at a, 1 at b, eased in between: shapes fade and grow instead of popping in.
const ramp = (v, a, b) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const number = (value, digits = 0) =>
  value.toLocaleString("he-IL", { minimumFractionDigits: digits, maximumFractionDigits: digits });
// A number inside Hebrew text: isolated (U+2068 ... U+2069), so the sentence around it never reorders.
const iso = (text) => `\u2068${text}\u2069`;
const MINUS = "\u2212";
const valueText = (kind, v, spec) => { const p = kind.valueParts(v, spec); return `${p.num} ${p.unit}${p.note ? ` (${p.note})` : ""}`; };
const FLOW_FPS = 12; // Slow motion of water and salt: few frames, so an idle explainer costs little.
const easeOut = (t) => 1 - (1 - t) ** 3;
// A path through points, for a Path2D or the context itself.
function polyline(target, points, close = false) {
  points.forEach(([x, y], i) => (i ? target.lineTo(x, y) : target.moveTo(x, y)));
  if (close) target.closePath();
  return target;
}
const shape = (points, close = true) => polyline(new Path2D(), points, close);

function hintSeen(id) {
  try { return localStorage.getItem(`explorable-hint:${id}`) === "1"; } catch { return false; }
}
function markHintSeen(id) {
  try { localStorage.setItem(`explorable-hint:${id}`, "1"); } catch { /* Private mode: the hint may show again. */ }
}

// Colours, gradients and fonts come from the CSS tokens. A theme change clears them and redraws.
function makeEnv(box) {
  const colors = new Map(), gradients = new Map(), layers = new Map();
  let ctx = null, family = "";
  const env = {
    unit: 1,
    time: 0,
    bind(context) { ctx = context; },
    pixel: 1, // Device pixels per drawing unit.
    reset() { colors.clear(); gradients.clear(); layers.clear(); family = getComputedStyle(box).fontFamily; },
    // Static parts are drawn once into a bitmap at the current size and theme; a frame only copies it.
    layer(key, [x, y, w, h], draw) {
      const id = `${key}@${env.pixel.toFixed(4)}`;
      if (!layers.has(id)) {
        const bitmap = document.createElement("canvas");
        bitmap.width = Math.max(1, Math.ceil(w * env.pixel));
        bitmap.height = Math.max(1, Math.ceil(h * env.pixel));
        const lc = bitmap.getContext("2d");
        lc.setTransform(env.pixel, 0, 0, env.pixel, -x * env.pixel, -y * env.pixel);
        draw(lc);
        for (const old of layers.keys()) if (old.startsWith(`${key}@`)) layers.delete(old);
        layers.set(id, bitmap);
      }
      return layers.get(id);
    },
    color(token) {
      if (!colors.has(token)) {
        const value = getComputedStyle(box).getPropertyValue(token).trim();
        if (!value) throw new Error(`explorable: CSS token ${token} is not set`);
        colors.set(token, value);
      }
      return colors.get(token);
    },
    gradient(key, x0, y0, x1, y1, stops) {
      if (!gradients.has(key)) {
        const g = ctx.createLinearGradient(x0, y0, x1, y1);
        for (const [offset, token] of stops) g.addColorStop(offset, env.color(token));
        gradients.set(key, g);
      }
      return gradients.get(key);
    },
    // Hebrew label with a paper halo, about `size` CSS pixels at any width. align: "left", "right" or "center".
    label(c, text, x, y, { align = "center", size = 13, weight = 600, color = "--ink", rotate = 0 } = {}) {
      c.save();
      c.translate(x, y);
      if (rotate) c.rotate(rotate);
      c.font = `${weight} ${size * env.unit}px ${family}`;
      c.direction = "rtl";
      c.textAlign = align;
      c.lineJoin = "round";
      c.lineWidth = 3.5 * env.unit;
      c.strokeStyle = env.color("--paper");
      c.strokeText(text, 0, 0);
      c.fillStyle = env.color(color);
      c.fillText(text, 0, 0);
      c.restore();
    },
    // A number whose digits all take the width of "0", right-aligned at x: it never shifts as it changes.
    figures(c, text, x, y, { size = 13, weight = 700, color = "--ink" } = {}) {
      c.save();
      c.font = `${weight} ${size * env.unit}px ${family}`;
      c.direction = "ltr";
      c.textAlign = "center";
      c.lineJoin = "round";
      c.lineWidth = 3.5 * env.unit;
      c.strokeStyle = env.color("--paper");
      c.fillStyle = env.color(color);
      const digit = c.measureText("0").width;
      const widths = [...text].map((ch) => (ch >= "0" && ch <= "9" ? digit : c.measureText(ch).width));
      let at = x - widths.reduce((a, b) => a + b, 0);
      [...text].forEach((ch, i) => { c.strokeText(ch, at + widths[i] / 2, y); c.fillText(ch, at + widths[i] / 2, y); at += widths[i]; });
      c.restore();
    },
  };
  env.reset();
  return env;
}

async function setUp(figure, box) {
  const response = await fetch(box.dataset.explorable);
  if (!response.ok) throw new Error(`${box.dataset.explorable}: HTTP ${response.status}`);
  const spec = await response.json();
  const kind = kinds[spec.kind];
  if (!kind) throw new Error(`explorable ${figure.id}: no drawing for kind ${spec.kind}`);
  const c = spec.control;
  const span = c.max - c.min;
  const decimals = String(c.step).split(".")[1]?.length ?? 0;
  const snap = (v) => clamp(Number((Math.round((v - c.min) / c.step) * c.step + c.min).toFixed(decimals)), c.min, c.max);
  const [vx, vy, vw, vh] = kind.view;

  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; };
  const head = el("div", "xp-head");
  head.append(el("p", "xp-title", spec.title), el("p", "xp-instruction", spec.instruction));
  const stage = el("div", "xp-stage");
  stage.style.aspectRatio = `${vw} / ${vh}`;
  const canvas = el("canvas", "xp-canvas");
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", spec.title);
  const handle = el("div", "xp-handle");
  handle.setAttribute("aria-hidden", "true"); // The range input is the accessible control.
  const grip = el("span", "xp-grip");
  grip.innerHTML = '<svg viewBox="-12 -12 24 24" aria-hidden="true"><path d="M0 -6.5 L-4 -2.5 M0 -6.5 L4 -2.5 M0 -6.5 V6.5 M0 6.5 L-4 2.5 M0 6.5 L4 2.5"/></svg>';
  handle.append(el("span", "xp-grip-ring"), grip);
  stage.append(canvas, handle);

  const controls = el("div", "xp-controls");
  const id = `${figure.id}-xp`;
  const label = el("label", "xp-label-text", c.label);
  label.htmlFor = id;
  // The value: number, unit and note, each in a slot as wide as its longest text, so the line never moves.
  const output = el("output", "xp-output");
  output.htmlFor = id;
  const numSlot = el("bdi", "xp-num"), unitSlot = el("span", "xp-unit"), noteSlot = el("span", "xp-note");
  numSlot.dir = "ltr";
  output.append(numSlot, " ", unitSlot, " ", noteSlot);
  const track = el("div", "xp-track");
  track.dir = "ltr"; // Same direction as the chart axes on this site: the start of the process on the left.
  const input = el("input", "xp-range");
  Object.assign(input, { type: "range", id, min: c.min, max: c.max, step: c.step, value: c.start });
  const fill = el("span", "xp-fill");
  track.append(el("span", "xp-rail"), fill, input);
  const marks = el("div", "xp-marks");
  for (const mark of spec.marks ?? []) {
    const b = el("button", "xp-mark", mark.label);
    b.type = "button";
    const at = (mark.value - c.min) / span;
    b.style.setProperty("--at", at.toFixed(4));
    b.dataset.edge = at < 0.08 ? "start" : at > 0.92 ? "end" : "middle";
    b.setAttribute("aria-label", `${c.label}: ${mark.label}`);
    b.addEventListener("click", () => { markHintSeen(figure.id); animateTo(mark.value); });
    marks.append(b);
  }
  if (marks.childElementCount) track.append(marks);
  const reset = el("button", "xp-reset", "איפוס");
  reset.type = "button";
  const top = el("div", "xp-control-head");
  top.append(label, output);
  controls.append(top, track, reset);

  const readout = el("p", "xp-readout");
  // Screen readers hear the summary when a move ends, not on every frame of a drag.
  const live = el("p", "visually-hidden");
  live.setAttribute("aria-live", "polite");
  box.prepend(head, stage, controls, readout, live);
  box.hidden = false;

  {
    // Slot widths: every value of the control, measured once with the output's own font (no layout reads).
    const probe = document.createElement("canvas").getContext("2d");
    probe.font = getComputedStyle(output).font;
    const steps = Math.min(400, Math.round(span / c.step));
    const samples = [...Array(steps + 1).keys()].map((i) => kind.valueParts(snap(c.min + (span * i) / steps), spec));
    const widest = (text) => Math.ceil(Math.max(...samples.map((p) => probe.measureText(text(p)).width)));
    numSlot.style.minWidth = `${widest((p) => p.num) + 2}px`;
    unitSlot.style.minWidth = `${widest((p) => p.unit)}px`;
    noteSlot.style.minWidth = `${widest((p) => (p.note ? `(${p.note})` : ""))}px`;
  }
  const env = makeEnv(box);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error(`explorable ${figure.id}: no 2D canvas`);
  env.bind(ctx);
  const scene = kind.create(spec, env);
  let value = c.start, summary = "", scale = 1, moving = false;
  let frame = 0, tween = 0, pending = c.start;

  function drawCanvas(v) {
    const dpr = devicePixelRatio || 1;
    env.time = performance.now() / 1000;
    ctx.setTransform(dpr * scale, 0, 0, dpr * scale, -vx * dpr * scale, -vy * dpr * scale);
    ctx.clearRect(vx, vy, vw, vh);
    summary = scene.draw(ctx, v, env);
  }
  function paint(v) {
    value = v;
    drawCanvas(v);
    const [hx, hy] = scene.handle(v);
    handle.style.transform = `translate(${((hx - vx) * scale).toFixed(1)}px, ${((hy - vy) * scale).toFixed(1)}px)`;
    const parts = kind.valueParts(snap(v), spec);
    if (numSlot.textContent !== parts.num) numSlot.textContent = parts.num;
    if (unitSlot.textContent !== parts.unit) unitSlot.textContent = parts.unit;
    const note = parts.note ? `(${parts.note})` : "";
    if (noteSlot.textContent !== note) noteSlot.textContent = note;
    fill.style.transform = `scaleX(${((v - c.min) / span).toFixed(4)})`;
    // The paragraph changes when a move ends, so a drag does not reflow the page on every frame.
    if (!moving && readout.textContent !== summary) readout.textContent = summary;
  }
  // Pointer moves can come faster than frames: draw the newest value once per frame.
  function show(v) {
    pending = v;
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = 0; paint(pending); });
  }
  function setValue(v) {
    cancelAnimationFrame(tween); tween = 0;
    v = clamp(v, c.min, c.max);
    input.value = String(snap(v));
    show(v);
  }
  function animateTo(target, duration = 380) {
    target = snap(target);
    input.value = String(target);
    cancelAnimationFrame(tween);
    if (reduceMotion.matches || duration === 0) { moving = false; show(target); commit(); return; }
    moving = true;
    const from = value, start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      if (t === 1) moving = false;
      paint(from + (target - from) * easeOut(t));
      tween = t < 1 ? requestAnimationFrame(step) : 0;
      if (!tween) commit();
    };
    tween = requestAnimationFrame(step);
  }
  function commit() {
    input.setAttribute("aria-valuetext", valueText(kind, Number(input.value), spec));
    requestAnimationFrame(() => { if (!moving) { readout.textContent = summary; live.textContent = summary; } });
  }

  // touch-action: none on the handle stops scrolling; these also stop a long-press menu and a late scroll.
  handle.addEventListener("contextmenu", (e) => e.preventDefault());
  handle.addEventListener("touchmove", (e) => { if (stage.classList.contains("dragging")) e.preventDefault(); }, { passive: false });
  handle.addEventListener("pointerdown", (down) => {
    if (down.button !== 0) return;
    down.preventDefault();
    markHintSeen(figure.id);
    handle.setPointerCapture(down.pointerId);
    stage.classList.add("dragging");
    moving = true;
    const rect = canvas.getBoundingClientRect(); // Read once per drag: no layout reads while moving.
    const at = (e) => ({ x: (e.clientX - rect.left) / scale + vx, y: (e.clientY - rect.top) / scale + vy });
    const start = { point: at(down), value };
    const move = (e) => setValue(scene.drag(at(e), start));
    const end = () => {
      handle.removeEventListener("pointermove", move);
      stage.classList.remove("dragging");
      animateTo(value, 160); // Settle on the nearest step.
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", end, { once: true });
    handle.addEventListener("pointercancel", end, { once: true });
  });
  input.addEventListener("input", () => { moving = true; setValue(Number(input.value)); });
  input.addEventListener("change", () => { moving = false; show(value); commit(); });
  input.addEventListener("pointerdown", () => markHintSeen(figure.id));
  input.addEventListener("keydown", (e) => {
    const big = c.step * Math.max(1, Math.round(span / c.step / 10));
    const delta = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10 }[e.key];
    const base = Number(input.value); // The target of a running ease, so quick presses add up.
    let target = null;
    if (delta) target = base + (Math.abs(delta) === 10 || e.shiftKey ? Math.sign(delta) * big : delta * c.step);
    if (e.key === "Home") target = c.min;
    if (e.key === "End") target = c.max;
    if (target === null) return;
    e.preventDefault();
    markHintSeen(figure.id);
    animateTo(target, 220);
  });
  reset.addEventListener("click", () => animateTo(c.start, 520));

  // The canvas matches its box in device pixels; drawings work in their own units (`scale` CSS px each).
  new ResizeObserver(() => {
    const width = stage.clientWidth;
    if (!width) return;
    scale = width / vw;
    env.unit = 1 / scale;
    env.pixel = scale * (devicePixelRatio || 1);
    const dpr = devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(width * (vh / vw) * dpr);
    show(value);
  }).observe(stage);
  const retheme = () => { env.reset(); show(value); };
  // The canvas draws with the site font; draw again once it has loaded, or labels keep a fallback font.
  document.fonts.ready.then(retheme);
  document.fonts.addEventListener("loadingdone", retheme);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", retheme);
  new MutationObserver(retheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  commit();

  if (kind.animated) {
    let onScreen = false, running = false;
    const loop = () => {
      if (!onScreen || document.hidden || reduceMotion.matches) { running = false; return; }
      if (!frame && !tween && !moving) requestAnimationFrame(() => drawCanvas(value));
      setTimeout(loop, 1000 / FLOW_FPS);
    };
    const start = () => { if (!running && onScreen) { running = true; loop(); } };
    new IntersectionObserver((entries) => { onScreen = entries[0].isIntersecting; start(); }).observe(stage);
    document.addEventListener("visibilitychange", start);
  }

  // One nudge, the first time a visitor sees this explainer: the handle moves a little and comes back.
  if (!reduceMotion.matches && !hintSeen(figure.id) && c.hint) {
    new IntersectionObserver((entries, observer) => {
      if (!entries[0].isIntersecting) return;
      observer.disconnect();
      setTimeout(() => {
        if (hintSeen(figure.id)) return;
        markHintSeen(figure.id);
        stage.classList.add("hinting");
        const back = value;
        animateTo(back + c.hint, 650);
        setTimeout(() => { animateTo(back, 650); setTimeout(() => stage.classList.remove("hinting"), 700); }, 750);
      }, 500);
    }, { threshold: 0.6 }).observe(stage);
  }
}

const kinds = {}; // Filled by the drawing files, which run after this one; set-up waits for the figure to scroll near.
for (const figure of document.querySelectorAll("figure.has-explorable")) {
  const box = figure.querySelector(":scope > .explorable");
  const img = figure.querySelector(":scope > img");
  const group = document.createElement("div");
  group.className = "view-toggle";
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "תצוגת האיור");
  const make = (text, explain) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.addEventListener("click", () => setView(explain));
    group.append(b);
    return b;
  };
  const explainButton = make("הדגמה אינטראקטיבית", true);
  const printButton = make("האיור המודפס", false);
  let ready = false;
  const setView = (explain) => {
    explainButton.setAttribute("aria-pressed", String(explain));
    printButton.setAttribute("aria-pressed", String(!explain));
    box.hidden = !explain || !ready;
    if (img) img.hidden = explain && ready;
  };
  figure.prepend(group);
  group.hidden = true; // Shown once the explainer works; until then the printed image stays.
  new IntersectionObserver((entries, observer) => {
    if (!entries[0].isIntersecting) return;
    observer.disconnect();
    setUp(figure, box)
      .then(() => { ready = true; group.hidden = false; setView(true); })
      .catch((err) => { box.hidden = true; group.remove(); console.error(err); });
  }, { rootMargin: "400px" }).observe(figure);
}
return { kinds, interpolate, number, iso, MINUS, clamp, ramp, polyline, shape };
})();
