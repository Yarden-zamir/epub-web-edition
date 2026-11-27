// Road 90 over the sinkhole strip (figure fig-a14-21). Two schematic sections along the road, with one dissolution
// cavity that grows under both: above, the road without the protection layers (asphalt on its base, a14-p052);
// below, the road with the layers of the printed figure. The compacted road is a ceiling that hides the cavity until
// its thin roof fails (a14-p050). Without the layers the road falls in; with them the sheets span the hole and the
// road dips only a little. The control value is the cavity size in percent of the largest drawn cavity: schematic.
explorableKit.kinds.road = (() => {
const { number, ramp, shape } = explorableKit;

const W = 600, PANEL = 196, GAP = 14, H = 2 * PANEL + GAP;
const MID = 300, SURFACE = 46, FLOOR = PANEL - 14; // Cavity centre x; asphalt top and cavity floor in a panel.
// Layers from the asphalt top down, in drawing units: schematic thicknesses, not to scale (the book gives none).
const PLAIN = [["asphalt", 0, 8], ["base", 8, 38]];
const PROTECTED = [["asphalt", 0, 8], ["aggregate", 8, 26], ["gravel", 29, 46], ["sheet-filter", 46, 48.5], ["sheet-load", 48.5, 52]];
const GRID_DEPTH = 27.5; // The geogrid, between the aggregate and the gravel layers.
const ROOF_GONE = 55; // Value at which the cavity top reaches the bottom of the road layers.
const COLLAPSE = [ROOF_GONE, 62]; // Without the layers, the thin roof fails over this part of the control.
const BREAK = 82; // Half width of the road part that falls in.
const PIECES = [[-BREAK, -24, 18, -0.42], [-24, 30, 30, 0.12], [30, BREAK, 16, 0.5]]; // x from, x to, rest height, final turn.
const MAX_SAG = 15; // Sheet sag at the widest span, drawing units (schematic).
const SPREAD = 2.1, MIN_HALF = 10; // Cavity half width: MIN_HALF + SPREAD * value.

const halfWidth = (v) => MIN_HALF + SPREAD * v;
// Cavity top: rises from near the floor to the road bottom at ROOF_GONE, then (virtually) above it.
const topAt = (v, roadBottom) => FLOOR - (FLOOR - roadBottom) * (v / ROOF_GONE);
const profile = (u) => (1 - Math.min(1, u * u)) ** 0.6;
// A fixed wobble, so the cavity edge looks dissolved and not drawn with a compass.
const jag = (x) => Math.sin(x * 0.11) * 1.6 + Math.sin(x * 0.29 + 1) * 0.9;
const cavityY = (x, v, roadBottom) => {
  const hw = halfWidth(v);
  const u = (x - MID) / hw;
  return FLOOR - (FLOOR - topAt(v, roadBottom)) * profile(u) + jag(x) * (1 - u * u);
};
// Half width of the part of the cavity top that reaches the road bottom (0 before ROOF_GONE).
function span(v, roadBottom) {
  const top = topAt(v, roadBottom);
  if (top >= roadBottom) return 0;
  const r = (FLOOR - roadBottom) / (FLOOR - top);
  return halfWidth(v) * Math.sqrt(1 - r ** (1 / 0.6));
}

const STATES = ["none", "growing", "thin", "collapse"];
const stateOf = (v) => STATES[v < 3 ? 0 : v < 45 ? 1 : v < COLLAPSE[1] ? 2 : 3];
const valueParts = (v, spec) => ({ num: number(v), unit: spec.control.unit, note: spec.labels.states[stateOf(v)] });

function create(spec, env) {
  const L = spec.labels, t = spec.texts;
  const xs = [];
  for (let x = 0; x <= W; x += 6) xs.push(x);
  let dots = null, stones = null, patternTheme = "";

  // Small repeating textures, made once per theme: dots for the ground, stones for the aggregate and gravel.
  function patterns(ctx) {
    const theme = env.color("--xp-dot") + env.color("--xp-road-stone");
    if (theme === patternTheme) return;
    const tile = (size, drawTile) => {
      const c = document.createElement("canvas");
      c.width = c.height = size;
      drawTile(c.getContext("2d"));
      return ctx.createPattern(c, "repeat");
    };
    dots = tile(9, (c) => { c.fillStyle = env.color("--xp-dot"); c.beginPath(); c.arc(2, 2, 0.9, 0, Math.PI * 2); c.arc(6.5, 6.5, 0.7, 0, Math.PI * 2); c.fill(); });
    stones = tile(10, (c) => {
      c.strokeStyle = env.color("--xp-road-stone");
      c.lineWidth = 0.8;
      c.beginPath(); c.ellipse(3, 3, 2.2, 1.6, 0.4, 0, Math.PI * 2); c.moveTo(9.6, 7.5); c.ellipse(7.5, 7.5, 2.1, 1.5, -0.5, 0, Math.PI * 2); c.stroke();
    });
    patternTheme = theme;
  }
  const textureOf = (key) => (key === "aggregate" || key === "gravel" || key === "base" ? stones : null);

  // A band between two lines y = top(x) and y = bottom(x), over the whole width.
  function band(ctx, key, top, bottom) {
    const path = shape([...xs.map((x) => [x, top(x)]), ...[...xs].reverse().map((x) => [x, bottom(x)])]);
    ctx.fillStyle = env.color(`--xp-road-${key}`);
    ctx.fill(path);
    const texture = textureOf(key);
    if (texture) { ctx.fillStyle = texture; ctx.fill(path); }
  }

  function sky(ctx) {
    ctx.fillStyle = env.gradient("sky", 0, 0, 0, SURFACE, [[0, "--xp-sky-top"], [1, "--xp-sky"]]);
    ctx.fillRect(0, 0, W, SURFACE + 2);
  }
  function ground(ctx, top) {
    const path = shape([...xs.map((x) => [x, top(x)]), [W, PANEL], [0, PANEL]]);
    ctx.fillStyle = env.color("--xp-land");
    ctx.fill(path);
    ctx.fillStyle = dots;
    ctx.fill(path);
  }
  // The cavity under a top line (the roof or the sheet), with groundwater on its floor.
  function cavity(ctx, v, roadBottom, top) {
    const hw = halfWidth(v);
    if (v <= 0) return null;
    const pts = [];
    for (let x = MID - hw; x <= MID + hw; x += 4) pts.push([x, Math.max(cavityY(x, v, roadBottom), top(x))]);
    pts.push([MID + hw, FLOOR]);
    const path = shape(pts);
    ctx.save();
    ctx.globalAlpha = ramp(v, 0, 4);
    ctx.fillStyle = env.color("--xp-void");
    ctx.fill(path);
    ctx.clip(path);
    ctx.fillStyle = env.color("--xp-lake");
    ctx.fillRect(MID - hw, FLOOR - 6, 2 * hw, 8);
    ctx.restore();
    return path;
  }
  function title(ctx, text) {
    env.label(ctx, text, W - 12, 20, { align: "right", size: 13, weight: 700 });
  }

  function plainPanel(ctx, v) {
    const bottom = SURFACE + PLAIN.at(-1)[2];
    const fall = ramp(v, ...COLLAPSE);
    sky(ctx);
    ground(ctx, () => bottom);
    cavity(ctx, v, bottom, () => bottom); // The road holds the roof up until it fails.
    for (const [key, from, to] of PLAIN) band(ctx, key, () => SURFACE + from, () => SURFACE + to);
    if (fall > 0) {
      // The opening: the road part and its roof are gone; the cavity is open to the sky, between broken road ends.
      const pts = [[MID - BREAK, SURFACE - 1], [MID + BREAK, SURFACE - 1], [MID + BREAK + 3, SURFACE + 12], [MID + BREAK - 2, SURFACE + 26]];
      for (let x = MID + BREAK; x >= MID - BREAK; x -= 4) pts.push([x, Math.max(cavityY(x, v, bottom), bottom) + 3]);
      pts.push([MID - BREAK + 2, SURFACE + 26], [MID - BREAK - 3, SURFACE + 12]);
      ctx.fillStyle = env.gradient("opening", 0, SURFACE, 0, bottom + 24, [[0, "--xp-sky"], [1, "--xp-void"]]);
      ctx.fill(shape(pts));
      // Roof soil heaped on the floor.
      ctx.fillStyle = env.color("--xp-land-deep");
      ctx.fill(shape([[MID - BREAK * 1.2, FLOOR + 1], [MID - 30, FLOOR - 12 * fall], [MID + 40, FLOOR - 10 * fall], [MID + BREAK * 1.2, FLOOR + 1]]));
      // Road pieces fall and turn, and come to rest on the heap.
      for (const [from, to, rest, turn] of PIECES) {
        const cx = MID + (from + to) / 2, cy = SURFACE + PLAIN.at(-1)[2] / 2;
        const drop = (FLOOR - rest - cy) * fall;
        ctx.save();
        ctx.translate(cx, cy + drop);
        ctx.rotate(turn * fall);
        const w = to - from - 3;
        for (const [key, a, b] of PLAIN) {
          ctx.fillStyle = env.color(`--xp-road-${key}`);
          ctx.fillRect(-w / 2, a - PLAIN.at(-1)[2] / 2, w, b - a);
          const texture = textureOf(key);
          if (texture) { ctx.fillStyle = texture; ctx.fillRect(-w / 2, a - PLAIN.at(-1)[2] / 2, w, b - a); }
        }
        ctx.restore();
      }
      ctx.globalAlpha = fall;
      env.label(ctx, L.fell, 12, 20, { align: "left", size: 13, weight: 700, color: "--accent" }); // Opposite the title.
      ctx.globalAlpha = 1;
    }
    title(ctx, L.plain);
  }

  function protectedPanel(ctx, v) {
    const bottom = SURFACE + PROTECTED.at(-1)[2];
    const a = span(v, bottom);
    const sag = MAX_SAG * (a / 200) ** 2;
    // The sheets carry the hole; the layers above follow their dip, a little less toward the surface.
    const dip = (x, depth) => (a > 0 && Math.abs(x - MID) < a ? sag * (1 - ((x - MID) / a) ** 2) * (0.45 + 0.55 * depth / PROTECTED.at(-1)[2]) : 0);
    const at = (depth) => (x) => SURFACE + depth + dip(x, depth);
    sky(ctx);
    ground(ctx, at(PROTECTED.at(-1)[2]));
    cavity(ctx, v, bottom, at(PROTECTED.at(-1)[2]));
    for (const [key, from, to] of PROTECTED) band(ctx, key, at(from), at(to));
    // The geogrid: a strong mesh, drawn as a line with knots.
    const grid = at(GRID_DEPTH);
    ctx.strokeStyle = env.color("--xp-road-grid");
    ctx.lineWidth = 1.6;
    ctx.stroke(shape(xs.map((x) => [x, grid(x)]), false));
    ctx.fillStyle = env.color("--xp-road-grid");
    for (let x = 4; x < W; x += 12) ctx.fillRect(x - 1.2, grid(x) - 2.2, 2.4, 4.4);
    if (a > 0) {
      ctx.globalAlpha = ramp(v, ROOF_GONE, COLLAPSE[1]);
      env.label(ctx, L.spans, 12, 20, { align: "left", size: 13, weight: 700, color: "--accent" });
      ctx.globalAlpha = 1;
    }
    title(ctx, L.protected);
  }

  function draw(ctx, v, env) {
    patterns(ctx);
    plainPanel(ctx, v);
    ctx.save();
    ctx.translate(0, PANEL + GAP);
    protectedPanel(ctx, v);
    ctx.restore();
    ctx.fillStyle = env.color("--paper");
    ctx.fillRect(0, PANEL, W, GAP);
    const state = stateOf(v);
    if (state === "none") return t.start;
    if (state === "growing") return t.growing;
    if (state === "thin") return t.thin;
    return v >= 95 ? `${t.collapse} ${t.case}` : t.collapse;
  }

  return {
    draw,
    handle: (v) => [MID + halfWidth(v), PANEL + GAP + FLOOR - 12],
    drag: (point, start) => start.value + (point.x - start.point.x) / SPREAD,
  };
}
return { view: [0, 0, W, H], valueParts, create };
})();
