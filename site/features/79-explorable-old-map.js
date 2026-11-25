// An old map and today (chapter a07; data: books/eli-raz/scripts/old_maps.py). The printed map stays as printed.
// Today's Dead Sea, salt ponds, lower Jordan and Mediterranean coast come in the frame of the printed image, through a
// fitted similarity (turn, one scale, shift). The control is a swipe: left of the line today's map, right of it the old
// map with today's Dead Sea shore dashed over it. Each named place has a ring where the old map puts it, a dot where it
// really is, a line between them and the distance in km.
// Drawing units are pixels of the printed image: the spec's "view" is [0, 0, width, height].
explorableKit.kinds["old-map"] = (() => {
const { number, clamp, shape, polyline } = explorableKit;

const images = new Map(); // URL -> Image; the printed figure's own <img> loads the same file.
function oldImage(url) {
  if (!images.has(url)) {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    images.set(url, img);
  }
  return images.get(url);
}

// Where the segment from a to b leaves the box [m, w - m] x [m, h - m]: b itself when it lies inside.
function clipToBox([ax, ay], [bx, by], w, h, m) {
  let t = 1;
  const dx = bx - ax, dy = by - ay;
  if (bx < m) t = Math.min(t, (m - ax) / dx);
  if (bx > w - m) t = Math.min(t, (w - m - ax) / dx);
  if (by < m) t = Math.min(t, (m - ay) / dy);
  if (by > h - m) t = Math.min(t, (h - m - ay) / dy);
  return { point: [ax + dx * t, ay + dy * t], inside: t === 1 };
}

function valueParts(value) {
  return { num: number(value), unit: "%", note: "" };
}

function create(spec, env) {
  if (!Array.isArray(spec.view) || spec.view.length !== 4) throw new Error(`old-map ${spec.figure}: needs a view`);
  const [, , W, H] = spec.view;
  const img = oldImage(spec.image);
  const L = spec.labels;
  const sea = spec.sea.map((r) => shape(r));
  const ponds = spec.ponds.map((r) => shape(r));
  const rivers = spec.rivers.map((r) => shape(r, false));
  const coast = spec.coast.map((r) => shape(r, false));
  const u = (px) => px * env.unit; // CSS pixels in drawing units.
  const CREDIT = { size: 10, weight: 500, color: "--muted" };
  const northArrow = () => ({ r: u(16), cx: u(26), cy: u(30) });

  // Today's map in the frame of the old one: land, water, north and the credit.
  function drawToday(c) {
    c.fillStyle = env.color("--xp-land");
    c.fillRect(0, 0, W, H);
    // Salt ponds: pale water with a thin edge, apart from the open lake in both themes.
    c.fillStyle = env.color("--xp-fresh");
    c.strokeStyle = env.color("--xp-fresh-ink");
    c.lineWidth = u(0.75);
    for (const p of ponds) { c.fill(p); c.stroke(p); }
    c.fillStyle = env.color("--xp-lake");
    for (const p of sea) c.fill(p);
    c.lineJoin = c.lineCap = "round";
    c.strokeStyle = env.color("--xp-lake");
    c.lineWidth = u(2);
    for (const p of rivers) c.stroke(p);
    c.strokeStyle = env.color("--xp-fresh-ink");
    c.lineWidth = u(1.5);
    for (const p of coast) c.stroke(p);
    // North arrow, top left, with its name to the right of it: on the Peutinger map it points to the right.
    const { r, cx, cy } = northArrow();
    c.save();
    c.translate(cx, cy);
    c.rotate((spec.fit.north_deg * Math.PI) / 180);
    c.fillStyle = env.color("--ink");
    c.fill(shape([[0, -r], [r * 0.42, r * 0.55], [0, r * 0.25], [-r * 0.42, r * 0.55]]));
    c.restore();
    env.label(c, L.north, cx + r + u(6), cy + u(4), { align: "left", size: 11, weight: 700 });
    env.label(c, L.osm, u(8), H - u(8), { align: "left", ...CREDIT });
  }

  // Today's Dead Sea shore over the old map: dashed, on a paper halo so it reads on the ink of the scan.
  function drawShore(c) {
    c.lineJoin = "round";
    for (const [width, color, dash] of [[5, "--paper", []], [2, "--accent", [7, 4]]]) {
      c.setLineDash(dash.map(u));
      c.lineWidth = u(width);
      c.strokeStyle = env.color(color);
      for (const ring of spec.sea) c.stroke(polyline(new Path2D(), ring, true));
    }
    c.setLineDash([]);
  }

  // Ring (printed place), line, dot (real place) and a label with the distance; over both sides of the swipe.
  function drawPlaces(c) {
    const m = u(14);
    const marks = spec.places.map((place) => ({ place, ...clipToBox(place.map, place.true, W, H, m) }));
    for (const { place, point: [tx, ty], inside } of marks) {
      const [mx, my] = place.map;
      c.lineWidth = u(4);
      c.strokeStyle = env.color("--paper");
      c.beginPath(); c.moveTo(mx, my); c.lineTo(tx, ty); c.stroke();
      c.lineWidth = u(1.5);
      c.strokeStyle = env.color("--accent");
      c.setLineDash(place.fitted ? [] : [u(4), u(3)]);
      c.stroke();
      c.setLineDash([]);
      for (const [width, color] of [[u(4.5), "--paper"], [u(2), "--accent"]]) {
        c.lineWidth = width; c.strokeStyle = env.color(color);
        c.beginPath(); c.arc(mx, my, u(6), 0, Math.PI * 2); c.stroke();
      }
      c.fillStyle = env.color("--accent");
      if (inside) {
        c.beginPath(); c.arc(tx, ty, u(4), 0, Math.PI * 2); c.fill();
      } else { // The real place lies outside the frame: an arrow head at the edge points to it.
        const a = Math.atan2(ty - my, tx - mx);
        c.save(); c.translate(tx, ty); c.rotate(a);
        c.fill(shape([[u(2), 0], [-u(9), -u(5.5)], [-u(9), u(5.5)]]));
        c.restore();
      }
    }
    // Labels next to the real places, without overlaps: each takes the first free spot around its dot (below, above,
    // to the side), first with its distance, then without it. On a small screen a label that finds no spot is left
    // out; the ring, the line and the dot stay. A map that is not to scale has no distances (km is null).
    const NAME = { size: 12, weight: 700 }, KM = { size: 11, weight: 600, color: "--accent" };
    const { r, cx, cy } = northArrow();
    const taken = [
      ...marks.flatMap(({ place: { map: [mx, my] }, point: [tx, ty] }) =>
        [[mx - u(8), my - u(8), u(16), u(16)], [tx - u(5), ty - u(5), u(10), u(10)]]),
      [cx - r, cy - r, 2 * r + u(40), 2 * r], // The north arrow and its name.
      [0, H - u(22), env.textWidth(c, L.osm, CREDIT) + u(16), u(22)], // The credit.
    ];
    const free = ([x, y, w, h]) => x >= u(2) && y >= u(2) && x + w <= W - u(2) && y + h <= H - u(2)
      && taken.every(([a, b, cw, ch]) => x >= a + cw || a >= x + w || y >= b + ch || b >= y + h);
    for (const { place, point: [tx, ty] } of marks) {
      const km = place.km === null ? "" : `${number(place.km, place.km < 10 ? 1 : 0)} ק"מ`;
      const gap = u(4), h = u(15);
      for (const withKm of km ? [true, false] : [false]) {
        const wn = env.textWidth(c, place.name, NAME), wk = withKm ? env.textWidth(c, km, KM) + gap : 0, w = wn + wk;
        const spots = [[tx - w / 2, ty + u(7)], [tx - w / 2, ty - u(7) - h], [tx + u(8), ty - h / 2], [tx - u(8) - w, ty - h / 2]];
        const spot = spots.map(([x, y]) => [x, y, w, h]).find(free);
        if (!spot) continue;
        taken.push(spot);
        const [x, y] = spot, base = y + h - u(4);
        env.label(c, place.name, x + w, base, { ...NAME, align: "right" }); // Hebrew: the name on the right.
        if (withKm) env.label(c, km, x, base, { ...KM, align: "left" });
        break;
      }
    }
  }

  let ready = false;
  function draw(ctx, value, env) {
    if (!ready) {
      if (!img.complete || !img.naturalWidth) {
        env.wantsFrame = true; // Draw again next frame, until the printed image is in.
        ctx.fillStyle = env.color("--xp-land");
        ctx.fillRect(0, 0, W, H);
        return spec.texts.old;
      }
      if (Math.abs(img.naturalWidth / img.naturalHeight - W / H) > 0.01) {
        throw new Error(`old-map ${spec.figure}: ${spec.image} is ${img.naturalWidth}x${img.naturalHeight}, the view ${W}x${H}`);
      }
      ready = true;
    }
    const x = (W * value) / 100;
    const view = [0, 0, W, H];
    ctx.save();
    ctx.beginPath(); ctx.rect(x, 0, W - x, H); ctx.clip();
    ctx.drawImage(img, 0, 0, W, H);
    ctx.drawImage(env.layer("old-map-shore", view, drawShore), 0, 0, W, H);
    ctx.restore();
    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, x, H); ctx.clip();
    ctx.drawImage(env.layer("old-map-today", view, drawToday), 0, 0, W, H);
    ctx.restore();
    ctx.drawImage(env.layer("old-map-places", view, drawPlaces), 0, 0, W, H);
    // The swipe line, with the name of each side next to it when there is room.
    ctx.fillStyle = env.color("--paper");
    ctx.fillRect(x - u(2.5), 0, u(5), H);
    ctx.fillStyle = env.color("--ink");
    ctx.fillRect(x - u(1), 0, u(2), H);
    const gap = u(10), top = u(18);
    if (x > u(70)) env.label(ctx, L.now, x - gap, top, { align: "right", size: 12, weight: 700 });
    if (W - x > u(110)) env.label(ctx, L.old, x + gap, top, { align: "left", size: 12, weight: 700 });
    return value < 50 ? spec.texts.old : spec.texts.fit;
  }

  return {
    draw,
    handle: (value) => [(W * value) / 100, H / 2],
    drag: (point) => clamp((point.x / W) * 100, 0, 100),
  };
}

return { valueParts, create };
})();
