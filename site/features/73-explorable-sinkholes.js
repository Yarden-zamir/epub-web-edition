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
// Top 20 to 30 m below the ground (book: 20 to 70 m). The thickness is schematic (the book gives none for this shore):
// up to `thick` metres, tapering to a sliver at both ends, where the thin salt is eaten through first (small sinkholes).
const SALT = { from: 105, to: 470, dip: 0.15, thick: 18 };
const thickAt = (x) => {
  const ease = (q) => q * q * (3 - 2 * q), edge = (v, a, b) => ease(Math.min(1, Math.max(0, (v - a) / (b - a))));
  return SALT.thick * (0.12 + 0.88 * edge(x, SALT.from, SALT.from + 80)) * (0.12 + 0.88 * edge(x, SALT.to, SALT.to - 70));
};
const saltTop = (x) => -386 - SALT.dip * x;
const INTERFACE_DIP = 0.03; // Metres per unit of x, down to the west.
const WATER_TABLE_WEST = -382; // Groundwater table at the west edge.
// Dissolution (schematic, after the printed figure, not a model of the rate): fresh water eats the salt from its top
// once the interface sinks below the top of the layer, and from its bottom once it sinks below the whole layer. Each
// side is eaten deeper with every metre of level drop after that (EAT metres for the full eaten share, scaled by seeded
// noise), up to half of the layer or less, so chunky pieces stay. At a few sites the two fronts meet: there the salt
// is gone, the layer breaks into separate jagged pieces, and above each gap the ground collapses.
const EAT = 9, GRID = 2.5, SEED = 7, GAPS = 4, GAP_SPACING = 34, SPOTS = 2; // Any fixed seed: it fixes the shapes only.
const COLLAPSE_S = 1.1, REFILL_S = 0.6; // Collapse when a gap opens; refill when the level rises again.
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
// Fresh water reaches the salt at x, at the top of the layer (below = 0) or below the whole layer (below = thickAt(x)).
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
  const BEDS = [12, 26, 42, 60, 82, 108, 136]; // Bedding lines: depth below the surface, in drawing units.
  const saltAngle = Math.atan(SALT.dip * SCALE);
  const rand = random(SEED);
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
    x, top: Y(saltTop(x)), bottom: Y(saltTop(x) - thickAt(x)), th: thickAt(x) * SCALE,
    atTop: exposureLevel(x, min, max), atBottom: exposureLevel(x, min, max, thickAt(x)),
    rt: topRate[i], rb: bottomRate[i], jt: topJag[i], jb: bottomJag[i],
  }));
  const bite = (at, level, rate, most) => (at === null ? 0 : Math.max(0, Math.min(most, ((at - level) / EAT) * (0.35 + 1.1 * rate))));
  // The eaten share from the top and from the bottom at a level; their sum of 1 or more means a gap.
  // Gap sites: where both sides bite fastest, at least GAP_SPACING units apart, at most GAPS; the pieces between them
  // are the salt left over. Near a site the eaten share may
  // reach the full layer; elsewhere at most 0.5 from the top and 0.4 from the bottom.
  const sum = (col) => (col ? col.rt + col.rb : 0);
  const peaks = cols.filter((col, i) => col.atBottom !== null && sum(col) >= sum(cols[i - 1]) && sum(col) >= sum(cols[i + 1]) && sum(col) > 0.7);
  const sites = [];
  for (const col of [...peaks].sort((c1, c2) => sum(c2) - sum(c1))) if (sites.length < GAPS && sites.every((site) => Math.abs(site.x - col.x) >= GAP_SPACING)) sites.push(col);
  for (const site of sites) site.size = 0.8 + rand(); // Gaps of different widths (the gap radius below scales with it).
  for (const col of cols) {
    const near = Math.max(0, ...sites.map((site) => 1 - Math.abs(site.x - col.x) / (6 + 9 * site.size)));
    col.topMost = 0.12 + 0.38 * col.rt + 0.6 * near;
    col.bottomMost = 0.1 + 0.3 * col.rb + 0.6 * near;
  }
  // The eaten share from the top and from the bottom at a level; their sum of 1 or more means a gap.
  // Shares of the local thickness. Fresh water eats metres of salt, so where the layer is thin it is eaten through sooner.
  const share = (col, eaten) => (eaten * SALT.thick * SCALE) / col.th;
  const eatenAt = (col, level) => [share(col, bite(col.atTop, level, col.rt, col.topMost)), share(col, bite(col.atBottom, level, col.rb, col.bottomMost))];
  // Spots: up to SPOTS holes inside the salt that is left, away from the gaps, like the closed loop in the print.
  const spots = [];
  for (const col of cols.filter((c) => c.atBottom !== null && sites.every((site) => Math.abs(site.x - c.x) > 18)).sort((c1, c2) => c2.rt - c1.rt))
    if (spots.length < SPOTS && spots.every((spot) => Math.abs(spot.col.x - col.x) > 30)) spots.push({ col, size: 0.8 + 0.5 * rand(), radii: grid.slice(0, 10).map(() => 0.7 + 0.6 * rand()) });
  // A collapse at each gap site: the ground above the gap moves down into the space the salt left. Its size follows
  // the salt cleared there, the gap width times the local thickness: small over the thin ends, big where the layer is
  // thick. Width and depth each take the square root, so the crater's cross-section follows the cleared area. The
  // widest gap in the thickest salt gives size 1.8. Half width at the surface: w; it narrows toward the gap.
  const holes = sites.sort((c1, c2) => c1.x - c2.x).map((col) => {
    const size = Math.sqrt(col.size * (thickAt(col.x) / SALT.thick) * 1.8);
    return { x: col.x, col, size, w: 16 * size, surface: (dx) => Y(ground(col.x + dx)) };
  });
  let pores = null, poresColor = "";
  const poreTile = (ctx, env) => { // Small dots: water in the pores of the ground. One tile per theme.
    const color = env.color("--xp-fresh-ink");
    if (color !== poresColor) {
      const tile = document.createElement("canvas");
      tile.width = tile.height = 7;
      const tc = tile.getContext("2d");
      tc.fillStyle = color;
      tc.globalAlpha = 0.35;
      tc.beginPath(); tc.arc(1.5, 1.5, 0.7, 0, Math.PI * 2); tc.arc(5, 4.5, 0.6, 0, Math.PI * 2); tc.fill();
      pores = ctx.createPattern(tile, "repeat");
      poresColor = color;
    }
    return pores;
  };
  const arrowRight = new Path2D("M-12 0 H9 M3 -5 L10 0 L3 5");
  const arrowLeft = new Path2D("M12 0 H-9 M-3 -5 L-10 0 L-3 5");
  const arrowDown = new Path2D("M0 -12 V9 M-5 3 L0 10 L5 3");

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
    const easeOut = (q) => 1 - (1 - q) ** 3;
    const flowing = !reduceMotion.matches;

    // Collapse state first: each hole runs toward open (its gap is open) or closed (COLLAPSE_S to open, REFILL_S to
    // refill; at once under reduced motion). From it: how far its crater has sunk at the surface.
    let fallen = 0;
    for (const h of holes) {
      const [t, b] = eatenAt(h.col, level);
      const target = t + b >= 1 ? 1 : 0;
      const dt = h.last === undefined ? 0 : Math.min(0.1, Math.max(0, env.time - h.last));
      h.last = env.time;
      h.p ??= 0;
      if (reduceMotion.matches) h.p = target;
      else if (h.p < target) h.p = Math.min(target, h.p + dt / COLLAPSE_S);
      else if (h.p > target) h.p = Math.max(target, h.p - dt / REFILL_S);
      if (h.p !== target) env.wantsFrame = true;
      if (target) fallen++;
      h.closing = target === 0;
      h.crater = 20 * h.size * easeOut(ramp(h.p, 0.1, 0.55));
    }
    const active = holes.filter((h) => h.p > 0);
    // The salt that is gone at each point (drawing units), smoothed sideways: the ground above settles into it, fully
    // at the salt and less toward the surface. It grows with every metre of level drop, so the ground subsides
    // gradually before a sinkhole opens; over a gap the drop is deepest.
    let removed = cols.map((col) => { const [t, b] = eatenAt(col, level); return Math.min(1, t + b) * col.th; });
    for (let k = 0; k < 4; k++) removed = removed.map((v, i) => (removed[Math.max(0, i - 2)] + removed[Math.max(0, i - 1)] + v + removed[Math.min(removed.length - 1, i + 1)] + removed[Math.min(removed.length - 1, i + 2)]) / 5);
    const settled = removed.some((v) => v > 0.2);
    const removedAt = (x) => { // Linear between the grid points; a direct index, as it runs for every point drawn.
      const at = (x - cols[0].x) / GRID, i = Math.floor(at);
      if (i < 0 || i >= cols.length - 1) return 0;
      return removed[i] + (removed[i + 1] - removed[i]) * (at - i);
    };
    // How far the ground at x moves down, at depth fraction f between the surface (0) and the top of the salt (1):
    // the removed salt below it, and over an open gap the crater, in a bell that narrows with depth.
    const sagAt = (x, f) => {
      let amount = removedAt(x) * (0.3 + 0.7 * f);
      for (const h of active) {
        const half = h.w * (1 - 0.45 * f) + 4, q = (x - h.x) / half;
        if (Math.abs(q) < 1) amount += h.crater * (1 - f) * (1 + Math.cos(Math.PI * q)) / 2;
      }
      return amount;
    };
    const STEP = 3;
    const surfacePts = [];
    const moving = active.length || settled;
    for (let x = 0; x <= W; x += STEP) surfacePts.push([x, Y(ground(x)) + (moving ? sagAt(x, 0) : 0)]);
    const belowNow = moving ? shape([...surfacePts, [W, H + 40], [0, H + 40]]) : below;

    ctx.drawImage(env.layer("back", [0, 0, W, H], (c) => {
      c.fillStyle = env.gradient("sky", 0, 0, 0, H, [[0, "--xp-sky-top"], [1, "--xp-sky"]]);
      c.fillRect(0, 0, W, H);
      c.clip(below);
      c.fillStyle = env.gradient("land", 0, 0, 0, H, [[0, "--xp-land"], [1, "--xp-land-deep"]]);
      c.fillRect(0, 0, W, H);
    }), 0, 0, W, H);
    // Water in the ground: a tint and pore dots over the sediment. Fresh groundwater between the water table and the
    // interface, saturated Dead Sea water below the interface. The ground stays ground; only the lake is open water.
    // Each kind of wet ground is a fixed bitmap; a frame copies it through its zone, a simple polygon (cheap to clip;
    // a pattern fill through the sagging surface cost most of a frame on phones).
    const wet = (key, token, alpha) => env.layer(key, [0, 0, W, H], (c) => {
      c.clip(below);
      c.fillStyle = env.gradient("land", 0, 0, 0, H, [[0, "--xp-land"], [1, "--xp-land-deep"]]);
      c.fillRect(0, 0, W, H);
      c.globalAlpha = alpha;
      c.fillStyle = env.color(token);
      c.fillRect(0, 0, W, H);
      c.globalAlpha = 1;
      c.fillStyle = poreTile(c, env);
      c.fillRect(0, 0, W, H);
    });
    const freshZone = shape([[0, wt0], [xs, yL], [0, yI0]]);
    const brineZone = shape([[0, yI0], [W, yI(W)], [W, H], [0, H]]);
    for (const [zone, layer] of [[freshZone, wet("fresh-ground", "--xp-fresh", 0.62)], [brineZone, wet("brine-ground", "--xp-brine", 0.72)]]) {
      ctx.save();
      ctx.clip(zone);
      ctx.drawImage(layer, 0, 0, W, H);
      ctx.restore();
    }
    // The sunken surface: sky in the strip between the old surface and the new one, over the salt only.
    const sunk = surfacePts.filter(([x]) => x >= SALT.from - 40 && x <= SALT.to + 40);
    if (moving && sunk.length) {
      ctx.fillStyle = env.gradient("sky", 0, 0, 0, H, [[0, "--xp-sky-top"], [1, "--xp-sky"]]);
      ctx.fill(shape([...sunk, ...sunk.map(([x]) => [x, Y(ground(x)) - 1]).reverse()]));
    }
    ctx.save();
    ctx.clip(belowNow);
    // Bedding lines of the ground; over a collapse they bend down into the space the salt left.
    ctx.strokeStyle = env.color("--xp-land-edge");
    ctx.globalAlpha = 0.3;
    ctx.lineWidth = 1;
    for (const d of BEDS) {
      ctx.beginPath();
      for (let x = 0; x <= W; x += STEP) {
        const g = Y(ground(x)), span = Y(saltTop(x)) - g, f = d / span;
        const y = g + d + (moving && f > 0 && f <= 1.05 && x >= SALT.from - 20 && x <= SALT.to ? sagAt(x, Math.min(1, f)) : 0);
        x ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    // Disturbed ground over each collapse: a soft darker column from the sunken surface down into the gap.
    for (const h of active) {
      const left = [], right = [];
      for (let k = 0; k <= 8; k++) {
        const f = k / 8, g = h.surface(0), y = g + f * (h.col.top - g) + sagAt(h.x, f);
        const half = (h.w * (1 - 0.45 * f) + 4) * 0.55;
        left.push([h.x - half, y]);
        right.unshift([h.x + half, y]);
      }
      ctx.globalAlpha = 0.18 * easeOut(ramp(h.p, 0.15, 0.85));
      ctx.fillStyle = env.color("--xp-land-edge");
      ctx.fill(shape([...left, ...right]));
    }
    ctx.globalAlpha = 1;
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
    const streaks = () => {
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
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    };
    if (flowing) {
      ctx.save();
      ctx.clip(belowNow);
      streaks();
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
      run.push([col.x, col.top + t * col.th + col.jt * wobble(t), col.bottom - b * col.th + col.jb * wobble(b)]);
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
    // Spots: holes inside the salt that is left, growing as the salt around them dissolves; the flow shows through.
    for (const spot of spots) {
      const [t, b] = eatenAt(spot.col, level);
      // Only inside solid salt: it grows while at least half the layer is left there and fades as the salt thins.
      const grow = ramp(t + b, 0.2, 0.45) * (1 - ramp(t + b, 0.45, 0.55));
      if (grow < 0.05) continue;
      const left = (1 - t - b) * spot.col.th, cx = spot.col.x, cy = spot.col.top + t * spot.col.th + left / 2;
      const rx = 7 * spot.size * grow, ry = Math.min(left * 0.3, 4 * spot.size) * grow;
      const ring = spot.radii.map((r, i) => {
        const a = (i / spot.radii.length) * Math.PI * 2;
        return [cx + Math.cos(a) * rx * r, cy + Math.sin(a) * ry * r];
      });
      const blob = new Path2D(); // A smooth closed outline through the midpoints of the ring.
      const mid = (k) => [(ring[k % ring.length][0] + ring[(k + 1) % ring.length][0]) / 2, (ring[k % ring.length][1] + ring[(k + 1) % ring.length][1]) / 2];
      blob.moveTo(...mid(0));
      for (let k = 1; k <= ring.length; k++) blob.quadraticCurveTo(...ring[k % ring.length], ...mid(k));
      blob.closePath();
      ctx.save();
      ctx.clip(pieces); // A spot is a hole in the salt, never a shape of its own.
      ctx.globalAlpha = Math.min(1, grow * 1.5);
      ctx.fillStyle = env.color("--xp-fresh");
      ctx.fill(blob);
      ctx.strokeStyle = env.color("--xp-salt-edge");
      ctx.lineWidth = 1.2;
      ctx.stroke(blob);
      ctx.globalAlpha = 1;
      if (flowing) {
        ctx.clip(blob);
        streaks();
      }
      ctx.restore();
    }
    if (flowing && deepest > 0.2) { // Grains of salt leave the eaten edges with the flow and fade.
      ctx.fillStyle = env.color("--xp-salt");
      cols.forEach((col, i) => {
        const [t] = eatenAt(col, level);
        if (i % 11 || t < 0.25) return;
        const phase = (env.time * 0.3 + i * 0.137) % 1;
        ctx.globalAlpha = (1 - phase) * 0.85;
        ctx.beginPath();
        ctx.arc(col.x + phase * 16, col.top + t * col.th * 0.6 - 2 - phase * 4, 1.3, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    // While the ground falls in: a down arrow that sinks with it (not on refill), and dust over the new crater.
    for (const h of active) {
      const top = h.surface(0), p = h.p;
      const fall = h.closing ? 0 : ramp(p, 0, 0.15) * (1 - ramp(p, 0.7, 1));
      if (fall > 0.01) {
        ctx.save();
        ctx.globalAlpha = fall;
        ctx.translate(h.x, top + h.crater * 0.55 - 4);
        ctx.strokeStyle = env.color("--ink");
        ctx.lineWidth = 1.6;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.stroke(arrowDown);
        ctx.restore();
      }
      const puff = ramp(p, 0.2, 0.75);
      if (!h.closing && puff > 0 && puff < 1) {
        ctx.fillStyle = env.color("--xp-land");
        ctx.globalAlpha = 0.45 * (1 - puff);
        for (const [dx, r] of [[-5, 1], [0, 1.3], [5, 0.9]]) {
          ctx.beginPath();
          ctx.arc(h.x + dx * h.size * (0.6 + puff), top - 3 - 7 * puff, (2 + 6 * puff) * r, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    }
    const open = deepest > 0.05 ? 1 : 0;
    // Once a second sinkhole opens: a short explanation above the largest open crater, with a pointer down to it.
    const opened = holes.reduce((total, h) => total + h.p, 0);
    const explain = ramp(opened, 1.3, 1.9);
    if (explain > 0.01) {
      const h = holes.filter((hole) => !hole.closing && hole.p > 0).sort((h1, h2) => h2.size - h1.size)[0];
      if (h) {
        const look = { weight: 700, size: small ? 11 : 12 };
        const [first, second] = L.sinkhole.split(" / ");
        const g = h.surface(0), y = Math.max(g - 34 * Math.max(1, u * 0.8), 30 * u); // Both lines stay inside the drawing.
        ctx.globalAlpha = explain;
        ctx.strokeStyle = env.color("--ink");
        ctx.lineWidth = 1;
        ctx.stroke(shape([[h.x, y + 6 * u], [h.x, g + h.crater * 0.4]], false));
        env.label(ctx, first, h.x, y - 14 * u, look);
        env.label(ctx, second, h.x, y, look);
        ctx.globalAlpha = 1;
      }
    }

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
    // The ground surface, with its craters.
    const surfaceLine = moving ? shape(surfacePts, false) : groundPath;
    ctx.save();
    ctx.translate(0, 2);
    ctx.globalAlpha = 0.5;
    ctx.strokeStyle = env.color("--xp-shadow");
    ctx.lineWidth = 5;
    ctx.lineJoin = "round";
    ctx.stroke(surfaceLine);
    ctx.restore();
    ctx.strokeStyle = env.color("--xp-land-edge");
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke(surfaceLine);
    ctx.drawImage(env.layer("top", [0, 0, W, H], (c) => {
      env.label(c, L.west, 6, 4 + 11 * u, { align: "left", size: 12, weight: 500, color: "--muted" });
      env.label(c, L.east, W - 6, 4 + 11 * u, { align: "right", size: 12, weight: 500, color: "--muted" });
      if (!small) env.label(c, L.slope, 70, Y(ground(70)) - 9);
      // Along the slab, at its east end, where the interface never reaches within the control range.
      env.label(c, L.salt, 395, Y(saltTop(395) - thickAt(395) / 2) + 5, { rotate: saltAngle });
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
