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
// Cavity sites: x and a size factor, so cavities differ. Timing is schematic: a cavity reaches full size
// GROW metres of level drop after fresh water reaches it, and its roof falls COLLAPSE * size metres after that.
const SITES = [[122, 0.8], [158, 1.1], [184, 0.7], [221, 1], [259, 0.9], [296, 1.2], [327, 0.8], [362, 1]];
const GROW = 5, COLLAPSE = 7, FALL = 1.2;

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
  const holes = SITES.map(([x, size]) => {
    const top = Y(saltTop(x)), g = Y(ground(x)), w = 9 * size;
    // A collapse cone: the loose layers fall into the cavity, wide at the surface and narrow at the salt.
    const cone = shape([[-w * 1.5, 4], [-3 * size, top - g + 3], [3 * size, top - g + 3], [w * 1.5, 4]]);
    const pit = new Path2D();
    pit.moveTo(-w * 1.7, Y(ground(x - w * 1.7)) - g);
    pit.quadraticCurveTo(0, 16 * size, w * 1.7, Y(ground(x + w * 1.7)) - g);
    pit.closePath();
    return { x, size, top, g, cone, pit, at: exposureLevel(x, min, max) };
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

    ctx.fillStyle = env.gradient("sky", 0, 0, 0, H, [[0, "--xp-sky-top"], [1, "--xp-sky"]]);
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.clip(below);
    ctx.fillStyle = env.gradient("land", 0, 0, 0, H, [[0, "--xp-land"], [1, "--xp-land-deep"]]);
    ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = 0.16;
    ctx.strokeStyle = env.color("--xp-land-edge");
    ctx.lineWidth = 1;
    ctx.stroke(beds);
    ctx.globalAlpha = 1;
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

    ctx.fillStyle = env.gradient("salt", 0, Y(saltTop(SALT.from)), 0, Y(saltTop(SALT.to) - SALT.thick), [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
    ctx.fill(salt);
    ctx.save();
    ctx.clip(salt);
    ctx.clip(shape([[0, yI0], [xs, yL], [xs, 0], [0, 0]])); // Salt above the interface, in fresh water.
    ctx.globalAlpha = 0.92;
    ctx.fillStyle = env.color("--xp-dissolve");
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
    ctx.strokeStyle = env.color("--xp-salt-edge");
    ctx.lineWidth = 1.2;
    ctx.stroke(salt);

    let open = 0, fallen = 0;
    for (const h of holes) {
      const grown = h.at === null ? -1 : h.at - level;
      const r = ramp(grown, 0, GROW) * h.size;
      if (r > 0.01) {
        ctx.fillStyle = env.color("--xp-void");
        ctx.beginPath();
        ctx.ellipse(h.x, h.top + 7, 10 * r, 7 * r, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      const start = GROW + COLLAPSE * h.size;
      const down = ramp(grown, start, start + FALL);
      if (down > 0.01) {
        ctx.save();
        ctx.translate(h.x, h.g);
        ctx.scale(1, 0.35 + 0.65 * down);
        ctx.globalAlpha = down;
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
      if (r > 0.05) open++;
      if (down > 0.5) fallen++;
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
    ctx.globalAlpha = 1;
    ctx.lineCap = "butt";
    ctx.restore();
    ctx.save();
    ctx.translate(0, 2);
    ctx.globalAlpha = 0.5;
    ctx.strokeStyle = env.color("--xp-shadow");
    ctx.lineWidth = 5;
    ctx.lineJoin = "round";
    ctx.stroke(groundPath);
    ctx.restore();
    ctx.strokeStyle = env.color("--xp-land-edge");
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke(groundPath);

    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    for (const [i, f] of [0.62, 0.82].entries()) {
      const drift = 4 * Math.sin(env.time * 1.4 + i * 2); // Arrows sway along their flow.
      const x = xs * f + drift;
      ctx.save(); ctx.translate(x, (wt(x) + yI(x)) / 2); ctx.strokeStyle = env.color("--xp-fresh-ink"); ctx.stroke(arrowRight); ctx.restore();
      const xb = xs * (0.15 + 0.3 * i) - drift;
      ctx.save(); ctx.translate(xb, yI(xb) + 18); ctx.strokeStyle = env.color("--xp-brine-ink"); ctx.stroke(arrowLeft); ctx.restore();
    }
    ctx.lineCap = "butt";

    const small = u > 1.3; // Phones: fewer labels.
    env.label(ctx, L.west, 6, 14, { align: "left", size: 12, weight: 500, color: "--muted" });
    env.label(ctx, L.east, W - 6, 14, { align: "right", size: 12, weight: 500, color: "--muted" });
    if (!small) env.label(ctx, L.slope, 70, Y(ground(70)) - 9);
    // Along the slab, at its east end, where the interface never reaches within the control range.
    env.label(ctx, L.salt, 405, Y(saltTop(405) - SALT.thick / 2) + 5, { rotate: saltAngle });
    env.label(ctx, L.brine, W * 0.3, H - 14); // Below the interface at every level of the control.
    if (!small) env.label(ctx, L.water_table, xs * 0.5, wt(xs * 0.5) - 7);
    const ix = Math.max(60, xs * 0.3);
    env.label(ctx, L.interface, ix, yI(ix) + 18);
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
