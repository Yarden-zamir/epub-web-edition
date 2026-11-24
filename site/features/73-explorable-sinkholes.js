// Sinkholes as the Dead Sea drops (figure fig-a14-07). A schematic west-east section of the shore:
// the lake level sets the shoreline, and the interface between fresh groundwater (above) and saturated
// Dead Sea brine (below) runs from the shoreline down to the west. Where the interface sinks below the
// salt layer, fresh groundwater dissolves the salt; cavities grow and their roofs collapse.
// The control value is the lake level in metres below sea level.
explorableKit.kinds.sinkholes = (() => {
const { interpolate, number, iso, MINUS, ramp, polyline, shape } = explorableKit;

const W = 600, H = 330;
// Schematic geometry in (x, elevation in metres). Fitted so that the two levels of the printed figure give
// its two states: at -395 the salt lies fully below the interface; at -414 its western part lies above it.
const GROUND = [[0, -365], [130, -380], [250, -395], [500, -442], [600, -470]];
// Top 20 to 30 m below the ground (book: 20 to 70 m). The thickness is schematic (the book gives none for this shore).
const SALT = { from: 105, to: 470, dip: 0.15, thick: 14 };
const saltTop = (x) => -386 - SALT.dip * x;
const INTERFACE_DIP = 0.03; // Metres per unit of x, down to the west.
const WATER_TABLE_WEST = -382; // Groundwater table at the west edge.
// Dissolution (schematic, after the printed figure, not a model of the rate): fresh water eats the salt from its top
// once the interface sinks below the top of the layer, and from its bottom once it sinks below the whole layer. Each
// side is eaten deeper with every metre of level drop after that (EAT metres for the full eaten share, scaled by seeded
// noise), up to half of the layer or less, so chunky pieces stay. At a few sites the two fronts meet: there the salt
// is gone, the layer breaks into separate jagged pieces, and above each gap the ground collapses.
const EAT = 9, GRID = 2.5, SEED = 7, GAPS = 4; // Any fixed seed: it fixes the shapes only.
const STREAKS = [0.15, 0.35, 0.55, 0.75, 0.92]; // Fresh-water flow lines, as fractions between water table and interface.

// Seeded random numbers (mulberry32), so the front looks the same on every visit.
function random(seed) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const SCALE = 2.7; // Drawing units per metre of height.
const Y = (elev) => 14 + (-362 - elev) * SCALE;
const elevAt = (y) => -362 - (y - 14) / SCALE;
const K = INTERFACE_DIP * SCALE; // The interface in drawing units: y = y0 - K * x.
const ground = (x) => interpolate(GROUND, x);

function shoreline(level) {
  // The ground falls monotonically, so bisection finds where it meets the lake surface.
  let lo = 0, hi = W;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (ground(mid) > level) lo = mid; else hi = mid;
  }
  return lo;
}
const interfaceAt = (x, level, xs) => level - INTERFACE_DIP * (xs - x);
// Fresh water reaches the salt at x, at the top of the layer (below = 0) or below the whole layer (below = SALT.thick).
const exposed = (x, level, below = 0) => interfaceAt(x, level, shoreline(level)) < saltTop(x) - below;

// The level at which fresh water first reaches the salt at x (its top, or below it), or null if never in range.
function exposureLevel(x, min, max, below = 0) {
  if (!exposed(x, -max, below)) return null;
  let lo = -min, hi = -max; // lo: not exposed (higher level), hi: exposed.
  if (exposed(x, lo, below)) return lo;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (exposed(x, mid, below)) hi = mid; else lo = mid;
  }
  return hi;
}

const groundLine = (from, to) => [
  [from, Y(ground(from))],
  ...GROUND.filter(([gx]) => gx > from && gx < to).map(([gx, e]) => [gx, Y(e)]),
  [to, Y(ground(to))],
];

// First measured date at or below the level, or null above the first measurement (1976).
function dateOf(level, spec) {
  const first = spec.data.level.points.find(([, value]) => value <= level);
  return first ? new Date(first[0]) : null;
}

function valueParts(depth, spec) {
  const mark = spec.marks.find((m) => m.value === depth && m.year);
  const date = dateOf(-depth, spec);
  const firstMeasured = -spec.data.level.points[0][1];
  const when = mark ? mark.year
    : date && depth >= firstMeasured ? date.toLocaleDateString("he-IL", { month: "long", year: "numeric" })
    : "בין 1960 ל־1976";
  return { num: number(depth, 1), unit: spec.control.unit, note: when };
}

