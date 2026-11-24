// Mount Sodom rises (figure fig-a34-17). A schematic west-east section after the printed figure: salt flows
// from the layer under the rift, up the marginal fault, into a column of upturned layers. The control is the
// rise of the salt in metres. Up to the Lake Lisan rise (lisan_rise_m[1]) the salt dissolves at a flat salt
// mirror under the lake and only the cap rock grows (insoluble_fraction of the dissolved salt). After that the
// lake is dry, and the layers rise since_lisan_m, the centre faster than the flanks, so the mirror breaks.
explorableKit.kinds.diapir = (() => {
const { svgEl, svgText, number } = explorableKit;

const W = 600, H = 360, TOP = -70; // The drawing starts above y 0: room for the risen mountain.
const MIRROR = 112; // Drawing y of the salt mirror: the floor of Lake Lisan around the mountain.
const CAP_SCALE = 0.9; // Drawing units per metre of cap rock.
const RISE_SCALE = 1.1; // Drawing units per metre of rise after the lake.
const COLUMN = { x: 252, width: 96, bottom: 440 };
const FACTORS = [0.6, 0.78, 0.92, 1, 0.9, 0.74, 0.58]; // Share of the full rise per layer, west to east (schematic).

function valueText(rise, spec) {
  const lake = spec.lisan_rise_m[1];
  return rise <= lake ? `${number(rise)} ${spec.control.unit} לתוך אגם הלשון`
    : `${number(lake)} ${spec.control.unit} באגם הלשון ועוד ${number(rise - lake)} ${spec.control.unit} אחריו`;
}

function mount(svg, spec, api) {
  const L = spec.labels;
  const t = spec.texts;
  const lakeRise = spec.lisan_rise_m[1];
  const { max } = spec.control;
  svg.setAttribute("viewBox", `0 ${TOP} ${W} ${H - TOP}`);

  const lake = svgEl("rect", { class: "dp-lake", x: 0, y: TOP, width: W, height: 140 - TOP }, svg);
  const strip = COLUMN.width / FACTORS.length;
  const layers = FACTORS.map((f, i) => {
    const g = svgEl("g", {}, svg);
    const x = COLUMN.x + i * strip;
    svgEl("rect", { class: i % 2 ? "dp-salt" : "dp-salt alt", x, y: MIRROR, width: strip, height: COLUMN.bottom - MIRROR }, g);
    const cap = svgEl("rect", { class: "dp-cap", x, width: strip }, g);
    return { g, f, cap };
  });
  svgEl("path", { class: "dp-sand", d: `M0 ${MIRROR} H${COLUMN.x} V${H} H0 Z` }, svg);
  svgEl("path", { class: "dp-sand", d: `M${COLUMN.x + COLUMN.width} 138 H${W} V${H} H${COLUMN.x + COLUMN.width} Z` }, svg);
  svgEl("rect", { class: "dp-salt", x: 0, y: 212, width: 170, height: 16 }, svg);
  svgEl("path", { class: "dp-salt", d: `M${COLUMN.x + COLUMN.width} 250 C 370 262, 380 285, 400 290 H${W} V346 H400 C 370 346, 350 320, ${COLUMN.x + COLUMN.width} 300 Z` }, svg);
  for (const y of [302, 314, 326, 338]) svgEl("line", { class: "dp-bed", x1: 400, x2: W, y1: y, y2: y }, svg);
  svgEl("path", { class: "dp-arrow", d: "M392 318 C 378 300, 368 285, 358 270 M356 282 L357 268 L370 274" }, svg);
  const mirror = svgEl("line", { class: "dp-mirror", x1: COLUMN.x - 30, x2: COLUMN.x + COLUMN.width + 30, y1: MIRROR, y2: MIRROR }, svg);

  const label = (text, attrs, cls = "xp-label") => svgText(text, { class: cls, "text-anchor": "middle", ...attrs }, svg);
  label(L.west, { x: 6, y: H - 8, "text-anchor": "end" }, "xp-label xp-compass");
  label(L.east, { x: W - 6, y: H - 8, "text-anchor": "start" }, "xp-label xp-compass");
  label(L.amiaz, { x: 120, y: MIRROR - 8 });
  label(L.rift, { x: 480, y: 130 });
  label(L.sand, { x: 120, y: 175 }, "xp-label xp-minor");
  label(L.sand, { x: 480, y: 215 }, "xp-label xp-minor");
  label(L.salt, { x: 85, y: 246 });
  label(L.salt, { x: 500, y: 278 });
  const lakeLabel = label(L.lake, { x: 470, y: 20 });
  const mirrorLabel = label(L.mirror, { x: COLUMN.x - 34, y: MIRROR + 4, "text-anchor": "start" });
  const capLabel = label(L.cap, { x: COLUMN.x + COLUMN.width + 8, "text-anchor": "end" });
  const sodom = label(L.sodom, { x: COLUMN.x + COLUMN.width / 2 });

  // Drag the salt column up. 200 drawing units of drag cover the whole range.
  const grip = svgEl("g", { class: "dp-grip" }, svg);
  svgEl("rect", { x: -48, y: -30, width: 96, height: 60, fill: "transparent" }, grip);
  svgEl("circle", { r: 14 }, grip);
  svgEl("path", { d: "M0 -8 L-5 -3 M0 -8 L5 -3 M0 -8 V8 M0 8 L-5 3 M0 8 L5 3" }, grip);
  api.drag(grip, (point, start) => api.setValue(Math.min(max, Math.max(0, start.value + ((start.point.y - point.y) * max) / 200))));

  return (rise) => {
    const dissolved = Math.min(rise, lakeRise);
    const after = Math.max(0, rise - lakeRise);
    const capM = dissolved * spec.insoluble_fraction;
    const capH = capM * CAP_SCALE;
    let top = MIRROR;
    for (const layer of layers) {
      const lift = after * RISE_SCALE * layer.f;
      layer.g.setAttribute("transform", `translate(0 ${(-lift).toFixed(1)})`);
      layer.cap.setAttribute("y", (MIRROR - capH).toFixed(1));
      layer.cap.setAttribute("height", capH.toFixed(1));
      top = Math.min(top, MIRROR - capH - lift);
    }
    const dry = rise > lakeRise;
    for (const el of [lake, lakeLabel, mirror, mirrorLabel]) el.toggleAttribute("hidden", dry);
    capLabel.toggleAttribute("hidden", capM < 8);
    capLabel.setAttribute("y", (MIRROR - capH / 2 + 4 - after * RISE_SCALE * FACTORS.at(-1)).toFixed(1));
    sodom.setAttribute("y", (top - 10).toFixed(1));
    grip.setAttribute("transform", `translate(${COLUMN.x + COLUMN.width / 2} ${(top + 40).toFixed(1)})`);

    if (rise === 0) return t.start;
    if (!dry) return `${t.lake} ${t.cap.replace("{rise}", number(dissolved)).replace("{cap}", number(Math.round(capM)))}`;
    const years = Math.round((after / spec.since_lisan_m) * spec.since_lisan_years / 100) * 100;
    const text = t.dry.replace("{rise}", number(after)).replace("{years}", number(years));
    return rise === max ? `${text} ${t.today}` : text;
  };
}
return { valueText, mount };
})();
