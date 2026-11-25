// Shorelines on a real elevation map: the shrinking Dead Sea (kind "dead-sea", fig-a14-24) and Lake Lisan
// (kind "lisan", fig-a34-07). Both share one drawing: a relief map on one side, a level chart with the drag handle on
// the other. The map data (books/eli-raz/scripts/shoreline_maps.py) holds the "flood level" of each cell: the lowest
// lake level at which the lake reaches it. A cell is water when its flood level is at or below the lake level.
// The control value is a year (Dead Sea) or minus thousands of years ago (Lisan, so the oldest is on the left).
(() => {
const { interpolate, number, iso, MINUS, clamp, polyline } = explorableKit;

const W = 520, H = 720, PAD = 10;

// Bytes of a packed grid: base64 of zlib data (DecompressionStream "deflate" reads the zlib format).
async function unpack(b64, length) {
  const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate"));
  const codes = new Uint8Array(await new Response(stream).arrayBuffer());
  if (codes.length !== length) throw new Error(`shoreline: grid has ${codes.length} cells, expected ${length}`);
  return codes;
}

function hexRgb(color) {
  const rgb = [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16));
  if (color.length !== 7 || !color.startsWith("#") || rgb.some(Number.isNaN)) throw new Error(`shoreline: expected a #rrggbb colour, got ${color}`);
  return rgb;
}

// Marching squares over cell centres: the line between cells inside (flood code <= t) and outside, in grid units.
function contour(codes, cols, rows, t) {
  const path = [];
  const inside = (r, c) => (codes[r * cols + c] <= t ? 1 : 0);
  for (let r = 0; r < rows - 1; r++) {
    for (let c = 0; c < cols - 1; c++) {
      const k = inside(r, c) * 8 + inside(r, c + 1) * 4 + inside(r + 1, c + 1) * 2 + inside(r + 1, c);
      if (k === 0 || k === 15) continue;
      const top = [c + 1, r + 0.5], right = [c + 1.5, r + 1], bottom = [c + 1, r + 1.5], left = [c + 0.5, r + 1];
      const segments = {
        1: [[left, bottom]], 2: [[bottom, right]], 3: [[left, right]], 4: [[top, right]], 5: [[left, top], [bottom, right]],
        6: [[top, bottom]], 7: [[left, top]], 8: [[left, top]], 9: [[top, bottom]], 10: [[top, right], [left, bottom]],
        11: [[top, right]], 12: [[left, right]], 13: [[bottom, right]], 14: [[left, bottom]],
      }[k];
      for (const segment of segments) path.push(segment);
    }
  }
  return path;
}

// The map: relief image, water, reference shoreline, overlays and places, all in drawing units.
function makeMap(spec, map, env) {
  const [south, west, north, east] = map.bounds;
  const [kmY, kmX] = map.km_per_degree;
  const h = H - 2 * PAD;
  const w = (h * ((east - west) * kmX)) / ((north - south) * kmY);
  const x0 = W - PAD - w, y0 = PAD;
  const { cols, rows } = map;
  const at = (lon, lat) => [x0 + ((lon - west) / (east - west)) * w, y0 + ((north - lat) / (north - south)) * h];
  const cellKm2 = (((east - west) * kmX) / cols) * (((north - south) * kmY) / rows);
  const { base, step } = map.flood;
  // The same rounding as the packing script, so a cell floods at its own level.
  const code = (level) => clamp(Math.round((level - base) / step), 0, 255);
  const lakeCode = code(map.dem_lake);

  const state = { codes: null, relief: null, failed: null };
  Promise.all([
    unpack(map.flood.data, cols * rows),
    new Promise((resolve, reject) => { const img = new Image(); img.onload = () => resolve(img); img.onerror = reject; img.src = map.relief; }),
  ]).then(([codes, img]) => { state.codes = codes; state.relief = img; })
    .catch((err) => { state.failed = err; console.error(err); });

  const mask = document.createElement("canvas");
  mask.width = cols;
  mask.height = rows;
  const maskCtx = mask.getContext("2d");
  const pixels = maskCtx.createImageData(cols, rows);
  let maskCode = -1, maskColor = "";
  const paths = new Map(); // Flood code -> Path2D of the shoreline, in drawing units.
  const toUnits = (segments) => {
    const p = new Path2D(), sx = w / cols, sy = h / rows;
    for (const [[ax, ay], [bx, by]] of segments) { p.moveTo(x0 + ax * sx, y0 + ay * sy); p.lineTo(x0 + bx * sx, y0 + by * sy); }
    return p;
  };
  const shore = (t) => {
    if (!paths.has(t)) {
      if (paths.size > 300) paths.clear();
      paths.set(t, toUnits(contour(state.codes, cols, rows, t)));
    }
    return paths.get(t);
  };
  let hatchPattern = null, hatchKey = "";
  const hatch = (c, env) => {
    const color = env.color("--xp-land-edge"), key = `${color}|${env.pixel}`;
    if (key !== hatchKey) {
      const size = Math.max(4, Math.round(5 * env.pixel)), tile = document.createElement("canvas");
      tile.width = tile.height = size;
      const tc = tile.getContext("2d");
      tc.strokeStyle = color;
      tc.globalAlpha = 0.55;
      tc.lineWidth = Math.max(1, env.pixel * 0.7);
      tc.beginPath(); tc.moveTo(0, size); tc.lineTo(size, 0); tc.stroke();
      hatchPattern = c.createPattern(tile, "repeat");
      hatchPattern.setTransform(new DOMMatrix().scale(1 / env.pixel));
      hatchKey = key;
    }
    return hatchPattern;
  };
  const ringPaths = (rings) => rings.map((ring) => polyline(new Path2D(), ring.map(([lon, lat]) => at(lon, lat)), true));
  const ponds = ringPaths(map.ponds ?? []);

  return {
    rect: [x0, y0, w, h],
    at,
    ready: () => state.codes !== null,
    // Flood code for a lake level. Below the flat DEM lake surface the map has no shore: it stays at the surface.
    code: (level) => Math.max(code(level), lakeCode),
    belowData: (level) => level < map.dem_lake,
    area(t) {
      let n = 0;
      for (const v of state.codes) if (v <= t) n++;
      return n * cellKm2;
    },
    cellCode: (lon, lat) => {
      const r = Math.floor(((north - lat) / (north - south)) * rows), c = Math.floor(((lon - west) / (east - west)) * cols);
      return state.codes[r * cols + c];
    },
    draw(ctx, t, reference) {
      if (state.failed) throw state.failed;
      ctx.drawImage(env.layer(`relief-${state.relief ? 1 : 0}`, [x0, y0, w, h], (c) => {
        c.fillStyle = env.color("--xp-land");
        c.fillRect(x0, y0, w, h);
        if (!state.relief) return;
        c.drawImage(state.relief, x0, y0, w, h);
        c.globalAlpha = Number(env.color("--xp-map-dim")); // Dark mode: the light relief image under a dark veil.
        c.fillStyle = env.color("--paper");
        c.fillRect(x0, y0, w, h);
      }), x0, y0, w, h);
      if (!state.codes) { env.wantsFrame = true; return; }
      const color = env.color("--xp-lake");
      if (t !== maskCode || color !== maskColor) {
        const [r, g, b] = hexRgb(color), d = pixels.data;
        for (let i = 0; i < state.codes.length; i++) {
          d[i * 4] = r; d[i * 4 + 1] = g; d[i * 4 + 2] = b;
          d[i * 4 + 3] = state.codes[i] <= t ? 220 : 0;
        }
        maskCtx.putImageData(pixels, 0, 0);
        maskCode = t; maskColor = color;
      }
      ctx.save();
      ctx.beginPath();
      ctx.rect(x0, y0, w, h);
      ctx.clip();
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(mask, x0, y0, w, h);
      if (ponds.length) {
        // Evaporation ponds: the DEM has no lake bed there, so the map keeps them dry and hatches them.
        ctx.fillStyle = hatch(ctx, env);
        ctx.strokeStyle = env.color("--xp-land-edge");
        ctx.lineWidth = 0.8;
        for (const p of ponds) { ctx.fill(p); ctx.stroke(p); }
      }
      if (reference !== undefined) {
        ctx.strokeStyle = env.color("--xp-brine-ink");
        ctx.lineWidth = 1.1;
        ctx.setLineDash([3, 2.5]);
        ctx.stroke(shore(reference));
        ctx.setLineDash([]);
      }
      ctx.strokeStyle = env.color("--xp-lake-deep");
      ctx.lineWidth = 1.3;
      ctx.lineCap = "round";
      ctx.stroke(shore(t));
      ctx.restore();
      ctx.strokeStyle = env.color("--xp-salt-edge");
      ctx.lineWidth = 0.75;
      ctx.strokeRect(x0, y0, w, h);
    },
    // North arrow, scale bar and place names: fixed, drawn once into a layer.
    decorations(ctx, places) {
      ctx.drawImage(env.layer("map-labels", [0, 0, W, H], (c) => {
        const ink = env.color("--ink");
        for (const place of places) {
          const [x, y] = at(place.lon, place.lat);
          c.fillStyle = ink;
          c.beginPath(); c.arc(x, y, 2.2, 0, Math.PI * 2); c.fill();
          env.label(c, place.label, x + (place.side === "east" ? 5 : -5), y + 4, { align: place.side === "east" ? "left" : "right", size: 11, weight: 600 });
        }
        for (const area of spec.map_labels ?? []) {
          const [x, y] = at(area.lon, area.lat);
          env.label(c, area.label, x, y, { size: 11, weight: 700, color: area.water ? "--xp-fresh-ink" : "--soft" });
        }
        const km = spec.scale_km, bar = (km / ((east - west) * kmX)) * w;
        const bx = x0 + w - 8 - bar, by = y0 + h - 12;
        c.strokeStyle = ink; c.lineWidth = 1.5;
        c.beginPath(); c.moveTo(bx, by - 4); c.lineTo(bx, by); c.lineTo(bx + bar, by); c.lineTo(bx + bar, by - 4); c.stroke();
        env.label(c, `${km} ק"מ`, bx + bar / 2, by - 6, { size: 10.5, weight: 600 });
        const nx = x0 + 14, ny = y0 + 14; // Top left: the lakes reach the top right of the Lisan map.
        c.fillStyle = ink;
        c.beginPath(); c.moveTo(nx, ny - 8); c.lineTo(nx + 5, ny + 5); c.lineTo(nx, ny + 2); c.lineTo(nx - 5, ny + 5); c.closePath(); c.fill();
        env.label(c, "צ", nx, ny + 17, { size: 10.5, weight: 700 });
      }), 0, 0, W, H);
    },
  };
}

// A small line chart in the side panel: x is the control value, y a series. One y axis per chart.
function makeChart(box, xDomain, yDomain) {
  const [left, top, width, height] = box;
  const [x0, x1] = xDomain, [yTop, yBottom] = yDomain;
  return {
    box,
    x: (v) => left + ((v - x0) / (x1 - x0)) * width,
    y: (v) => top + ((yTop - v) / (yTop - yBottom)) * height,
    value: (px) => x0 + ((px - left) / width) * (x1 - x0),
  };
}

function drawAxes(c, env, chart, { xTicks, yTicks, xLabel, yLabel, title }) {
  const [left, top, width, height] = chart.box;
  c.strokeStyle = env.color("--rule");
  c.lineWidth = 1;
  for (const v of yTicks) {
    const y = chart.y(v.value);
    c.beginPath(); c.moveTo(left, y); c.lineTo(left + width, y); c.stroke();
    env.label(c, v.label, left - 4, y + 3.5, { align: "right", size: 10, weight: 500, color: "--soft" });
  }
  c.strokeStyle = env.color("--muted");
  c.beginPath(); c.moveTo(left, top + height); c.lineTo(left + width, top + height); c.stroke();
  for (const v of xTicks) {
    const x = chart.x(v.value);
    c.beginPath(); c.moveTo(x, top + height); c.lineTo(x, top + height + 4); c.stroke();
    env.label(c, v.label, x, top + height + 15, { size: 10, weight: 500, color: "--soft" });
  }
  env.label(c, title, left + width, top - (yLabel ? 22 : 9), { align: "right", size: 12, weight: 700 });
  if (yLabel) env.label(c, yLabel, left + width, top - 8, { align: "right", size: 10, weight: 500, color: "--soft" });
  if (xLabel) env.label(c, xLabel, left + width, top + height + 30, { align: "right", size: 10, weight: 500, color: "--soft" });
}

function seriesPath(chart, points) {
  return polyline(new Path2D(), points.map(([x, y]) => [chart.x(x), chart.y(y)]));
}

// Shared frame for both kinds: the map, the panel with its charts, and the handle on the level curve.
function scene(spec, env, config) {
  const map = makeMap(spec, spec.data.map.points, env);
  const panelRight = map.rect[0] - 22;
  const left = 60; // Room for the y tick labels at phone size.
  const chart = makeChart([left, config.levelTop, panelRight - left, config.levelHeight], [spec.control.min, spec.control.max], config.levelDomain);
  const levelPath = seriesPath(chart, config.curve);
  const extra = config.extraChart?.(left, panelRight);
  return {
    draw(ctx, value, env) {
      const level = config.level(value);
      const t = map.code(level);
      ctx.drawImage(env.layer("panel", [0, 0, W, H], (c) => {
        drawAxes(c, env, chart, config.levelAxes);
        config.panelExtras?.(c, chart);
        c.strokeStyle = env.color("--series");
        c.lineWidth = 2;
        c.lineJoin = "round";
        c.stroke(levelPath);
        if (extra) extra.drawStatic(c);
      }), 0, 0, W, H);
      const x = chart.x(value), y = chart.y(level);
      ctx.strokeStyle = env.color("--muted");
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 3]);
      ctx.beginPath(); ctx.moveTo(x, chart.box[1]); ctx.lineTo(x, chart.box[1] + chart.box[3]); ctx.stroke();
      ctx.setLineDash([]);
      if (extra) extra.drawValue(ctx, value);
      map.draw(ctx, t, config.reference === undefined ? undefined : map.code(config.reference));
      map.decorations(ctx, spec.places);
      if (!map.ready()) return spec.texts.loading;
      return config.summary(value, level, map, t);
    },
    handle: (value) => [chart.x(value), chart.y(config.level(value))],
    drag: (point) => clamp(chart.value(point.x), spec.control.min, spec.control.max),
  };
}