function create(spec) {
  const L = spec.labels;
  const t = spec.texts;
  const { min, max } = spec.control;
  const line = groundLine(0, W);
  const below = shape([...line, [W, H + 40], [0, H + 40]]);
  const above = shape([[0, -40], [W, -40], ...[...line].reverse()]);
  const groundPath = shape(line, false);
  const beds = new Path2D();
  for (let i = 1; i <= 5; i++) polyline(beds, line.map(([x, y]) => [x, y + 26 * i + (x / W) * 8])); // Texture only.
  const saltAngle = Math.atan(SALT.dip * SCALE);
  const rand = random(SEED);
  const thickPx = SALT.thick * SCALE;
  const smooth = (values, passes) => {
    let v = values;
    for (let k = 0; k < passes; k++) v = v.map((x, i) => (v[Math.max(0, i - 1)] + 2 * x + v[Math.min(v.length - 1, i + 1)]) / 4);
    return v;
  };
  const scaled = (v) => { const lo = Math.min(...v), hi = Math.max(...v); return v.map((x) => (x - lo) / (hi - lo)); };
  const grid = [];
  for (let x = SALT.from; x <= SALT.to; x += GRID) grid.push(x);
  // Per point: how fast each side is eaten (smooth noise: broad bites) and a fine wobble for a hand-drawn edge.
  const topRate = scaled(smooth(grid.map(() => rand()), 6)), bottomRate = scaled(smooth(grid.map(() => rand()), 6));
  const topJag = smooth(grid.map(() => rand() * 2 - 1), 1), bottomJag = smooth(grid.map(() => rand() * 2 - 1), 1);
  const cols = grid.map((x, i) => ({
    x, top: Y(saltTop(x)), bottom: Y(saltTop(x) - SALT.thick),
    atTop: exposureLevel(x, min, max), atBottom: exposureLevel(x, min, max, SALT.thick),
    rt: topRate[i], rb: bottomRate[i], jt: topJag[i], jb: bottomJag[i],
  }));
  const bite = (at, level, rate, most) => (at === null ? 0 : Math.max(0, Math.min(most, ((at - level) / EAT) * (0.35 + 1.1 * rate))));
  // The eaten share from the top and from the bottom at a level; their sum of 1 or more means a gap.
  // Gap sites: where both sides bite fastest, at least 40 units apart, at most GAPS. Near a site the eaten share may
  // reach the full layer; elsewhere at most 0.5 from the top and 0.4 from the bottom.
  const sum = (col) => (col ? col.rt + col.rb : 0);
  const peaks = cols.filter((col, i) => col.atBottom !== null && sum(col) >= sum(cols[i - 1]) && sum(col) >= sum(cols[i + 1]) && sum(col) > 1);
  const sites = [];
  for (const col of [...peaks].sort((c1, c2) => sum(c2) - sum(c1))) if (sites.length < GAPS && sites.every((site) => Math.abs(site.x - col.x) >= 40)) sites.push(col);
  for (const col of cols) {
    const near = Math.max(0, ...sites.map((site) => 1 - Math.abs(site.x - col.x) / 8));
    col.topMost = 0.12 + 0.38 * col.rt + 0.6 * near;
    col.bottomMost = 0.1 + 0.3 * col.rb + 0.6 * near;
  }
  // The eaten share from the top and from the bottom at a level; their sum of 1 or more means a gap.
  const eatenAt = (col, level) => [bite(col.atTop, level, col.rt, col.topMost), bite(col.atBottom, level, col.rb, col.bottomMost)];
  // A collapse at each gap site: a funnel straight above the gap, from the sloping surface down through the gap,
  // and a pit at the surface. Its top follows the ground, so nothing sticks out of the slope.
  const holes = sites.sort((c1, c2) => c1.x - c2.x).map((col) => {
    const x = col.x, size = 0.9 + 0.2 * col.rt, w = 8 * size;
    const surface = (dx) => Y(ground(x + dx));
    const funnel = shape([
      [x - w * 1.6, surface(-w * 1.6) - 2], [x - w * 1.5, surface(-w * 1.5) + 3], [x - 3 * size, col.top], [x - 2 * size, col.bottom],
      [x + 2 * size, col.bottom], [x + 3 * size, col.top], [x + w * 1.5, surface(w * 1.5) + 3], [x + w * 1.6, surface(w * 1.6) - 2],
    ]);
    return { x, col, size, w, surface, funnel };
  });
  const arrowRight = new Path2D("M-12 0 H9 M3 -5 L10 0 L3 5");
  const arrowLeft = new Path2D("M12 0 H-9 M-3 -5 L-10 0 L-3 5");

  function draw(ctx, depth, env) {
    const level = -depth;
    const xs = shoreline(level);
    const yL = Y(level);
    const yI0 = Y(interfaceAt(0, level, xs));
    const wt0 = Y(WATER_TABLE_WEST);
    const wt = (x) => wt0 + ((yL - wt0) * x) / xs;
    const yI = (x) => yI0 - K * x;
    const u = env.unit;

    const small = u > 1.3; // Phones: fewer labels.
    // Fixed parts come from cached bitmaps; only water, salt dissolving, cavities, arrows and moving labels are drawn.
    ctx.drawImage(env.layer("back", [0, 0, W, H], (c) => {
      c.fillStyle = env.gradient("sky", 0, 0, 0, H, [[0, "--xp-sky-top"], [1, "--xp-sky"]]);
      c.fillRect(0, 0, W, H);
      c.clip(below);
      c.fillStyle = env.gradient("land", 0, 0, 0, H, [[0, "--xp-land"], [1, "--xp-land-deep"]]);
      c.fillRect(0, 0, W, H);
      c.globalAlpha = 0.16;
      c.strokeStyle = env.color("--xp-land-edge");
      c.lineWidth = 1;
      c.stroke(beds);
    }), 0, 0, W, H);
    ctx.save();
    ctx.clip(below);
    ctx.fillStyle = env.color("--xp-fresh");
    ctx.fill(shape([[0, wt0], [W, wt(W)], [W, H], [0, H]]));
    ctx.fillStyle = env.color("--xp-brine");
    ctx.fill(shape([[0, yI0], [W, yI(W)], [W, H], [0, H]]));
    ctx.strokeStyle = env.color("--xp-fresh-ink");
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 4]);
    ctx.lineDashOffset = -env.time * 6;
    ctx.stroke(shape([[0, wt0], [xs, yL]], false));
    ctx.setLineDash([]);
    ctx.lineDashOffset = 0;
    ctx.strokeStyle = env.color("--ink");
    ctx.stroke(shape([[0, yI0], [xs, yL]], false));
    ctx.restore();

    // Fresh groundwater flows east under, over and through the exposed salt; under reduced motion, still arrows (below).
    const flowing = !reduceMotion.matches;
    if (flowing) {
      ctx.save();
      ctx.clip(below);
      ctx.strokeStyle = env.color("--xp-fresh-ink");
      ctx.globalAlpha = 0.6;
      ctx.lineWidth = 1.3;
      ctx.lineCap = "round";
      ctx.setLineDash([5, 9]);
      STREAKS.forEach((f, i) => {
        const end = xs - 4;
        ctx.lineDashOffset = -env.time * 14 - i * 5;
        ctx.stroke(shape([[0, wt0 + f * (yI0 - wt0)], [end, wt(end) + f * (yI(end) - wt(end))]], false));
      });
      ctx.restore();
    }

    // The salt that is left: pieces between the gaps, each with an eaten top and bottom edge (drawn over the streaks,
    // which so show only around the pieces and through the gaps).
    let deepest = 0, frontEnd = SALT.from;
    const pieces = new Path2D();
    let run = [];
    const closeRun = () => {
      if (run.length >= 4) { // Shorter bits count as dissolved: no thin slivers.
        const edge = (points, i) => { // A smooth edge through the midpoints of the points.
          pieces.lineTo(points[0][0], points[0][i]);
          for (let k = 1; k < points.length; k++) {
            const [x0, y0] = [points[k - 1][0], points[k - 1][i]], [x1, y1] = [points[k][0], points[k][i]];
            pieces.quadraticCurveTo(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2);
          }
          pieces.lineTo(points.at(-1)[0], points.at(-1)[i]);
        };
        pieces.moveTo(run[0][0], run[0][1]);
        edge(run, 1);
        edge([...run].reverse(), 2);
        pieces.closePath();
      }
      run = [];
    };
    for (const col of cols) {
      const [t, b] = eatenAt(col, level);
      if (t + b >= 0.97) { closeRun(); continue; } // A gap: no salt left here.
      const wobble = (side) => 2.4 * Math.min(1, side * 5); // Eaten edges are ragged; untouched ones stay straight.
      run.push([col.x, col.top + t * thickPx + col.jt * wobble(t), col.bottom - b * thickPx + col.jb * wobble(b)]);
      deepest = Math.max(deepest, t + b);
      if (t > 0.02) frontEnd = col.x;
    }
    closeRun();
    ctx.fillStyle = env.gradient("salt", 0, Y(saltTop(SALT.from)), 0, Y(saltTop(SALT.to) - SALT.thick), [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
    ctx.fill(pieces);
    ctx.strokeStyle = env.color("--xp-salt-edge");
    ctx.lineWidth = 1.2;
    ctx.lineJoin = "round";
    ctx.stroke(pieces);
    if (flowing && deepest > 0.2) { // Grains of salt leave the eaten edges with the flow and fade.
      ctx.fillStyle = env.color("--xp-salt");
      cols.forEach((col, i) => {
        const [t] = eatenAt(col, level);
        if (i % 11 || t < 0.25) return;
        const phase = (env.time * 0.3 + i * 0.137) % 1;
        ctx.globalAlpha = (1 - phase) * 0.85;
        ctx.beginPath();
        ctx.arc(col.x + phase * 16, col.top + t * thickPx * 0.6 - 2 - phase * 4, 1.3, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    let fallen = 0;
    for (const h of holes) {
      const [t, b] = eatenAt(h.col, level);
      const down = ramp(t + b, 0.97, 1.05); // Only once the gap below is open.
      if (down > 0.01) {
        // The funnel shows from the surface down to a depth that grows with `down`, under the ground only.
        const reach = h.surface(0) + (h.col.bottom - h.surface(0)) * down;
        ctx.save();
        ctx.clip(below);
        ctx.beginPath();
        ctx.rect(0, 0, W, reach);
        ctx.clip();
        ctx.fillStyle = env.color("--xp-land-edge");
        ctx.globalAlpha = 0.32;
        ctx.fill(h.funnel);
        ctx.globalAlpha = 1;
        ctx.strokeStyle = env.color("--xp-land-edge");
        ctx.lineWidth = 0.8;
        ctx.setLineDash([2, 2]);
        ctx.stroke(h.funnel);
        ctx.setLineDash([]);
        ctx.restore();
        // The pit: both ends on the ground line, its middle as deep as `down` allows.
        const left = h.x - h.w * 1.7, right = h.x + h.w * 1.7;
        const yl = h.surface(-h.w * 1.7), yr = h.surface(h.w * 1.7), mid = h.surface(0) + 10 * h.size * down;
        ctx.fillStyle = env.color("--xp-void");
        ctx.beginPath();
        ctx.moveTo(left, yl);
        ctx.quadraticCurveTo(h.x, 2 * mid - (yl + yr) / 2, right, yr); // The curve's middle lands at `mid`.
        ctx.closePath();
        ctx.fill();
      }
      if (down > 0.5) fallen++;
    }
    const open = deepest > 0.05 ? 1 : 0;

    ctx.save();
    ctx.clip(above);
    ctx.fillStyle = env.gradient("lake", 0, Y(-395), 0, H, [[0, "--xp-lake"], [1, "--xp-lake-deep"]]);
    ctx.fillRect(0, yL, W, H - yL);
    ctx.strokeStyle = env.color("--xp-surface");
    ctx.lineWidth = 2.5;
    ctx.stroke(shape([[0, yL], [W, yL]], false));
    ctx.lineWidth = 1.5;
    ctx.lineCap = "round";
    ctx.globalAlpha = 0.55;
    for (let i = 0; i < 5; i++) { // Glints drift slowly east across the lake and wrap round.
      const x = xs + 8 + ((i * 53 + env.time * 7) % Math.max(1, W - xs - 16));
      const y = yL + 7 + ((i * 11) % 22);
      if (y < Y(ground(x)) - 3) ctx.stroke(shape([[x - 6, y], [x + 6, y]], false));
    }
    ctx.restore();
    ctx.drawImage(env.layer("top", [0, 0, W, H], (c) => {
      c.save();
      c.translate(0, 2);
      c.globalAlpha = 0.5;
      c.strokeStyle = env.color("--xp-shadow");
      c.lineWidth = 5;
      c.lineJoin = "round";
      c.stroke(groundPath);
      c.restore();
      c.strokeStyle = env.color("--xp-land-edge");
      c.lineWidth = 2;
      c.lineJoin = "round";
      c.stroke(groundPath);
      env.label(c, L.west, 6, 14, { align: "left", size: 12, weight: 500, color: "--muted" });
      env.label(c, L.east, W - 6, 14, { align: "right", size: 12, weight: 500, color: "--muted" });
      if (!small) env.label(c, L.slope, 70, Y(ground(70)) - 9);
      // Along the slab, at its east end, where the interface never reaches within the control range.
      env.label(c, L.salt, 405, Y(saltTop(405) - SALT.thick / 2) + 5, { rotate: saltAngle });
      env.label(c, L.brine, W * 0.3, H - 14); // Below the interface at every level of the control.
    }), 0, 0, W, H);

    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    for (const [i, f] of [0.62, 0.82].entries()) {
      const drift = 4 * Math.sin(env.time * 1.4 + i * 2); // Arrows sway along their flow.
      const x = xs * f + drift;
      if (!flowing) { ctx.save(); ctx.translate(x, (wt(x) + yI(x)) / 2); ctx.strokeStyle = env.color("--xp-fresh-ink"); ctx.stroke(arrowRight); ctx.restore(); }
      const xb = xs * (0.15 + 0.3 * i) - drift;
      ctx.save(); ctx.translate(xb, yI(xb) + 18); ctx.strokeStyle = env.color("--xp-brine-ink"); ctx.stroke(arrowLeft); ctx.restore();
    }
    ctx.lineCap = "butt";
    if (!small) env.label(ctx, L.water_table, Math.max(xs * 0.5, Math.min(xs - 60, 400)), wt(Math.max(xs * 0.5, Math.min(xs - 60, 400))) - 7);
    const ix = Math.max(60, xs * 0.3);
    env.label(ctx, L.interface, ix, yI(ix) + 18);
    const say = ramp(deepest, 0.02, 0.2);
    if (say > 0.01) {
      // West of the salt, between the water table and the interface: the fresh water that flows into the salt.
      // Two short lines (split at the label's middle space), so it fits before the salt starts.
      const words = L.fresh_dissolves.split(" ");
      const half = Math.ceil(words.length / 2);
      const lines = [words.slice(0, half).join(" "), words.slice(half).join(" ")];
      const look = { color: "--xp-fresh-ink", weight: 700, size: small ? 11 : 12 };
      const widest = Math.max(...lines.map((line) => env.textWidth(ctx, line, look)));
      const lx = Math.max(56, widest / 2 + 5 * u), ly = (wt(lx) + yI(lx)) / 2 - 2; // Never past the left edge.
      ctx.globalAlpha = say;
      lines.forEach((line, i) => env.label(ctx, line, lx, ly + i * 14 * u, look));
      ctx.globalAlpha = 1;
    }
    // Just left of the handle (radius 14 CSS pixels), right-aligned with fixed-width digits: it never jitters.
    env.figures(ctx, `${MINUS}${number(Math.round(depth * 2) / 2, 1)}`, W - 34 - 20 * u, yL + 4 * u);

    const date = dateOf(level, spec);
    const year = date ? date.getFullYear() : depth <= min ? 1960 : 1976;
    const series = spec.data.sinkholes.points;
    const [firstYear] = series[0];
    const [lastYear, lastCount] = series[series.length - 1];
    const count = year < firstYear ? ""
      : year > lastYear ? ` ${t.count} ב־${iso(lastYear)}: כ־${iso(number(lastCount))} (${t.count_after}).`
      : ` ${t.count} ב־${iso(year)}: כ־${iso(number(Math.round(interpolate(series, year) / 10) * 10))} (${t.count_source}).`;
    const state = open === 0 ? t.protected : fallen === 0 ? t.exposed : `${t.exposed} ${t.collapse}`;
    return state + count;
  }

  return {
    draw,
    handle: (depth) => [W - 34, Y(-depth)],
    drag: (point) => -elevAt(point.y),
  };
}
return { view: [0, 0, W, H], animated: true, valueParts, create };
})();
