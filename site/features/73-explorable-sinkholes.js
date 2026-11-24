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
const SALT = { from: 105, to: 470, dip: 0.15, thick: 10 }; // Top 20 to 30 m below the ground (book: 20 to 70 m).
const saltTop = (x) => -386 - SALT.dip * x;
const INTERFACE_DIP = 0.03; // Metres per unit of x, down to the west.
const WATER_TABLE_WEST = -382; // Groundwater table at the west edge.
// Dissolution (schematic, like the printed figure, not a model of the rate): along the salt layer, how deep fresh water
// has eaten (0 to 1, above 1 is through the layer) grows with the metres of level drop since fresh water reached
// that point, EAT metres for the full depth, up to a seeded limit per point: the layer stays riddled, not removed,
// and only some points are eaten through. Seeded low-frequency noise gives the front a few broad lobes.
const EAT = 10, GRID = 3, SEED = 7; // Any fixed seed: it only fixes the shape of the front.
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
const exposed = (x, level) => interfaceAt(x, level, shoreline(level)) < saltTop(x);

// The level at which fresh water first reaches the salt at x, or null if it never does in range.
function exposureLevel(x, min, max) {
  if (!exposed(x, -max)) return null;
  let lo = -min, hi = -max; // lo: not exposed (higher level), hi: exposed.
  if (exposed(x, lo)) return lo;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (exposed(x, mid)) hi = mid; else lo = mid;
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
  const salt = shape([
    [SALT.from, Y(saltTop(SALT.from))], [SALT.to, Y(saltTop(SALT.to))],
    [SALT.to - 10, Y(saltTop(SALT.to) - SALT.thick)], [SALT.from + 6, Y(saltTop(SALT.from) - SALT.thick)],
  ]);
  const saltAngle = Math.atan(SALT.dip * SCALE);
  const rand = random(SEED);
  const thickPx = SALT.thick * SCALE;
  const smooth = (values, passes) => {
    let v = values;
    for (let k = 0; k < passes; k++) v = v.map((x, i) => (v[Math.max(0, i - 1)] + 2 * x + v[Math.min(v.length - 1, i + 1)]) / 4);
    return v;
  };
  const grid = [];
  for (let x = SALT.from + 2; x <= SALT.to - 8; x += GRID) grid.push(x);
  // Low-frequency noise, so the front is a few broad lobes, not spikes: how deep each point can be eaten (its limit,
  // scaled to 0..1) and a small wobble of the edge.
  const depth = smooth(grid.map(() => rand()), 8);
  const wobble = smooth(grid.map(() => rand() * 2 - 1), 3);
  const lo = Math.min(...depth), hi = Math.max(...depth);
  const cols = grid.map((x, i) => ({ x, at: exposureLevel(x, min, max), n: (depth[i] - lo) / (hi - lo), w: wobble[i] }));
  // Sinkhole sites: the broad peaks of the noise, at least 34 units apart, at most 6, west to east. Only there is the
  // salt eaten through (a dip in the front); elsewhere at most 85% of the layer, so the salt that is left stays visible.
  const peaks = cols.filter((col, i) => col.n >= (cols[i - 1]?.n ?? 0) && col.n >= (cols[i + 1]?.n ?? 0) && col.n > 0.35);
  const sites = [];
  for (const col of [...peaks].sort((p1, p2) => p2.n - p1.n)) if (sites.length < 6 && sites.every((site) => Math.abs(site.x - col.x) >= 34)) sites.push(col);
  sites.sort((p1, p2) => p1.x - p2.x);
  for (const col of cols) {
    const near = Math.max(0, ...sites.map((site) => 1 - Math.abs(site.x - col.x) / 9));
    col.limit = Math.max(0.25 + 0.6 * col.n, near * 1.05);
  }
  const eaten = (col, level) => (col.at === null ? 0 : Math.max(0, Math.min(col.limit, ((col.at - level) / EAT) * (0.6 + 0.6 * col.n))));
  const holes = sites.map((col) => {
    const x = col.x, size = 0.85 + 0.3 * col.n, top = Y(saltTop(x)), g = Y(ground(x)), w = 8 * size;
    // A collapse cone straight above the deepest point: wide at the surface, narrow where it enters the pocket.
    const bottom = top + thickPx * 0.5 - g;
    const cone = shape([[-w * 1.5, 4], [-2.5 * size, bottom], [2.5 * size, bottom], [w * 1.5, 4]]);
    const pit = new Path2D();
    pit.moveTo(-w * 1.7, Y(ground(x - w * 1.7)) - g);
    pit.quadraticCurveTo(0, 16 * size, w * 1.7, Y(ground(x + w * 1.7)) - g);
    pit.closePath();
    return { x, col, g, cone, pit };
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

    // Fresh groundwater flows east under and through the exposed salt; under reduced motion, still arrows (below).
    const flowing = !reduceMotion.matches;
    const streaks = (alpha) => {
      ctx.strokeStyle = env.color("--xp-fresh-ink");
      ctx.globalAlpha = alpha;
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
      streaks(0.6);
      ctx.restore();
    }

    ctx.drawImage(env.layer("salt", [0, 0, W, H], (c) => {
      c.fillStyle = env.gradient("salt", 0, Y(saltTop(SALT.from)), 0, Y(saltTop(SALT.to) - SALT.thick), [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
      c.fill(salt);
      c.strokeStyle = env.color("--xp-salt-edge");
      c.lineWidth = 1.2;
      c.stroke(salt);
    }), 0, 0, W, H);

    // Eaten salt: a front from the top of the layer down, as deep as the fresh water has eaten at each point, filled
    // with fresh water. Its top edge sits just above the salt, in fresh water, so it also hides the salt's old top line.
    let deepest = 0, frontEnd = SALT.from;
    const hole = new Path2D();
    let run = [];
    const closeRun = () => {
      if (run.length > 1) {
        hole.moveTo(run[0][0], run[0][1] - 2);
        hole.lineTo(run.at(-1)[0], run.at(-1)[1] - 2);
        const back = [...run].reverse();
        hole.lineTo(back[0][0], back[0][2]);
        for (let i = 1; i < back.length; i++) { // A smooth bottom edge through the midpoints.
          const [x0, , y0] = back[i - 1], [x1, , y1] = back[i];
          hole.quadraticCurveTo(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2);
        }
        hole.lineTo(back.at(-1)[0], back.at(-1)[2]);
        hole.closePath();
      }
      run = [];
    };
    for (const col of cols) {
      const e = eaten(col, level);
      if (e > 0.02) {
        const top = Y(saltTop(col.x));
        run.push([col.x, top, top + Math.min(e, 1) * thickPx + col.w * 1.5 * Math.min(1, e * 4)]);
        deepest = Math.max(deepest, e);
        frontEnd = col.x;
      } else closeRun();
    }
    closeRun();
    if (deepest > 0.02) {
      ctx.fillStyle = env.color("--xp-fresh");
      ctx.fill(hole);
      ctx.save();
      ctx.clip(salt);
      ctx.strokeStyle = env.color("--xp-salt-edge");
      ctx.lineWidth = 1.2;
      ctx.lineJoin = "round";
      ctx.stroke(hole); // Only the edge inside the salt shows: the outline of the salt that is left.
      if (flowing) {
        ctx.clip(hole);
        streaks(0.6); // The flow continues through the pockets.
        if (deepest > 0.2) { // Grains of salt leave the pockets with the flow and fade.
          ctx.fillStyle = env.color("--xp-salt");
          cols.forEach((col, i) => {
            const e = eaten(col, level);
            if (i % 9 || e < 0.3) return;
            const phase = (env.time * 0.3 + i * 0.137) % 1;
            ctx.globalAlpha = (1 - phase) * 0.9;
            ctx.beginPath();
            ctx.arc(col.x + phase * 18, Y(saltTop(col.x)) + e * thickPx * 0.45 - phase * 3, 1.3, 0, Math.PI * 2);
            ctx.fill();
          });
          ctx.globalAlpha = 1;
        }
      }
      ctx.restore();
    }

    let fallen = 0;
    for (const h of holes) {
      const down = ramp(eaten(h.col, level), 0.92, 1.02);
      if (down > 0.01) {
        ctx.save();
        ctx.translate(h.x, h.g);
        ctx.scale(1, 0.35 + 0.65 * down);
        ctx.fillStyle = env.color("--xp-land-edge");
        ctx.globalAlpha = down * 0.32;
        ctx.fill(h.cone);
        ctx.globalAlpha = down;
        ctx.strokeStyle = env.color("--xp-land-edge");
        ctx.lineWidth = 0.8;
        ctx.setLineDash([2, 2]);
        ctx.stroke(h.cone);
        ctx.setLineDash([]);
        ctx.fillStyle = env.color("--xp-void");
        ctx.fill(h.pit);
        ctx.restore();
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
