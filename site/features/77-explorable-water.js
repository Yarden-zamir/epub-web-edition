// The Dead Sea's water (chapter a36). Two kinds:
// - inflow (figure fig-a36-08): the yearly inflow of the Red Sea–Dead Sea conduit sets the yearly level change, read
//   from the digitized chart fig-a36-11 (two lines: brine and sea water). The level goes on from today's measured
//   level at that rate, as a straight line to 2070.
// - layers (figure fig-a36-01): the layered lake of Neev and Emery (1967), from the digitized profile fig-a36-12.
//   The upper layer grows denser and mixes down; when it is as dense as the lower layer, the whole lake mixes.
explorableKit.kinds.inflow = (() => {
const { interpolate, number, iso, MINUS, polyline, shape } = explorableKit;

const W = 600, H = 340;
const PLOT = { left: 62, right: 494, top: 22, bottom: 304 };
const YEARS = [1976, 2070], LEVELS = [-500, -395];
const xOf = (year) => PLOT.left + ((year - YEARS[0]) / (YEARS[1] - YEARS[0])) * (PLOT.right - PLOT.left);
const yOf = (level) => PLOT.top + ((LEVELS[1] - level) / (LEVELS[1] - LEVELS[0])) * (PLOT.bottom - PLOT.top);
const M_TO_Y = (PLOT.bottom - PLOT.top) / (LEVELS[1] - LEVELS[0]);
function decimalYear(date) {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) throw new Error(`inflow: bad date ${date}`);
  return y + (m - 1) / 12 + (d - 1) / 365;
}
const signed = (v) => `${v < 0 ? MINUS : v > 0 ? "+" : ""}${number(Math.abs(v), 2)}`;
const level = (v) => `${MINUS}${number(Math.abs(v), 1)}`;
// Labels draw right to left: a signed number keeps its sign on the left only inside a left-to-right isolate.
const ltr = (text) => `\u2066${text}\u2069`;
// Both lines of the chart at one inflow: brine (RB, the upper line) and sea water (SW).
const rates = (spec, inflow) => ({ rb: interpolate(spec.data.rb.points, inflow), sw: interpolate(spec.data.sw.points, inflow) });

function valueParts(inflow, spec) {
  const { rb, sw } = rates(spec, inflow);
  return { num: number(inflow), unit: spec.control.unit, note: `${iso(signed(sw))} עד ${iso(signed(rb))} מ' בשנה` };
}

function create(spec, env) {
  waterContext(spec);
  const L = spec.labels, t = spec.texts;
  const history = spec.data.level.points;
  if (!history.length) throw new Error("inflow: no level data");
  const [lastDate, today] = history.at(-1);
  const t0 = decimalYear(lastDate), end = spec.end_year, years = end - t0;
  if (years <= 0) throw new Error(`inflow: the last level date ${lastDate} is after ${end}`);
  const historyLine = polyline(new Path2D(), history.map(([date, lvl]) => [xOf(decimalYear(date)), yOf(lvl)]));
  const mid = (inflow) => { const r = rates(spec, inflow); return (r.rb + r.sw) / 2; };
  // Drawing units of handle height per unit of inflow, so a drag follows the pointer.
  const unitsPerInflow = ((mid(spec.control.max) - mid(spec.control.min)) * years * M_TO_Y) / (spec.control.max - spec.control.min);
  const noAction = spec.no_action_2070;

  function frame(c, small) {
    c.fillStyle = env.color("--paper");
    c.fillRect(0, 0, W, H);
    c.strokeStyle = env.color("--rule");
    c.lineWidth = 1;
    for (let lvl = -400; lvl >= LEVELS[0]; lvl -= 20) {
      c.stroke(shape([[PLOT.left, yOf(lvl)], [PLOT.right, yOf(lvl)]], false));
      env.label(c, ltr(`${MINUS}${-lvl}`), PLOT.left - 6, yOf(lvl) + 4, { align: "right", size: 11, weight: 500, color: "--muted" });
    }
    for (const year of small ? [1980, 2026, 2070] : [1980, 2000, 2026, 2050, 2070])
      env.label(c, String(year), xOf(year), PLOT.bottom + 18, { size: 11, weight: 500, color: "--muted" });
    if (!small) env.label(c, L.y_axis, 10, 12, { align: "left", size: 11, weight: 500, color: "--muted" }); // No room on a phone: the unit is in the readout.
    // Today: a thin vertical rule.
    c.setLineDash([2, 4]);
    c.stroke(shape([[xOf(t0), PLOT.top], [xOf(t0), PLOT.bottom]], false));
    c.setLineDash([]);
    // The steady level: no change from today on.
    c.strokeStyle = env.color("--muted");
    c.setLineDash([6, 5]);
    c.stroke(shape([[xOf(t0), yOf(today)], [PLOT.right, yOf(today)]], false));
    c.setLineDash([]);
    env.label(c, small ? L.steady_short : L.steady, PLOT.right - 4, yOf(today) - 7, { align: "right", size: 11, color: "--muted" });
    c.strokeStyle = env.color("--ink");
    c.lineWidth = 2;
    c.lineJoin = "round";
    c.stroke(historyLine);
    env.label(c, L.measured, xOf(1990), yOf(-421), { size: 12, color: "--soft" });
    // The policy document's forecast without action, for 2070.
    c.fillStyle = env.color("--accent");
    c.beginPath();
    c.arc(xOf(end), yOf(noAction), 4, 0, Math.PI * 2);
    c.fill();
    env.label(c, small ? L.no_action_short : L.no_action, xOf(end) - (small ? 34 : 10), yOf(noAction) + 4, { align: "right", size: 11, color: "--accent" });
  }

  function draw(ctx, inflow) {
    const small = env.unit > 1.3;
    const view = [0, 0, W, H];
    ctx.drawImage(env.layer(`frame${small ? "s" : ""}`, view, (c) => frame(c, small)), ...view);
    const { rb, sw } = rates(spec, inflow);
    const x0 = xOf(t0), y0 = yOf(today), x1 = xOf(end);
    const yRb = yOf(today + rb * years), ySw = yOf(today + sw * years);
    ctx.fillStyle = env.color("--xp-lake");
    ctx.globalAlpha = 0.22;
    ctx.fill(shape([[x0, y0], [x1, yRb], [x1, ySw]]));
    ctx.globalAlpha = 1;
    ctx.strokeStyle = env.color("--xp-fresh-ink");
    ctx.lineWidth = 2;
    ctx.stroke(shape([[x0, y0], [x1, yRb]], false));
    ctx.setLineDash([5, 4]);
    ctx.stroke(shape([[x0, y0], [x1, ySw]], false));
    ctx.setLineDash([]);
    ctx.fillStyle = env.color("--ink");
    ctx.beginPath();
    ctx.arc(x0, y0, 3.5, 0, Math.PI * 2);
    ctx.fill();
    env.label(ctx, `${L.today} ${ltr(level(today))}`, x0 - 8, y0 + 18, { align: "right", size: 11, color: "--ink" });
    // Level in 2070 at the end of each line; one label for both when they would touch.
    const lvlRb = today + rb * years, lvlSw = today + sw * years;
    const gap = 15 * env.unit, lx = x1 + 14 * env.unit; // Clear of the 26 px grip.
    const look = { align: "left", size: small ? 11 : 12, weight: 700, color: "--xp-fresh-ink" };
    const endLabel = (lvl) => ltr(`${MINUS}${number(Math.abs(lvl), small ? 0 : 1)}`); // Whole metres on a phone: no room.
    if (Math.abs(ySw - yRb) < gap) env.label(ctx, endLabel((lvlRb + lvlSw) / 2), lx, (yRb + ySw) / 2 + 4, look);
    else {
      env.label(ctx, endLabel(lvlRb), lx, yRb + 4, look);
      env.label(ctx, endLabel(lvlSw), lx, ySw + 4, look);
    }

    const shown = Math.round(inflow / spec.control.step) * spec.control.step;
    const r = rates(spec, shown);
    const trend = r.rb < 0 ? t.falls : r.sw > 0 ? t.rises : t.near_steady;
    let text = t.rate.replace("{inflow}", iso(number(shown))).replace("{trend}", trend)
      .replace("{low}", iso(signed(r.sw))).replace("{high}", iso(signed(r.rb)))
      .replace("{end_low}", iso(level(today + r.sw * years))).replace("{end_high}", iso(level(today + r.rb * years)));
    const note = spec.notes.find((n) => n.value === shown);
    if (note) text += ` ${note.text}`;
    return text;
  }

  return {
    draw,
    handle: (inflow) => [xOf(end), yOf(today + mid(inflow) * years)],
    drag: (point, start) => start.value + (start.point.y - point.y) / unitsPerInflow,
  };
}
return { view: [0, 0, W, H], valueParts, create };
})();

