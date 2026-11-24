// Sinkholes as the Dead Sea drops (figure fig-a14-07). A schematic west-east section of the shore:
// the lake level sets the shoreline, and the interface between fresh groundwater (above) and saturated
// Dead Sea brine (below) runs from the shoreline down to the west. Where the interface sinks below the
// salt layer, fresh groundwater dissolves the salt; cavities grow and their roofs collapse.
// The control value is the lake level in metres below sea level.
explorableKit.kinds.sinkholes = (() => {
const { svgEl, svgText, interpolate, number } = explorableKit;

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
const GROW = 5, COLLAPSE = 7;

const Y = (elev) => 14 + (-362 - elev) * 2.7;
const elevAt = (y) => -362 - (y - 14) / 2.7;
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

const path = (points) => "M" + points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L") + " Z";
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

function valueText(depth, spec) {
  const mark = spec.marks.find((m) => m.value === depth);
  const date = dateOf(-depth, spec);
  const firstMeasured = -spec.data.level.points[0][1];
  const when = mark ? mark.year
    : date && depth >= firstMeasured ? date.toLocaleDateString("he-IL", { month: "long", year: "numeric" })
    : "בין 1960 ל־1976";
  return `${number(depth, depth % 1 ? 1 : 0)} ${spec.control.unit} (${when})`;
}

function mount(svg, spec, api) {
  const L = spec.labels;
  const t = spec.texts;
  const { min, max } = spec.control;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

  svgEl("path", { class: "sk-land", d: path([...groundLine(0, W), [W, H], [0, H]]) }, svg);
  const brine = svgEl("path", { class: "sk-brine" }, svg);
  const fresh = svgEl("path", { class: "sk-fresh" }, svg);
  const lake = svgEl("path", { class: "sk-lake" }, svg);
  const saltShape = path([
    [SALT.from, Y(saltTop(SALT.from))], [SALT.to, Y(saltTop(SALT.to))],
    [SALT.to - 10, Y(saltTop(SALT.to) - SALT.thick)], [SALT.from + 6, Y(saltTop(SALT.from) - SALT.thick)],
  ]);
  svgEl("path", { class: "sk-salt", d: saltShape }, svg);
  const clip = svgEl("clipPath", { id: `${svg.closest("figure").id}-fresh` }, svgEl("defs", {}, svg));
  const clipShape = svgEl("path", {}, clip);
  svgEl("path", { class: "sk-dissolving", d: saltShape, "clip-path": `url(#${clip.id})` }, svg);
  const holes = SITES.map(([x, size]) => {
    const top = Y(saltTop(x));
    return {
      x, size, top,
      at: exposureLevel(x, min, max),
      cavity: svgEl("ellipse", { class: "sk-void", cx: x, cy: top + 7 }, svg),
      rubble: svgEl("path", { class: "sk-rubble" }, svg),
      pit: svgEl("path", { class: "sk-void" }, svg),
    };
  });
  svgEl("polyline", { class: "sk-ground", points: groundLine(0, W).map((p) => p.join(",")).join(" ") }, svg);
  const table = svgEl("line", { class: "sk-table" }, svg);
  const iface = svgEl("line", { class: "sk-interface" }, svg);
  const surface = svgEl("line", { class: "sk-surface", x2: W }, svg);
  // Each arrow is a group placed by its transform attribute; CSS moves only the inner path (flow).
  const arrow = (kind, d) => { const g = svgEl("g", { class: `sk-arrow ${kind}` }, svg); svgEl("path", { d }, g); return g; };
  const freshArrows = [0, 1].map(() => arrow("fresh", "M-12 0 H9 M3 -5 L10 0 L3 5"));
  const brineArrows = [0, 1].map(() => arrow("brine", "M12 0 H-9 M-3 -5 L-10 0 L-3 5"));

  const label = (text, attrs, minor = false) =>
    svgText(text, { class: minor ? "xp-label xp-minor" : "xp-label", "text-anchor": "middle", ...attrs }, svg);
  label(L.west, { x: 6, y: 13, "text-anchor": "end", class: "xp-label xp-compass" });
  label(L.east, { x: W - 6, y: 13, "text-anchor": "start", class: "xp-label xp-compass" });
  label(L.slope, { x: 70, y: Y(ground(70)) - 9 }, true);
  // Along the slab, at its east end, where the interface never reaches within the control range.
  const saltX = 405, saltY = Y(saltTop(405) - SALT.thick / 2) + 5;
  label(L.salt, { x: saltX, y: saltY, transform: `rotate(${(Math.atan(SALT.dip * 2.7) * 180) / Math.PI} ${saltX} ${saltY})` });
  label(L.brine, { x: W * 0.3, y: H - 14 }); // Below the interface at every level of the control.
  const tableLabel = label(L.water_table, {}, true);
  const ifaceLabel = label(L.interface, {});
  // In right-to-left text "start" is the right edge: the number ends just left of the grip.
  const levelLabel = label("", { "text-anchor": "start" });

  // Drag the lake surface itself. The hit area is wide, so a finger finds it.
  const handle = svgEl("g", { class: "sk-grip" }, svg);
  svgEl("rect", { x: -130, y: -24, width: 160, height: 48, fill: "transparent" }, handle);
  svgEl("circle", { r: 12 }, handle);
  svgEl("path", { d: "M0 -7 L-4 -3 M0 -7 L4 -3 M0 -7 V7 M0 7 L-4 3 M0 7 L4 3" }, handle);
  api.drag(handle, (point) => api.setValue(Math.min(max, Math.max(min, -elevAt(point.y)))));

  return (depth) => {
    const level = -depth;
    const xs = shoreline(level);
    const yL = Y(level);
    const yI = (x) => Y(interfaceAt(x, level, xs));
    const wt = (x) => Y(WATER_TABLE_WEST + ((level - WATER_TABLE_WEST) * x) / xs);
    lake.setAttribute("d", path([[xs, yL], [W, yL], ...groundLine(xs, W).reverse()]));
    brine.setAttribute("d", path([[0, yI(0)], [xs, yL], ...groundLine(xs, W).slice(1), [W, H], [0, H]]));
    fresh.setAttribute("d", path([[0, wt(0)], [xs, yL], [0, yI(0)]]));
    clipShape.setAttribute("d", path([[0, 0], [xs, 0], [xs, yL], [0, yI(0)]]));
    for (const [line, y0] of [[table, wt(0)], [iface, yI(0)]]) {
      line.setAttribute("x1", 0); line.setAttribute("y1", y0); line.setAttribute("x2", xs); line.setAttribute("y2", yL);
    }
    surface.setAttribute("x1", xs); surface.setAttribute("y1", yL); surface.setAttribute("y2", yL);
    handle.setAttribute("transform", `translate(${W - 34} ${yL})`);
    tableLabel.setAttribute("x", xs * 0.5); tableLabel.setAttribute("y", wt(xs * 0.5) - 7);
    ifaceLabel.setAttribute("x", Math.max(60, xs * 0.3)); ifaceLabel.setAttribute("y", yI(Math.max(60, xs * 0.3)) + 18);
    levelLabel.setAttribute("x", W - 52); levelLabel.setAttribute("y", yL - 9);
    levelLabel.textContent = number(level, depth % 1 ? 1 : 0);
    freshArrows.forEach((a, i) => {
      const x = xs * (0.62 + 0.2 * i);
      a.setAttribute("transform", `translate(${x} ${(wt(x) + yI(x)) / 2})`);
    });
    brineArrows.forEach((a, i) => {
      const x = xs * (0.15 + 0.3 * i);
      a.setAttribute("transform", `translate(${x} ${yI(x) + 18})`);
    });

    let open = 0, fallen = 0;
    for (const h of holes) {
      const grown = h.at === null ? -1 : h.at - level;
      const r = Math.max(0, Math.min(1, grown / GROW)) * h.size;
      h.cavity.setAttribute("rx", (10 * r).toFixed(1));
      h.cavity.setAttribute("ry", (7 * r).toFixed(1));
      h.cavity.toggleAttribute("hidden", r === 0);
      const down = grown >= GROW + COLLAPSE * h.size;
      if (down) {
        // The loose layers above fall into the cavity; a pit opens at the surface.
        const g = Y(ground(h.x)), w = 9 * h.size;
        h.rubble.setAttribute("d", path([[h.x - w, g + 6], [h.x - 6 * h.size, h.top + 4], [h.x + 6 * h.size, h.top + 4], [h.x + w, g + 6]]));
        h.pit.setAttribute("d", path([[h.x - w - 4, Y(ground(h.x - w - 4))], [h.x - w * 0.6, g + 12], [h.x + w * 0.6, g + 12], [h.x + w + 4, Y(ground(h.x + w + 4))]]));
      }
      h.rubble.toggleAttribute("hidden", !down);
      h.pit.toggleAttribute("hidden", !down);
      if (r > 0) open++;
      if (down) fallen++;
    }

    const date = dateOf(level, spec);
    const year = date ? date.getFullYear() : depth === min ? 1960 : 1976;
    const series = spec.data.sinkholes.points;
    const [firstYear] = series[0];
    const [lastYear, lastCount] = series[series.length - 1];
    const count = year < firstYear ? ""
      : year > lastYear ? ` ${t.count} ב־${lastYear}: כ־${number(lastCount)} (${t.count_after}).`
      : ` ${t.count} ב־${year}: כ־${number(Math.round(interpolate(series, year) / 10) * 10)} (${t.count_source}).`;
    const state = open === 0 ? t.protected : fallen === 0 ? t.exposed : `${t.exposed} ${t.collapse}`;
    return state + count;
  };
}
return { valueText, mount };
})();