const metres = (level) => `${number(-level, 1)} מ' מתחת לפני הים`;
const area = (km2) => `${number(Math.round(km2 / 10) * 10)} קמ"ר`;

explorableKit.kinds["dead-sea"] = {
  view: [0, 0, W, H],
  valueParts(year, spec) {
    return { num: String(Math.round(year)), unit: "", note: metres(deadSeaLevel(Math.round(year), spec)) };
  },
  create(spec, env) {
    const t = spec.texts;
    const sinkholes = spec.data.sinkholes.points;
    const [firstCount, lastCount] = [sinkholes[0][0], sinkholes[sinkholes.length - 1][0]];
    const curve = [];
    for (let year = spec.control.min; year <= spec.control.max; year++) curve.push([year, deadSeaLevel(year, spec)]);
    const ticks = [1900, 1950, 2000].map((v) => ({ value: v, label: String(v) }));
    return scene(spec, env, {
      curve,
      level: (year) => deadSeaLevel(year, spec),
      levelTop: 46,
      levelHeight: 360,
      levelDomain: [-385, -445],
      reference: deadSeaLevel(spec.control.min, spec),
      levelAxes: {
        title: t.level_title, yLabel: t.level_unit, xTicks: ticks,
        yTicks: [-390, -400, -410, -420, -430, -440].map((v) => ({ value: v, label: `${MINUS}${-v}` })),
      },
      panelExtras(c, chart) {
        // Before the measured series the level rests on a few historic values: a lighter band marks those years.
        const [left, top, , height] = chart.box;
        const to = chart.x(spec.measured_from);
        c.fillStyle = env.color("--xp-dot");
        c.fillRect(left, top, to - left, height);
        env.label(c, t.sparse, (left + to) / 2, top + height - 8, { size: 10, weight: 500, color: "--soft" });
        const y = chart.y(spec.data.map.points.dem_lake);
        c.strokeStyle = env.color("--xp-brine-ink");
        c.setLineDash([3, 3]);
        c.beginPath(); c.moveTo(left, y); c.lineTo(chart.box[0] + chart.box[2], y); c.stroke();
        c.setLineDash([]);
        env.label(c, t.dem_line, left + 2, y - 5, { align: "left", size: 10, weight: 600, color: "--xp-brine-ink" });
      },
      extraChart(left, right) {
        const chart = makeChart([left, 490, right - left, 170], [spec.control.min, spec.control.max], [6500, 0]);
        const path = seriesPath(chart, sinkholes);
        return {
          drawStatic(c) {
            drawAxes(c, env, chart, {
              title: t.count_title, xTicks: ticks,
              yTicks: [0, 3000, 6000].map((v) => ({ value: v, label: number(v) })),
            });
            c.strokeStyle = env.color("--series");
            c.lineWidth = 2;
            c.stroke(path);
          },
          drawValue(ctx, year) {
            const x = chart.x(year);
            ctx.strokeStyle = env.color("--muted");
            ctx.setLineDash([2, 3]);
            ctx.beginPath(); ctx.moveTo(x, chart.box[1]); ctx.lineTo(x, chart.box[1] + chart.box[3]); ctx.stroke();
            ctx.setLineDash([]);
            const [left, top, width] = chart.box;
            if (year < firstCount) { env.label(ctx, t.count_before, left + 4, top + 14, { align: "left", size: 10, weight: 600, color: "--soft" }); return; }
            const n = interpolate(sinkholes, Math.min(year, lastCount));
            const y = chart.y(n);
            ctx.fillStyle = env.color("--series");
            ctx.beginPath(); ctx.arc(chart.x(Math.min(year, lastCount)), y, 3.5, 0, Math.PI * 2); ctx.fill();
            const text = `${number(Math.round(n / 10) * 10)}${year > lastCount ? ` ${t.count_end}` : ""}`;
            env.label(ctx, text, Math.min(x, left + width) - 7, Math.max(top + 10, y - 6), { align: "right", size: 11, weight: 700, color: "--accent" });
          },
        };
      },
      summary(year, level, map, code) {
        const rounded = Math.round(year);
        const parts = [`${iso(String(rounded))}: ${t.level_is} ${iso(metres(level))}${rounded < spec.measured_from ? ` (${t.approx})` : ""}.`];
        if (map.belowData(level)) parts.push(t.below_data);
        else parts.push(`${t.area_is} ${iso(area(map.area(code)))}.`);
        if (rounded < firstCount) parts.push(t.count_none);
        else if (rounded > lastCount) parts.push(t.count_after);
        else parts.push(`${t.count_is} ${iso(number(Math.round(interpolate(sinkholes, rounded) / 10) * 10))}.`);
        return parts.join(" ");
      },
    });
  },
};

