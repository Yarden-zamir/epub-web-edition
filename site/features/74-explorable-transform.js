// The Dead Sea transform (figure fig-a18-05). A schematic map, north up: the west block (Sinai–Israel)
// stays still and the east block (Arabia–Jordan) slides north along the fault. The fault steps to the
// left (west) three times; at each step the blocks move apart and a basin opens. The basin colour lies
// behind both blocks, so only the east block moves, by a transform. The control value is the slip in km.
explorableKit.kinds.transform = (() => {
const { svgEl, svgText, number } = explorableKit;

const W = 360, H = 600;
const TOP_KM = 455, S = 0.9; // Drawing units per km along the fault.
const Y = (km) => 24 + (TOP_KM - km) * S;
const STEP = 6; // Length of each oblique step, km.
// Fault segments from south to north: x of the segment, and the km where the next step starts (schematic).
const SEGMENTS = [[232, -105], [202, 175], [172, 330], [142, Infinity]];
const COPPER = { km: 25, x: 212, rx: 24, ry: 11 }; // One ore field across the fault, the larger part to the east.
const EILAT_KM = 0;

// Fault trace from far north to far south, as drawing points: each segment, then an oblique step to the next.
function trace(north, south) {
  const pts = [[SEGMENTS[0][0], south]];
  SEGMENTS.slice(0, -1).forEach(([x, stepKm], i) => pts.push([x, Y(stepKm)], [SEGMENTS[i + 1][0], Y(stepKm + STEP)]));
  pts.push([SEGMENTS.at(-1)[0], north]);
  return pts.reverse();
}
const d = (pts) => "M" + pts.map(([x, y]) => `${x} ${y.toFixed(1)}`).join(" L") + " Z";
const faultX = (km) => SEGMENTS.find(([, stepKm]) => km < stepKm)[0];

function valueText(km, spec) {
  return `${number(km)} ${spec.control.unit} צפונה`;
}

function mount(svg, spec, api) {
  const L = spec.labels;
  const t = spec.texts;
  const { max } = spec.control;
  const id = svg.closest("figure").id;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const extra = max * S + 20; // The east block reaches below the frame, so moving it north leaves no hole.
  const fault = trace(-20, H + extra);
  const westShape = d([[0, -20], ...fault.slice(0, -1), [fault.at(-1)[0], H + 20], [0, H + 20]]);
  const eastShape = d([[W, -20], ...fault, [W, H + extra]]);
  const defs = svgEl("defs", {}, svg);
  svgEl("path", { d: westShape }, svgEl("clipPath", { id: `${id}-west` }, defs));
  svgEl("path", { d: eastShape }, svgEl("clipPath", { id: `${id}-east` }, defs));

  svgEl("rect", { class: "tf-basin", x: 0, y: 0, width: W, height: H }, svg);
  svgEl("path", { class: "tf-west", d: westShape }, svg);
  const copper = (parent, side) => svgEl("ellipse", {
    class: "tf-copper", cx: COPPER.x, cy: Y(COPPER.km), rx: COPPER.rx, ry: COPPER.ry, "clip-path": `url(#${id}-${side})`,
  }, parent);
  copper(svg, "west");
  const east = svgEl("g", { class: "tf-east" }, svg);
  svgEl("path", { class: "tf-plate-east", d: eastShape }, east);
  copper(east, "east");

  const label = (text, attrs, parent = svg) =>
    svgText(text, { class: "xp-label", "text-anchor": "middle", ...attrs }, parent);
  const lines = (text, x, y, parent) => text.split("–").forEach((part, i, all) =>
    label(i < all.length - 1 ? `${part}–` : part, { x, y: y + i * 17 }, parent));
  lines(L.west_plate, 72, Y(260), svg);
  lines(L.east_plate, 290, Y(250), east);
  svgEl("path", { class: "tf-arrow", d: `M290 ${Y(200)} V${Y(150)} M282 ${Y(192)} L290 ${Y(200)} L298 ${Y(192)}` }, east);
  label(L.feinan, { x: COPPER.x + 30, y: Y(COPPER.km) + 4, "text-anchor": "end" }, east);
  label(L.timna, { x: COPPER.x - 26, y: Y(COPPER.km) + 4, "text-anchor": "start" });
  svgEl("circle", { class: "tf-town", cx: faultX(EILAT_KM) - 5, cy: Y(EILAT_KM), r: 3.5 }, svg);
  label(L.eilat, { x: faultX(EILAT_KM) - 12, y: Y(EILAT_KM) + 4, "text-anchor": "start", class: "xp-label xp-minor" });
  label(`↑ ${L.north}`, { x: 12, y: 18, "text-anchor": "end", class: "xp-label xp-compass" });

  // One label per basin, west of it; it moves to the basin's middle and shows once the basin is open.
  const basins = SEGMENTS.slice(0, -1).map(([, stepKm], i) => {
    const g = svgEl("g", { class: "tf-basin-label" }, svg);
    label(L.basins[i], { x: SEGMENTS[i + 1][0] - 8, y: 4, "text-anchor": "start" }, g);
    return { g, stepKm };
  });

  const grip = svgEl("g", { class: "tf-grip", transform: `translate(290 ${Y(90)})` }, east);
  svgEl("circle", { r: 16 }, grip);
  svgEl("path", { d: "M0 -9 L-5 -4 M0 -9 L5 -4 M0 -9 V9 M0 9 L-5 4 M0 9 L5 4" }, grip);
  api.drag(grip, (point, start) => api.setValue(Math.min(max, Math.max(0, start.value + (start.point.y - point.y) / S))));

  const list = new Intl.ListFormat("he", { type: "conjunction" });
  return (km) => {
    east.setAttribute("transform", `translate(0 ${(-km * S).toFixed(1)})`);
    const open = [];
    basins.forEach((b, i) => {
      const length = km - STEP;
      b.g.setAttribute("transform", `translate(0 ${Y(b.stepKm + STEP + Math.max(0, length) / 2).toFixed(1)})`);
      b.g.toggleAttribute("hidden", length < 12);
      if (length > 0) open.push(L.basins[i]);
    });
    if (km === 0) return t.before;
    const apart = t.apart.replace("{km}", number(km));
    if (km === spec.slip_km) return `${t.today} ${apart}`;
    return `${t.moving}${open.length ? `: ${list.format(open)}.` : "."} ${apart}`;
  };
}
return { valueText, mount };
})();
