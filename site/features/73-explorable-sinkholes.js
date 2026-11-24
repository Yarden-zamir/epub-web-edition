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
  // Gap sites: where both sides bite fastest, at least GAP_SPACING units apart, at most GAPS; the pieces between them
  // are the salt left over. Near a site the eaten share may
  // reach the full layer; elsewhere at most 0.5 from the top and 0.4 from the bottom.
  const sum = (col) => (col ? col.rt + col.rb : 0);
  const peaks = cols.filter((col, i) => col.atBottom !== null && sum(col) >= sum(cols[i - 1]) && sum(col) >= sum(cols[i + 1]) && sum(col) > 0.7);
  const sites = [];
  for (const col of [...peaks].sort((c1, c2) => sum(c2) - sum(c1))) if (sites.length < GAPS && sites.every((site) => Math.abs(site.x - col.x) >= GAP_SPACING)) sites.push(col);
  for (const site of sites) site.size = 0.6 + rand(); // Sinkholes of different sizes: wider gap, funnel and pit.
  for (const col of cols) {
    const near = Math.max(0, ...sites.map((site) => 1 - Math.abs(site.x - col.x) / (4 + 7 * site.size)));
    col.topMost = 0.12 + 0.38 * col.rt + 0.6 * near;
    col.bottomMost = 0.1 + 0.3 * col.rb + 0.6 * near;
  }
  // The eaten share from the top and from the bottom at a level; their sum of 1 or more means a gap.
  const eatenAt = (col, level) => [bite(col.atTop, level, col.rt, col.topMost), bite(col.atBottom, level, col.rb, col.bottomMost)];
  // Spots: up to SPOTS holes inside the salt that is left, away from the gaps, like the closed loop in the print.
  const spots = [];
  for (const col of cols.filter((c) => c.atBottom !== null && sites.every((site) => Math.abs(site.x - c.x) > 18)).sort((c1, c2) => c2.rt - c1.rt))
    if (spots.length < SPOTS && spots.every((spot) => Math.abs(spot.col.x - col.x) > 30)) spots.push({ col, size: 0.8 + 0.5 * rand(), radii: grid.slice(0, 10).map(() => 0.7 + 0.6 * rand()) });
  // A collapse at each gap site: a funnel straight above the gap, from the sloping surface down through the gap,
  // and a pit at the surface. Its top follows the ground, so nothing sticks out of the slope.
  const holes = sites.sort((c1, c2) => c1.x - c2.x).map((col) => {
    const x = col.x, size = col.size, w = 8 * size;
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
      ctx.clip(below);
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
    // Spots: holes inside the salt that is left, growing as the salt around them dissolves; the flow shows through.
    for (const spot of spots) {
      const [t, b] = eatenAt(spot.col, level);
      // Only inside solid salt: it grows while at least half the layer is left there and fades as the salt thins.
      const grow = ramp(t + b, 0.2, 0.45) * (1 - ramp(t + b, 0.45, 0.55));
      if (grow < 0.05) continue;
      const left = (1 - t - b) * thickPx, cx = spot.col.x, cy = spot.col.top + t * thickPx + left / 2;
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
        ctx.arc(col.x + phase * 16, col.top + t * thickPx * 0.6 - 2 - phase * 4, 1.3, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    let fallen = 0;
    // Each hole runs toward open (its gap is open) or closed. Opening (COLLAPSE_S): cracks, the roof breaks and the pit
    // opens, the funnel tears down to the gap, soil falls into it, dust rises. Closing when the level rises again
    // (REFILL_S): the same in reverse, without soil and dust. Under reduced motion it changes at once.
    const easeOut = (q) => 1 - (1 - q) ** 3;
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
      if (h.p <= 0) continue;
      const p = h.p, closing = target === 0;
      const top = h.surface(0), bottom = h.col.bottom;
      const tear = easeOut(ramp(p, 0.18, 0.8)), sag = easeOut(ramp(p, 0.15, 0.55));
      // Cracks in the surface, before the roof gives way.
      const crack = ramp(p, 0, 0.15) * (1 - ramp(p, 0.45, 0.7));
      if (crack > 0.01) {
        ctx.globalAlpha = crack;
        ctx.strokeStyle = env.color("--xp-void");
        ctx.lineWidth = 1;
        for (const [dx, dy] of [[-6, 7], [-1, 9], [5, 6]]) ctx.stroke(shape([[h.x, top + 1], [h.x + dx * h.size, top + dy * h.size]], false));
        ctx.globalAlpha = 1;
      }
      if (tear > 0.01) { // The funnel, from the surface down as far as it has torn.
        ctx.save();
        ctx.clip(below);
        ctx.beginPath();
        ctx.rect(0, 0, W, top + (bottom - top) * tear);
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
      }
      if (sag > 0.01) { // The pit: both ends on the ground line, its middle as deep as the collapse has gone.
        const left = h.x - h.w * 1.7, right = h.x + h.w * 1.7;
        const yl = h.surface(-h.w * 1.7), yr = h.surface(h.w * 1.7), mid = top + 10 * h.size * sag;
        ctx.fillStyle = env.color("--xp-void");
        ctx.beginPath();
        ctx.moveTo(left, yl);
        ctx.quadraticCurveTo(h.x, 2 * mid - (yl + yr) / 2, right, yr); // The curve's middle lands at `mid`.
        ctx.closePath();
        ctx.fill();
      }
      if (p < 1 && !closing) {
        // Soil falls down the funnel into the gap (accelerating), and dust rises over the pit.
        ctx.fillStyle = env.color("--xp-land-edge");
        for (let k = 0; k < 6; k++) {
          const q = ramp(p, 0.22 + k * 0.06, 0.62 + k * 0.06);
          if (q <= 0 || q >= 1) continue;
          ctx.globalAlpha = 1 - ramp(q, 0.75, 1);
          ctx.beginPath();
          ctx.arc(h.x + (k - 2.5) * 1.8 * (1 - q), top + 3 + (bottom - top - 3) * q * q, 1.2 + (k % 3) * 0.4, 0, Math.PI * 2);
          ctx.fill();
        }
        const puff = ramp(p, 0.2, 0.75);
        if (puff > 0 && puff < 1) {
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
