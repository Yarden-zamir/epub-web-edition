// The Dead Sea transform (figure fig-a18-05). A schematic map after the printed figure, north up: the fault runs
// north-north-east; at its south end the Gulf of Suez branches off to the north-west, with Africa beyond it. The
// Sinai–Israel subplate stays still and the Arabia–Jordan plate slides north along the fault. The fault steps to the
// left (west) three times; at each step the plates move apart and a basin opens. The control value is the slip in km.
explorableKit.kinds.transform = (() => {
const { number, iso, ramp, shape } = explorableKit;

const W = 360, H = 600;
// Shapes are drawn in a frame along the fault (x across it, y down along it), turned by TILT about the middle.
const TILT = (20 * Math.PI) / 180, COS = Math.cos(TILT), SIN = Math.sin(TILT), MX = W / 2, MY = H / 2;
const P = (x, y) => [MX + (x - MX) * COS - (y - MY) * SIN, MY + (x - MX) * SIN + (y - MY) * COS];
const turned = (c) => { c.translate(MX, MY); c.rotate(TILT); c.translate(-MX, -MY); };
const TOP_KM = 450, S = 0.84; // Drawing units per km along the fault.
const Y = (km) => 20 + (TOP_KM - km) * S;
const STEP = 6; // Length of each oblique step, km.
// Fault segments from south to north: x across the fault, and the km where the step to the next one starts. South
// of the first step the fault is the Arabian shore of the Red Sea. Basins open at the steps: the Gulf of Eilat (sea),
// the Dead Sea and the Kinneret (lakes).
const SEGMENTS = [[220, -105], [202, 175], [184, 330], [166, Infinity]];
const LAKES = [1, 2]; // Steps whose basins hold a lake; the first holds the sea.
// Coasts (schematic, after the printed figure): the Gulf of Suez leaves the south tip of Sinai SUEZ off the fault,
// 14 units wide at its mouth and 6 at its head; the Mediterranean shore runs from its head 12 degrees off the fault.
const along = (p, d, t) => [p[0] + d[0] * t, p[1] + d[1] * t];
const SUEZ = (34 * Math.PI) / 180, SUEZ_DIR = [-Math.sin(SUEZ), -Math.cos(SUEZ)], SUEZ_ACROSS = [-Math.cos(SUEZ), Math.sin(SUEZ)];
const TIP = [SEGMENTS[1][0], Y(SEGMENTS[0][1] + STEP)]; // South tip of Sinai, at the mouth of the Gulf of Eilat.
const HEAD = along(TIP, SUEZ_DIR, 250); // Head of the Gulf of Suez, on the Mediterranean shore.
const SHORE = [Math.sin(0.21), -Math.cos(0.21)];
const CROSS = [SEGMENTS[3][0], HEAD[1] + SHORE[1] * ((SEGMENTS[3][0] - HEAD[0]) / SHORE[0])]; // Shore meets fault.
const AFRICA_HEAD = along(HEAD, SUEZ_ACROSS, 6), AFRICA_MOUTH = along(TIP, SUEZ_ACROSS, 14);
const RED_SEA_DIR = [-0.349, 0.937]; // Africa's Red Sea shore, south of the Gulf of Suez.
// The copper ore body before the slip (a18-p021): one field across the fault where Timna is, the larger part to the
// east (Feinan holds about a hundred times the slag of Timna, a18-p022). Points around it, relative to the fault.
const ORE_KM = 25;
const ORE = [[-9, -6], [-11, 1], [-7, 8], [0, 10], [10, 14], [24, 13], [36, 7], [41, -2], [34, -11], [19, -15], [6, -12], [0, -9]];
const EILAT_KM = 0;

// Fault trace as points in the fault frame, from far south to far north.
function trace(south, north) {
  const pts = [[SEGMENTS[0][0], south]];
  SEGMENTS.slice(0, -1).forEach(([x, stepKm], i) => pts.push([x, Y(stepKm)], [SEGMENTS[i + 1][0], Y(stepKm + STEP)]));
  pts.push([SEGMENTS.at(-1)[0], north]);
  return pts;
}
const faultX = (km) => SEGMENTS.find(([, stepKm]) => km < stepKm)[0];

function valueParts(km, spec) {
  return { num: number(km), unit: `${spec.control.unit} צפונה`, note: "" };
}

function create(spec, env) {
  const L = spec.labels;
  const t = spec.texts;
  const { max } = spec.control;
  const fault = trace(1000, -500);
  const westEdge = [...fault.slice(2, -1), CROSS]; // From the tip of Sinai north to the shore.
  const sinai = shape([TIP, ...westEdge.slice(1), HEAD]);
  const africa = shape([AFRICA_HEAD, AFRICA_MOUTH, along(AFRICA_MOUTH, RED_SEA_DIR, 700), [-500, 1000], [-500, AFRICA_HEAD[1] + 50]]);
  const east = shape([[700, -500], ...[...fault].reverse(), [700, 1000]]);
  const ore = shape(ORE.map(([dx, dy]) => [faultX(ORE_KM) + dx, Y(ORE_KM) + dy]));
  const arrowUp = shape([[0, -24], [-9, -10], [-3, -10], [-3, 24], [3, 24], [3, -10], [9, -10]]);
  const ripples = new Path2D();
  for (let y = -20; y < H + 40; y += 9) { // Wavelets across the basins' band.
    ripples.moveTo(150, y);
    for (let x = 150; x < 240; x += 10) ripples.quadraticCurveTo(x + 2.5, y - 1.6, x + 5, y), ripples.quadraticCurveTo(x + 7.5, y + 1.6, x + 10, y);
  }
  const list = new Intl.ListFormat("he", { type: "conjunction" });
  const EAST_BOX = [-60, -60, W + 120, H + 200];
  const HANDLE = [310, Y(EILAT_KM)];
  let dots = null, dotsColor = "";

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
  function land(c, path, top, bottom, key) {
    c.fillStyle = env.gradient(key, 0, 0, 0, H, [[0, top], [1, bottom]]);
    c.fill(path);
    c.fillStyle = texture(c);
    c.fill(path);
  }
  function copper(c, clip) {
    c.save();
    c.clip(clip);
    c.fillStyle = env.color("--xp-copper");
    c.fill(ore);
    c.strokeStyle = env.color("--xp-copper-edge");
    c.lineWidth = 1;
    c.stroke(ore);
    c.restore();
  }
  function arrow(c, x, y, dir) { // A plate's direction of motion; dir: a unit vector in the fault frame.
    c.save();
    c.translate(x, y);
    c.rotate(Math.atan2(dir[0], -dir[1]));
    c.fillStyle = env.color("--ink");
    c.fill(arrowUp);
    c.restore();
  }
  function lines(c, text, [x, y]) { // A plate name, broken after its dash.
    text.split("–").forEach((part, i, all) => env.label(c, i < all.length - 1 ? `${part}–` : part, x, y + i * 17 * env.unit));
  }
  const at = (x, y, dy = 0) => { const [px, py] = P(x, y); return [px, py + dy]; };

  function draw(ctx, km, env) {
    const k = km * S, dx = SIN * k, dy = -COS * k; // The east plate's shift on screen.
    ctx.drawImage(env.layer("water", [0, 0, W, H], (c) => {
      c.fillStyle = env.gradient("sea", 0, 0, W, 0, [[0, "--xp-basin-light"], [1, "--xp-basin"]]);
      c.fillRect(0, 0, W, H);
      turned(c);
      for (const i of LAKES) { // Lake water in the band each basin opens into, deepest in its middle.
        const [x0, stepKm] = SEGMENTS[i], x1 = SEGMENTS[i + 1][0];
        c.fillStyle = env.gradient(`lake-${i}`, x1, 0, x0, 0, [[0, "--xp-lake"], [0.5, "--xp-lake-deep"], [1, "--xp-lake"]]);
        c.fillRect(x1, Y(stepKm + STEP + max + 2), x0 - x1, Y(stepKm) - Y(stepKm + STEP + max + 2));
      }
    }), 0, 0, W, H);
    const rippleBox = [140, -30, 110, H + 80];
    const rippleLayer = env.layer("ripples", rippleBox, (c) => {
      c.strokeStyle = "rgb(255 255 255 / 0.18)";
      c.lineWidth = 0.8;
      c.stroke(ripples);
    });
    ctx.save();
    turned(ctx);
    ctx.drawImage(rippleLayer, rippleBox[0], rippleBox[1] - ((env.time * 2.5) % 9), rippleBox[2], rippleBox[3]); // Drift.
    ctx.restore();

    ctx.drawImage(env.layer("land", [0, 0, W, H], (c) => {
      c.save();
      turned(c);
      land(c, africa, "--xp-plate-a-deep", "--xp-plate-b-deep", "africa");
      land(c, sinai, "--xp-plate-a", "--xp-plate-a-deep", "sinai");
      copper(c, sinai);
      c.strokeStyle = env.color("--xp-land-edge");
      c.lineWidth = 0.8;
      c.stroke(africa);
      c.stroke(shape([HEAD, TIP], false));
      c.stroke(shape([HEAD, CROSS], false));
      c.strokeStyle = env.color("--ink");
      c.lineWidth = 1.5;
      c.lineJoin = "round";
      c.stroke(shape(westEdge, false));
      arrow(c, 118, 520, SUEZ_ACROSS);
      c.restore();
      env.label(c, L.mediterranean, 8, 150, { align: "left", size: 12, weight: 500, color: "--muted" });
      env.label(c, L.africa, ...at(110, 470));
      env.label(c, L.red_sea, ...at(192, 572), { size: 12, weight: 500 });
      // The Gulf of Suez's name stays horizontal, on the gulf near its mouth: turned along the gulf, it read as
      // mirrored on a phone.
      env.label(c, L.suez, ...at(...along(TIP, SUEZ_DIR, 30), 4), { size: 12, weight: 500 });
      lines(c, L.west_plate, at(124, Y(112)));
      env.label(c, `↑ ${L.north}`, W - 10, 4 + 12 * env.unit, { align: "right", size: 12, weight: 500, color: "--muted" });
    }), 0, 0, W, H);

    ctx.drawImage(env.layer("east", EAST_BOX, (c) => {
      c.save();
      turned(c);
      c.lineJoin = "round";
      c.save();
      c.translate(3, 0);
      c.strokeStyle = env.color("--xp-shadow");
      c.lineWidth = 6;
      c.stroke(shape(fault, false));
      c.restore();
      land(c, east, "--xp-plate-b", "--xp-plate-b-deep", "east");
      copper(c, east);
      c.strokeStyle = env.color("--ink");
      c.lineWidth = 1.5;
      c.stroke(shape(fault, false));
      arrow(c, HANDLE[0], HANDLE[1] - 56, [0, -1]);
      c.restore();
      lines(c, L.east_plate, at(288, Y(165)));
      env.label(c, L.feinan, ...at(faultX(ORE_KM) + 46, Y(ORE_KM), 4), { align: "left" });
    }), EAST_BOX[0] + dx, EAST_BOX[1] + dy, EAST_BOX[2], EAST_BOX[3]);

    // The open basins: steep walls (hachures on both sides, pointing down into the basin) and their names.
    const opened = km - STEP;
    const names = [];
    ctx.save();
    turned(ctx);
    ctx.strokeStyle = env.color("--ink");
    ctx.globalAlpha = 0.55;
    ctx.lineWidth = 0.9;
    const walls = new Path2D();
    SEGMENTS.slice(0, -1).forEach(([x0, stepKm], i) => {
      if (opened <= 0) return;
      const x1 = SEGMENTS[i + 1][0];
      for (let y = Y(stepKm + STEP) - 2; y > Y(stepKm + km) + 2; y -= 4) {
        walls.moveTo(x1, y); walls.lineTo(x1 + 3.5, y - 1.2);
        walls.moveTo(x0, y); walls.lineTo(x0 - 3.5, y - 1.2);
      }
    });
    ctx.stroke(walls);
    ctx.restore();
    const shown = ramp(opened, 6, 20);
    if (shown > 0.01) {
      ctx.globalAlpha = shown;
      SEGMENTS.slice(0, -1).forEach(([x0, stepKm], i) => {
        const mid = Y(stepKm + STEP + opened / 2);
        // The Gulf's name sits east of it (Sinai is narrow there), the lakes' names west of them.
        if (i === 0) env.label(ctx, L.basins[i], ...at(x0 + 6, mid, 4), { align: "left" });
        else env.label(ctx, L.basins[i], ...at(SEGMENTS[i + 1][0] - 6, mid, 4), { align: "right" });
        names.push(L.basins[i]);
      });
      ctx.globalAlpha = 1;
    }

    // Timna, Eilat and the offset between the two parts of the copper field: a gauge west of the fault.
    const [ex, ey] = P(faultX(EILAT_KM) - 4, Y(EILAT_KM));
    ctx.fillStyle = env.color("--ink");
    ctx.beginPath(); ctx.arc(ex, ey, 3.2, 0, Math.PI * 2); ctx.fill();
    if (env.unit <= 1.3) env.label(ctx, L.eilat, ex - 8, ey + 4, { align: "right" });
    env.label(ctx, L.timna, ...at(faultX(ORE_KM) - 34, Y(ORE_KM), 4), { align: "right" });
    const gauge = ramp(km, 4, 12);
    if (gauge > 0.01) {
      const gx = faultX(ORE_KM) - 26, y0 = Y(ORE_KM), y1 = Y(ORE_KM) - k;
      ctx.save();
      turned(ctx);
      ctx.globalAlpha = gauge;
      ctx.strokeStyle = env.color("--xp-copper-edge");
      ctx.lineWidth = 1.2;
      ctx.stroke(shape([[faultX(ORE_KM) - 12, y0], [gx - 4, y0]], false));
      ctx.stroke(shape([[faultX(ORE_KM) + 2, y1], [gx - 4, y1]], false));
      ctx.setLineDash([3, 3]);
      ctx.stroke(shape([[gx, y0], [gx, y1]], false));
      ctx.restore();
      if (km >= 20) {
        ctx.globalAlpha = ramp(km, 20, 30);
        const [lx, ly] = P(gx - 6, (y0 + y1) / 2);
        env.label(ctx, `${number(Math.round(km))} ${spec.control.unit}`, lx, ly + 4, { align: "right", weight: 700, color: "--xp-copper-edge" });
      }
      ctx.globalAlpha = 1;
    }

    // Once the basins are open: what a left step does, on the empty Arabian land in the south-east, with a pointer to
    // the Gulf of Eilat (the nearest basin; the labels further north leave no room on phones).
    const explain = ramp(opened, 25, 45);
    if (explain > 0.01) {
      const rows = L.explain.split(" / "), size = env.unit > 1.3 ? 11 : 12, gap = (size + 4) * env.unit;
      const [x0, stepKm] = SEGMENTS[0], x1 = SEGMENTS[1][0];
      const [bx, by] = P((x0 + x1) / 2 + 3, Y(stepKm + STEP + opened * 0.35));
      const lx = W - 92, ly = H - 34 - (rows.length - 1) * gap;
      ctx.globalAlpha = explain;
      ctx.strokeStyle = env.color("--ink");
      ctx.lineWidth = 1;
      ctx.stroke(shape([[lx - 30, ly - gap], [bx + 6, by + 2]], false));
      rows.forEach((row, i) => env.label(ctx, row, lx, ly + i * gap, { weight: 700, size }));
      ctx.globalAlpha = 1;
    }

    const whole = Math.round(km);
    if (whole === 0) return t.before;
    const apart = t.apart.replace("{km}", iso(number(whole)));
    if (whole === spec.slip_km) return `${t.today} ${apart}`;
    return `${t.moving}${names.length && opened > 0 ? `: ${list.format(names)}.` : "."} ${apart}`;
  }

  return {
    draw,
    handle: (km) => P(HANDLE[0], HANDLE[1] - km * S),
    // The plate moves along the fault: the pointer's movement along the fault's direction on screen.
    drag: (point, start) => start.value + ((point.x - start.point.x) * SIN - (point.y - start.point.y) * COS) / S,
  };
}
return { view: [0, 0, W, H], animated: true, valueParts, create };
})();