explorableKit.kinds.layers = (() => {
const { interpolate, number, ramp, polyline, shape } = explorableKit;

const W = 600, H = 372;
const SURFACE = 40, BOTTOM = 330, DEPTH = 330; // Drawing y of the surface and of the deepest point (DEPTH metres).
const yOf = (depth) => SURFACE + (depth / DEPTH) * (BOTTOM - SURFACE);
const CHART = { left: 52, right: 282 }, AXIS = [170, 174];
const xOf = (density) => CHART.left + ((density - AXIS[0]) / (AXIS[1] - AXIS[0])) * (CHART.right - CHART.left);
const LAKE = [[322, SURFACE], [348, 92], [388, 200], [418, BOTTOM], [522, BOTTOM], [558, 200], [580, 92], [592, SURFACE]];
const LIFE = [[352, 47], [371, 58], [392, 45], [410, 61], [431, 50], [452, 57], [470, 46], [492, 60], [513, 49], [534, 56], [553, 45], [572, 52]];

// "#rrggbb" tokens only (72-explorables.css): the lake colour mixes two of them by density.
function rgb(hex) {
  const parts = [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16));
  if (hex.length !== 7 || !hex.startsWith("#") || parts.some(Number.isNaN)) throw new Error(`layers: colour ${hex} is not #rrggbb`);
  return parts;
}
const mix = (a, b, t) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(" ")})`;

function create(spec, env) {
  waterContext(spec);
  const L = spec.labels, t = spec.texts;
  // The printed profile, sampled each metre. Density never falls with depth in a stable lake, so a running maximum
  // removes the digitizing noise (a few hundredths) where a deeper reading is lighter than the one above it.
  const curve = spec.data.profile.points.map(([density, depth]) => [-depth, density]).sort((a, b) => a[0] - b[0]);
  if (curve.length < 2) throw new Error("layers: no profile");
  const base = [];
  for (let z = 0, top = -Infinity; z <= DEPTH; z++) base.push((top = Math.max(top, interpolate(curve, z))));
  const lightest = base[0], densest = base[DEPTH];
  const upper = (v) => lightest + (v / 100) * (densest - lightest);
  const at = (v, z) => Math.max(base[z], upper(v));
  const lake = shape(LAKE);
  const measured = new Path2D();
  for (const [density, depth] of spec.data.measured.points) {
    measured.moveTo(xOf(density) + 2, yOf(-depth));
    measured.arc(xOf(density), yOf(-depth), 2, 0, Math.PI * 2);
  }
  const printed = polyline(new Path2D(), base.map((d, z) => [xOf(d), yOf(z)]).filter((_, z) => z % 2 === 0));
  const runoff = new Path2D("M300 6 C 312 14, 318 26, 330 38");

  function frame(c, small) {
    c.fillStyle = env.color("--paper");
    c.fillRect(0, 0, W, H);
    c.strokeStyle = env.color("--rule");
    c.lineWidth = 1;
    for (const depth of [0, 100, 200, 300]) {
      c.stroke(shape([[CHART.left, yOf(depth)], [CHART.right, yOf(depth)]], false));
      env.label(c, number(depth), CHART.left - 6, yOf(depth) + 4, { align: "right", size: 11, weight: 500, color: "--muted" });
    }
    for (let d = AXIS[0]; d <= AXIS[1]; d++) {
      c.stroke(shape([[xOf(d), SURFACE], [xOf(d), BOTTOM]], false));
      env.label(c, number(d), xOf(d), BOTTOM + 16, { size: 11, weight: 500, color: "--muted" });
    }
    env.label(c, L.depth_axis, 4, SURFACE - 22, { align: "left", size: 11, weight: 500, color: "--muted" });
    env.label(c, small ? L.density_axis_short : L.density_axis, (CHART.left + CHART.right) / 2, BOTTOM + (small ? 38 : 30), { size: 11, weight: 500, color: "--muted" });
    c.fillStyle = env.color("--muted");
    c.globalAlpha = 0.45;
    c.fill(measured);
    c.globalAlpha = 1;
    // Ground around the lake.
    c.fillStyle = env.gradient("land", 0, SURFACE, 0, H, [[0, "--xp-land"], [1, "--xp-land-deep"]]);
    c.fillRect(306, SURFACE, W - 306, H - SURFACE);
  }

  function draw(ctx, v) {
    const small = env.unit > 1.3;
    const view = [0, 0, W, H];
    ctx.drawImage(env.layer(`frame${small ? "s" : ""}`, view, (c) => frame(c, small)), ...view);
    const mixed = ramp(v, 92, 100);
    const u = upper(v);
    // Lake water: colour by density at each depth, light (the lightest printed value) to dark (the densest).
    const light = rgb(env.color("--xp-fresh")), dark = rgb(env.color("--xp-lake-deep"));
    const g = ctx.createLinearGradient(0, SURFACE, 0, BOTTOM);
    for (let z = 0; z <= DEPTH; z += 6) g.addColorStop(z / DEPTH, mix(light, dark, (at(v, z) - lightest) / (densest - lightest)));
    ctx.fillStyle = g;
    ctx.fill(lake);
    ctx.strokeStyle = env.color("--xp-land-edge");
    ctx.lineWidth = 1.2;
    ctx.stroke(lake);

    // The layer boundary: where the water is most of the way to the lower layer's density. Gone once mixed.
    const step = densest - u;
    const boundary = base.findIndex((d) => d >= u + 0.85 * step);
    const lineAlpha = 1 - ramp(v, 75, 95);
    if (boundary > 0 && lineAlpha > 0.01) {
      ctx.globalAlpha = lineAlpha;
      ctx.strokeStyle = env.color("--ink");
      ctx.lineWidth = 1.2;
      ctx.setLineDash([5, 4]);
      ctx.stroke(shape([[CHART.left, yOf(boundary)], [W - 6, yOf(boundary)]], false));
      ctx.setLineDash([]);
      env.label(ctx, v < 1 && !small ? L.boundary_printed : L.boundary, CHART.right - 4, yOf(boundary) - 6, { align: "right", size: 11 });
      ctx.globalAlpha = 1;
    }

    // Runoff feeds the upper layer; it shrinks as the upper layer grows saltier.
    const flow = 1 - ramp(v, 0, 90);
    ctx.strokeStyle = env.color("--xp-fresh-ink");
    ctx.lineCap = "round";
    ctx.lineWidth = 1.5 + 4 * flow;
    ctx.globalAlpha = 0.35 + 0.65 * flow;
    ctx.stroke(runoff);
    ctx.globalAlpha = 1;
    ctx.lineCap = "butt";
    env.label(ctx, L.runoff, 296, 14, { align: "right", size: 12, color: "--xp-fresh-ink" });

    // Algae and archaea of the upper layer fade as its salinity rises.
    const life = 1 - ramp(v, 20, 85);
    if (life > 0.01) {
      ctx.globalAlpha = life;
      ctx.fillStyle = env.color("--xp-copper");
      for (const [x, y] of LIFE) { ctx.beginPath(); ctx.arc(x, y, 2.4, 0, Math.PI * 2); ctx.fill(); }
      if (!small) env.label(ctx, L.life, 457, 78, { size: 11, color: "--xp-copper-edge" });
      ctx.globalAlpha = 1;
    }
    const layered = 1 - mixed;
    if (layered > 0.01) {
      ctx.globalAlpha = layered;
      env.label(ctx, L.upper, 470, small ? 72 : 96);
      env.label(ctx, L.lower, 470, 220);
      env.label(ctx, L.lower_note, 470, small ? 250 : 238, { size: 11, weight: 500 });
      ctx.globalAlpha = 1;
    }
    if (mixed > 0.01) {
      ctx.globalAlpha = mixed;
      ctx.strokeStyle = env.color("--xp-salt");
      ctx.lineWidth = 1.8;
      for (const [cx, rx] of [[430, 44], [512, 40]]) { // Two overturning loops, top to floor.
        ctx.beginPath();
        ctx.ellipse(cx, 180, rx, 120, 0, 0.25, Math.PI * 2 - 0.25);
        ctx.stroke();
      }
      ctx.fillStyle = env.color("--xp-salt");
      for (const [x, y, dir] of [[474, 180, 1], [552, 180, -1]]) ctx.fill(shape([[x - 5, y - 6 * dir], [x + 5, y - 6 * dir], [x, y + 4 * dir]]));
      env.label(ctx, small ? L.mixed_short : L.mixed, 470, 70);
      env.label(ctx, L.oxygen, 470, 300, { size: 11 });
      ctx.fillStyle = env.color("--xp-salt");
      ctx.strokeStyle = env.color("--xp-salt-edge");
      ctx.lineWidth = 0.8;
      for (let x = 430; x <= 510; x += 12) { const p = shape([[x, BOTTOM], [x + 4, BOTTOM - 7], [x + 8, BOTTOM]]); ctx.fill(p); ctx.stroke(p); }
      env.label(ctx, L.gypsum, 470, BOTTOM + 18, { size: 11 });
      ctx.globalAlpha = 1;
    }

    // The profile now: the printed one, with the upper layer mixed down to where it meets denser water.
    ctx.globalAlpha = 0.5 * ramp(v, 0, 6);
    ctx.strokeStyle = env.color("--muted");
    ctx.lineWidth = 1.2;
    ctx.setLineDash([3, 3]);
    ctx.stroke(printed);
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = env.color("--series");
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke(polyline(new Path2D(), base.map((_, z) => [xOf(at(v, z)), yOf(z)]).filter((_, z) => z % 2 === 0 || z === DEPTH)));

    const shown = Math.round(v);
    return shown === 0 ? t.start : shown >= 100 ? t.mixed : t.saltier;
  }

  const span = xOf(densest) - xOf(lightest);
  return {
    draw,
    handle: (v) => [xOf(upper(v)), yOf(14)],
    drag: (point, start) => start.value + ((point.x - start.point.x) / span) * 100,
  };
}
return { view: [0, 0, W, H], valueParts: (v, spec) => ({ num: number(v), unit: spec.control.unit, note: v >= 100 ? spec.labels.state_mixed : spec.labels.state_layered }), create };
})();

// A few lines of context under the title: what the explainer shows and why it matters in the chapter.
// The shared kit has no field for it, so each kind of this file adds the paragraph itself.
// Revisit when 72-explorables.js renders a "context" field for every explainer.
function waterContext(spec) {
  if (!spec.context) return;
  const head = document.querySelector(`#${CSS.escape(spec.figure)} > .explorable > .xp-head`);
  if (!head) throw new Error(`explorable ${spec.figure}: no head for the context`);
  const p = document.createElement("p");
  p.className = "xp-context";
  p.textContent = spec.context;
  head.append(p);
}