// Measured monthly levels from late 1976; before that a few historic values (spec.historic, each with its source).
const levelSeries = new WeakMap();
function deadSeaLevel(year, spec) {
  if (!levelSeries.has(spec)) {
    const measured = spec.data.level.points.map(([date, value]) => {
      const [y, m, d] = date.split("-").map(Number);
      return [y + (m - 1) / 12 + (d - 1) / 365, value];
    });
    const first = measured[0][0];
    const historic = spec.historic.map((p) => [p.year, p.level]);
    if (historic.some(([y]) => y >= first)) throw new Error("dead-sea: a historic value overlaps the measured series");
    levelSeries.set(spec, { points: [...historic, ...measured], last: measured[measured.length - 1] });
  }
  const { points, last } = levelSeries.get(spec);
  // A year stands for its middle; the last year shows the latest measurement.
  return year >= spec.control.max ? last[1] : interpolate(points, Math.min(year + 0.5, last[0]));
}

explorableKit.kinds.lisan = {
  view: [0, 0, W, H],
  valueParts(value, spec) {
    return { num: number(-value, 1), unit: spec.control.unit, note: metres(lisanLevel(value, spec)) };
  },
  create(spec, env) {
    const t = spec.texts;
    const curve = spec.data.level.points.filter(([ka]) => ka >= -spec.control.max - 0.5 && ka <= -spec.control.min + 0.5).map(([ka, v]) => [-ka, v]);
    const today = spec.data.today.points[spec.data.today.points.length - 1][1];
    return scene(spec, env, {
      curve,
      level: (value) => lisanLevel(value, spec),
      levelTop: 46,
      levelHeight: 600,
      levelDomain: [-150, -450],
      reference: undefined,
      levelAxes: {
        title: t.level_title, yLabel: t.level_unit, xLabel: t.age_unit,
        xTicks: [-60, -40, -20].map((v) => ({ value: v, label: number(-v) })),
        yTicks: [-150, -200, -250, -300, -350, -400, -450].map((v) => ({ value: v, label: `${MINUS}${-v}` })),
      },
      panelExtras(c, chart) {
        const [left, , width] = chart.box;
        for (const [level, text, color] of [[spec.photo_top, t.photo_line, "--xp-brine-ink"], [today, t.today_line, "--xp-fresh-ink"]]) {
          const y = chart.y(level);
          c.strokeStyle = env.color(color);
          c.setLineDash([3, 3]);
          c.beginPath(); c.moveTo(left, y); c.lineTo(left + width, y); c.stroke();
          c.setLineDash([]);
          env.label(c, text, left + 2, y + (level === today ? -5 : 13), { align: "left", size: 10, weight: 600, color });
        }
      },
      summary(value, level, map, code) {
        const parts = [`${t.before} ${iso(number(-value, 1))} ${t.age_unit_text}: ${t.level_is} ${iso(metres(level))}, ${iso(number(Math.round(level - today)))} ${t.above_today}.`];
        parts.push(`${t.area_is} ${iso(area(map.area(code)))}.`);
        // The northernmost point of spec.reach (listed north first) that the water covers.
        const reached = spec.reach.find((point) => map.cellCode(point.lon, point.lat) <= code);
        parts.push(reached ? reached.text : t.reach_none);
        return parts.join(" ");
      },
    });
  },
};

// Bartov's level curve (digitized, fig-a34-05) at an age; the curve is sorted by age, ages in thousands of years.
function lisanLevel(value, spec) {
  return interpolate(spec.data.level.points, -value);
}
})();
