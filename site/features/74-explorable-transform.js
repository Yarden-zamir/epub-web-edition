// The Dead Sea transform (figure fig-a18-05). A map from real geography (spec.geo, written by
// books/eli-raz/scripts/transform_geo.py: Natural Earth, Wikidata, a sinusoidal projection in km), north up. The
// "today" state is the map to scale. Going back, both blocks move south relative to Eurasia (the fixed grid) at their
// present-day velocities (GSRM v2.1): the Arabian block faster than the Sinai–Africa block, so that the difference
// between them is the book's 105 km of left-lateral slip. The basins on the fault (Gulf of Eilat, Dead Sea, Kinneret)
// open with the slip, from their south ends. The control value is that relative slip, in km.
explorableKit.kinds.transform = (() => {
const { number, iso, ramp, shape } = explorableKit;

const W = 360, H = 600;
const R = 6371.0088, LON0 = 35; // The projection of transform_geo.py, for the grid and the labels.
const geoKm = (lon, lat) => [R * ((lon - LON0) * Math.PI / 180) * Math.cos(lat * Math.PI / 180), R * lat * Math.PI / 180];
const SPEED_UNITS = 3.6; // Arrow length, drawing units per mm/yr.

function valueParts(km, spec) {
  return { num: number(km), unit: spec.control.unit, note: "" };
}

function create(spec, env) {
  const L = spec.labels, t = spec.texts, geo = spec.geo;
  const [fx0, fy0, fx1, fy1] = geo.frame;
  const S = W / (fx1 - fx0); // Drawing units per km.
  const X = (x) => (x - fx0) * S, Y = (y) => (fy1 - y) * S;
  const pt = ([x, y]) => [X(x), Y(y)];
  const at = (lon, lat) => pt(geoKm(lon, lat));
  const max = spec.control.max;
  const moveA = geo.displacement_km.arabia, moveS = geo.displacement_km.sinai; // Full displacements, km east and north.
  // Relative slip direction (east block against west block), as a unit vector in km: basins open along it.
  const rel = [moveA[0] - moveS[0], moveA[1] - moveS[1]], relLen = Math.hypot(...rel), along = [rel[0] / relLen, rel[1] / relLen];

  const ringsPath = (rings) => { const p = new Path2D(); for (const r of rings) p.addPath(shape(r.map(pt))); return p; };
  const land = ringsPath(geo.land);
  const fault = geo.fault.map(pt);
  // The two sides of the fault, as regions: west of the trace (Sinai, Africa) and east of it (Arabia).
  const westSide = shape([[-1e4, Y(geo.fault[0][1])], ...fault, [-1e4, fault.at(-1)[1]]]);
  const eastSide = shape([[1e4, Y(geo.fault[0][1])], ...fault, [1e4, fault.at(-1)[1]]]);
  const suez = geo.suez.map(pt), africa = shape([[-1e4, suez[0][1]], ...suez, [-1e4, suez.at(-1)[1]]]);
  // A strip of ground along the trace north of the Straits of Tiran, under both blocks: where the blocks part on a bend
  // going back, and where the Gulf of Eilat is still closed, ground shows, not sea.
  const tiranY = geo.places.tiran[1];
  const onLand = geo.fault.filter(([, y]) => y >= tiranY);
  const strip = shape([...onLand.map(([x, y]) => pt([x - 20, y])), ...onLand.map(([x, y]) => pt([x + 35, y])).reverse()]);
  const basins = [
    { key: "gulf", rings: geo.gulf, water: "sea", name: L.basins[0] },
    { key: "dead_sea", rings: geo.lakes.dead_sea, water: "--xp-lake", name: L.basins[1] },
    { key: "kinneret", rings: geo.lakes.kinneret, water: "--xp-lake", name: L.basins[2] },
  ].map((b) => {
    const proj = b.rings.flat().map(([x, y]) => x * along[0] + y * along[1]);
    const xs = b.rings.flat().map(([x]) => x), ys = b.rings.flat().map(([, y]) => y);
    return { ...b, path: ringsPath(b.rings), from: Math.min(...proj), to: Math.max(...proj), west: Math.min(...xs), centre: (Math.min(...xs) + Math.max(...xs)) / 2, mid: (Math.min(...ys) + Math.max(...ys)) / 2 };
  });
  const P = geo.places;
  const oreFeinan = new Path2D(), oreTimna = new Path2D();
  oreFeinan.ellipse(...pt(P.feinan), 12.5 * S, 10 * S, 0, 0, Math.PI * 2); // The Feinan copper district, 25 x 20 km (a18-p022).
  oreTimna.ellipse(...pt(P.timna), 4 * S, 3 * S, 0, 0, Math.PI * 2); // Timna: far smaller (a18-p018); its size is schematic.
  const list = new Intl.ListFormat("he", { type: "conjunction" });
  const ARABIA_AT = at(36.2, 31.3), SINAI_AT = at(33.9, 29.35);
  const HANDLE = at(36.15, 30.1);
  const dirA = [moveA[0] * S, -moveA[1] * S], dirLen = Math.hypot(...dirA); // Handle path on screen per full slip.
  let dots = null, dotsColor = "";
  // Whether a point of the drawing is land, with each block at its offset: a sea label hides there.
  const probe = document.createElement("canvas").getContext("2d");
  const isLand = ([x, y], offW, offE) =>
    (probe.isPointInPath(westSide, x - offW[0], y - offW[1]) && probe.isPointInPath(land, x - offW[0], y - offW[1])) ||
    (probe.isPointInPath(eastSide, x - offE[0], y - offE[1]) && probe.isPointInPath(land, x - offE[0], y - offE[1]));
  const inView = ([x, y]) => x > 20 && x < W - 20 && y > 14 && y < H - 14;

  function texture(c) { // A small dot pattern for the rock, one tile per theme.
    const color = env.color("--xp-dot");
    if (color !== dotsColor) {
      const tile = document.createElement("canvas");
      tile.width = tile.height = 9;
      const tc = tile.getContext("2d");
      tc.fillStyle = color;
      tc.beginPath(); tc.arc(2, 2, 0.9, 0, Math.PI * 2); tc.arc(6.5, 6.5, 0.7, 0, Math.PI * 2); tc.fill();
      dots = c.createPattern(tile, "repeat");
      dotsColor = color;
    }
    return dots;
  }
  function ground(c, region, top, bottom, key) {
    c.save();
    c.clip(region);
    c.fillStyle = env.gradient(key, 0, 0, 0, H, [[0, top], [1, bottom]]);
    c.fill(land);
    c.fillStyle = texture(c);
    c.fill(land);
    c.restore();
  }
  function arrow(c, [x, y], [e, n]) { // Velocity relative to Eurasia, from (x, y): length in proportion to speed.
    const length = Math.hypot(e, n) * SPEED_UNITS;
    c.save();
    c.translate(x, y);
    c.rotate(Math.atan2(e, n));
    c.fillStyle = env.color("--ink");
    c.fill(shape([[-2.4, 0], [-2.4, 11 - length], [-7, 11 - length], [0, -length], [7, 11 - length], [2.4, 11 - length], [2.4, 0]]));
    c.restore();
  }
  // Open part of a basin: the stretch from its south end, along the slip, as long as the slip so far allows.
  function opened(c, b, fraction) {
    const limit = b.from + (b.to - b.from) * fraction;
    const [ax, ay] = along, cx = limit * ax, cy = limit * ay; // A point on the limit line, km.
    const far = 2000;
    c.save();
    c.clip(shape([[cx - ay * far, cy + ax * far], [cx + ay * far, cy - ax * far], [cx + ay * far - ax * far, cy - ax * far - ay * far], [cx - ay * far - ax * far, cy + ax * far - ay * far]].map(pt)));
    c.fillStyle = b.water === "sea" ? env.gradient("sea", 0, 0, W, 0, [[0, "--xp-basin-light"], [1, "--xp-basin"]]) : env.color(b.water);
    c.fill(b.path);
    c.restore();
  }

  const WEST_BOX = [-40, -140, W + 80, H + 180], EAST_BOX = [-40, -230, W + 80, H + 270];
  function draw(ctx, km, env) {
    const f = km / max, back = 1 - f; // Share of the slip done; the rest is still to come.
    const offW = [-moveS[0] * back * S, moveS[1] * back * S], offE = [-moveA[0] * back * S, moveA[1] * back * S];
    ctx.fillStyle = env.gradient("sea", 0, 0, W, 0, [[0, "--xp-basin-light"], [1, "--xp-basin"]]);
    ctx.fillRect(0, 0, W, H);

    ctx.drawImage(env.layer("west", WEST_BOX, (c) => {
      c.fillStyle = env.gradient("sinai", 0, 0, 0, H, [[0, "--xp-plate-a"], [1, "--xp-plate-a-deep"]]);
      c.fill(strip);
      ground(c, westSide, "--xp-plate-a", "--xp-plate-a-deep", "sinai");
      c.save();
      c.clip(westSide);
      ground(c, africa, "--xp-plate-a-deep", "--xp-plate-b-deep", "africa");
      c.restore();
      c.strokeStyle = env.color("--xp-land-edge");
      c.lineWidth = 0.7;
      c.save();
      c.clip(westSide);
      c.stroke(land);
      c.restore();
      c.fillStyle = env.color("--xp-copper");
      c.fill(oreTimna);
    }), WEST_BOX[0] + offW[0], WEST_BOX[1] + offW[1], WEST_BOX[2], WEST_BOX[3]);
    ctx.save();
    ctx.translate(...offW);
    opened(ctx, basins[0], f);
    ctx.restore();

    ctx.drawImage(env.layer("east", EAST_BOX, (c) => {
      ground(c, eastSide, "--xp-plate-b", "--xp-plate-b-deep", "arabia");
      c.strokeStyle = env.color("--xp-land-edge");
      c.lineWidth = 0.7;
      c.save();
      c.clip(eastSide);
      c.stroke(land);
      c.restore();
      c.fillStyle = env.color("--xp-copper");
      c.fill(oreFeinan);
      c.strokeStyle = env.color("--xp-copper-edge");
      c.stroke(oreFeinan);
    }), EAST_BOX[0] + offE[0], EAST_BOX[1] + offE[1], EAST_BOX[2], EAST_BOX[3]);

    ctx.save();
    ctx.translate(...offW);
    for (const b of basins.slice(1)) opened(ctx, b, f);
    ctx.strokeStyle = env.color("--ink");
    ctx.lineWidth = 1.3;
    ctx.lineJoin = "round";
    ctx.setLineDash([5, 3]);
    ctx.stroke(shape(fault, false));
    ctx.setLineDash([]);
    ctx.restore();

    // The grid of longitude and latitude stays: it is the frame of Eurasia.
    ctx.drawImage(env.layer("grid", [0, 0, W, H], (c) => {
      c.strokeStyle = env.color("--ink");
      c.globalAlpha = 0.18;
      c.lineWidth = 0.8;
      for (const lon of geo.graticule.lon) {
        const line = [];
        for (let lat = 25; lat <= 37; lat += 0.5) line.push(at(lon, lat));
        c.stroke(shape(line, false));
      }
      for (const lat of geo.graticule.lat) c.stroke(shape([at(30, lat), at(40, lat)], false));
      c.globalAlpha = 1;
      for (const lat of geo.graticule.lat) env.label(c, `${lat}°`, 4, at(35, lat)[1] - 3, { align: "left", size: 10, weight: 500, color: "--muted" });
      for (const lon of geo.graticule.lon) { const [x] = at(lon, 27.6); if (x > 10 && x < W - 30) env.label(c, `${lon}°`, x + 3, H - 6, { align: "left", size: 10, weight: 500, color: "--muted" }); }
    }), 0, 0, W, H);

    // Places and names, moving with their blocks.
    const onW = ([x, y]) => [x + offW[0], y + offW[1]], onE = ([x, y]) => [x + offE[0], y + offE[1]];
    const [tx, ty] = onW(pt(P.timna)), [fxp, fyp] = onE(pt(P.feinan)), [ex, ey] = onW(pt(P.eilat));
    ctx.strokeStyle = env.color("--xp-copper-edge");
    ctx.lineWidth = 1.2;
    ctx.setLineDash([3, 3]);
    ctx.stroke(shape([[tx, ty], [fxp, fyp]], false));
    ctx.setLineDash([]);
    const apartKm = Math.hypot(fxp - tx, fyp - ty) / S;
    // The distance on the line; when the two are close, only in the readout (the label would cover Feinan's name).
    if (apartKm >= 45) env.label(ctx, `${number(Math.round(apartKm))} ${spec.control.unit}`, (tx + fxp) / 2 + 6, (ty + fyp) / 2 + 4, { align: "left", weight: 700, size: 12, color: "--xp-copper-edge" });
    ctx.fillStyle = env.color("--ink");
    ctx.beginPath(); ctx.arc(ex, ey, 2.6, 0, Math.PI * 2); ctx.fill();
    env.label(ctx, L.eilat, ex - 6, ey + 10, { align: "right", size: 12 });
    env.label(ctx, L.timna, tx - 7, ty + 2, { align: "right", size: 12 });
    env.label(ctx, L.feinan, fxp + 15 * S + 3, fyp + 4, { align: "left", size: 12 });
    // Each block's arrow starts at its name, which sits below it.
    arrow(ctx, onE(ARABIA_AT), geo.velocity_mm_yr.arabia);
    arrow(ctx, onW(SINAI_AT), geo.velocity_mm_yr.sinai);
    const speed = (v) => `${L.about}${number(Math.round(v[1]))} ${L.mm_per_year}`; // Northward, like the panel.
    const [ax, ay] = onE(ARABIA_AT), [sx, sy] = onW(SINAI_AT), line = 14 * env.unit;
    env.label(ctx, L.east_plate, ax, ay + line);
    env.label(ctx, speed(geo.velocity_mm_yr.arabia), ax, ay + 2 * line, { size: 11, weight: 500 });
    env.label(ctx, L.west_plate, sx, sy + line);
    env.label(ctx, speed(geo.velocity_mm_yr.sinai), sx, sy + 2 * line, { size: 11, weight: 500 });
    env.label(ctx, L.africa, ...onW(at(32.6, 27.75)), { align: "left", size: 12 });
    // Sea names move with the Sinai–Africa block, like its coasts; each hides where its point is land or off the map.
    for (const [name, lon, lat] of [[L.suez, 33.1, 28.95], [L.mediterranean, 33.4, 32.45], [L.red_sea, 35.05, 27.6]]) {
      const p = onW(at(lon, lat));
      if (inView(p) && !isLand(p, offW, offE)) env.label(ctx, name, ...p, { size: name === L.suez ? 11 : 12, weight: 500 });
    }
    const shown = ramp(f, 0.6, 0.85), names = []; // The basins' names fade in once they are mostly open.
    if (shown > 0.01) {
      ctx.globalAlpha = shown;
      for (const b of basins) {
        // The gulf's name on its water (Sinai beside it is narrow); the lakes' names west of them.
        if (b.key === "gulf") env.label(ctx, b.name, ...onW(pt([b.centre, b.mid])), { size: 12 });
        else { const [bx, by] = onW(pt([b.west, b.mid])); env.label(ctx, b.name, bx - 6, by + 4, { align: "right", size: 12 }); }
        names.push(b.name);
      }
      ctx.globalAlpha = 1;
    }

    // Live, top left over the sea: how far each block moved north since the start, and their difference (the slip).
    const rows = [[L.row_arabia, moveA[1] * f], [L.row_sinai, moveS[1] * f], [L.difference, km]];
    const size = env.unit > 1.3 ? 11 : 12, gap = (size + 5) * env.unit, panelH = gap * rows.length + 8 * env.unit;
    ctx.fillStyle = env.color("--paper");
    ctx.globalAlpha = 0.88;
    ctx.beginPath(); ctx.roundRect(6, 6, 150 * env.unit, panelH, 6 * env.unit); ctx.fill();
    ctx.globalAlpha = 1;
    rows.forEach(([name, value], i) => {
      const y = 6 + gap * (i + 1) - 2 * env.unit;
      env.label(ctx, `${name}:`, 6 + 146 * env.unit, y, { align: "right", size, weight: i === 2 ? 700 : 600 });
      env.label(ctx, `${number(Math.round(value))} ${spec.control.unit}`, 12 * env.unit, y, { align: "left", size, weight: 700 });
    });
    // Scale bar: 100 km, under the panel, over the sea.
    const barX = 10, barY = 6 + panelH + 24 * env.unit;
    ctx.strokeStyle = env.color("--ink");
    ctx.lineWidth = 1.5;
    ctx.stroke(shape([[barX, barY - 4], [barX, barY], [barX + 100 * S, barY], [barX + 100 * S, barY - 4]], false));
    env.label(ctx, `100 ${spec.control.unit}`, barX + 50 * S, barY - 6, { size: 11, weight: 600 });

    const whole = Math.round(km);
    const apart = t.apart.replace("{km}", iso(number(Math.round(apartKm))));
    if (whole === 0) return `${t.before} ${apart}`;
    if (whole === spec.slip_km) return `${t.today} ${apart}`;
    return `${t.moving}${names.length ? `: ${list.format(names)}.` : "."} ${apart}`;
  }

  return {
    draw,
    handle: (km) => { const back = 1 - km / max; return [HANDLE[0] - dirA[0] * back, HANDLE[1] - dirA[1] * back]; },
    // The handle moves with the Arabian block: the pointer's movement along that path, in slip km.
    drag: (point, start) => start.value + ((point.x - start.point.x) * dirA[0] + (point.y - start.point.y) * dirA[1]) / (dirLen * dirLen) * max,
  };
}
return { view: [0, 0, W, H], animated: false, valueParts, create };
})();
