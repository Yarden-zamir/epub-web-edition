// The Dead Sea transform (figure fig-a18-05). A schematic map, north up: the west block (Sinai–Israel)
// stays still and the east block (Arabia–Jordan) slides north along the fault. The fault steps to the
// left (west) three times; at each step the blocks move apart and a basin opens: the sea colour lies behind
// both blocks and shows through the gap. The control value is the slip in km.
explorableKit.kinds.transform = (() => {
const { number, iso, ramp, shape } = explorableKit;

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
const faultX = (km) => SEGMENTS.find(([, stepKm]) => km < stepKm)[0];

function valueParts(km, spec) {
  return { num: number(km), unit: `${spec.control.unit} צפונה`, note: "" };
}

function create(spec) {
  const L = spec.labels;
  const t = spec.texts;
  const { max } = spec.control;
  const extra = max * S + 20; // The east block reaches below the frame, so moving it north leaves no hole.
  const fault = trace(-20, H + extra);
  const westShape = shape([[0, -20], ...fault.slice(0, -1), [fault.at(-1)[0], H + 20], [0, H + 20]]);
  const eastShape = shape([[W, -20], ...fault, [W, H + extra]]);
  const faultLine = shape(fault, false);
  const ripples = new Path2D();
  for (let y = 40; y < H; y += 26) { // Texture in the basins only.
    ripples.moveTo(108, y);
    for (let x = 108; x < 248; x += 12) ripples.quadraticCurveTo(x + 3, y - 3, x + 6, y), ripples.quadraticCurveTo(x + 9, y + 3, x + 12, y);
  }
  const arrow = shape([[290, Y(150)], [281, Y(150) + 14], [287, Y(150) + 14], [287, Y(150) + 48], [293, Y(150) + 48], [293, Y(150) + 14], [299, Y(150) + 14]]);
  const copper = new Path2D();
  copper.ellipse(COPPER.x, Y(COPPER.km), COPPER.rx, COPPER.ry, 0, 0, Math.PI * 2);
  const list = new Intl.ListFormat("he", { type: "conjunction" });
  let dots = null, dotsColor = "";

  function texture(ctx, env) {
    // A small dot pattern for the rock, made once per theme.
    const color = env.color("--xp-dot");
    if (color !== dotsColor) {
      const tile = document.createElement("canvas");
      tile.width = tile.height = 9;
      const tc = tile.getContext("2d");
      tc.fillStyle = color;
      tc.beginPath(); tc.arc(2, 2, 0.9, 0, Math.PI * 2); tc.arc(6.5, 6.5, 0.7, 0, Math.PI * 2); tc.fill();
      dots = ctx.createPattern(tile, "repeat");
      dotsColor = color;
    }
    return dots;
  }
  function plate(ctx, env, path, key, top, bottom) {
    ctx.fillStyle = env.gradient(key, 0, 0, 0, H, [[0, top], [1, bottom]]);
    ctx.fill(path);
    ctx.fillStyle = texture(ctx, env);
    ctx.fill(path);
  }
  function ore(ctx, env, clip) {
    ctx.save();
    ctx.clip(clip);
    ctx.fillStyle = env.color("--xp-copper");
    ctx.fill(copper);
    ctx.strokeStyle = env.color("--xp-copper-edge");
    ctx.lineWidth = 1;
    ctx.stroke(copper);
    ctx.restore();
  }
  function lines(ctx, env, text, x, y) {
    text.split("–").forEach((part, i, all) => env.label(ctx, i < all.length - 1 ? `${part}–` : part, x, y + i * 17));
  }

  function draw(ctx, km, env) {
    const u = env.unit;
    ctx.fillStyle = env.gradient("sea", 0, 0, W, 0, [[0, "--xp-basin-light"], [1, "--xp-basin"]]);
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "rgb(255 255 255 / 0.16)";
    ctx.lineWidth = 1;
    ctx.save();
    ctx.translate((env.time * 3) % 12 - 12, Math.sin(env.time * 0.8) * 2); // Ripples drift slowly in the basins.
    ctx.stroke(ripples);
    ctx.restore();
    plate(ctx, env, westShape, "west", "--xp-plate-a", "--xp-plate-a-deep");
    ore(ctx, env, westShape);
    ctx.lineJoin = "round";

    ctx.save();
    ctx.translate(0, -km * S);
    ctx.save();
    ctx.translate(3, 0);
    ctx.strokeStyle = env.color("--xp-shadow");
    ctx.lineWidth = 6;
    ctx.stroke(faultLine);
    ctx.restore();
    plate(ctx, env, eastShape, "east", "--xp-plate-b", "--xp-plate-b-deep");
    ctx.strokeStyle = env.color("--ink");
    ctx.lineWidth = 1.5;
    ctx.stroke(faultLine);
    ore(ctx, env, eastShape);
    ctx.fillStyle = env.color("--ink");
    ctx.fill(arrow);
    lines(ctx, env, L.east_plate, 290, Y(250));
    env.label(ctx, L.feinan, COPPER.x + 30, Y(COPPER.km) + 4, { align: "left" });
    ctx.restore();
    ctx.strokeStyle = env.color("--ink");
    ctx.lineWidth = 1.5;
    ctx.stroke(faultLine);

    lines(ctx, env, L.west_plate, 72, Y(260));
    env.label(ctx, L.timna, COPPER.x - 26, Y(COPPER.km) + 4, { align: "right" });
    ctx.fillStyle = env.color("--ink");
    ctx.beginPath(); ctx.arc(faultX(EILAT_KM) - 5, Y(EILAT_KM), 3.5, 0, Math.PI * 2); ctx.fill();
    if (u <= 1.3) env.label(ctx, L.eilat, faultX(EILAT_KM) - 12, Y(EILAT_KM) + 4, { align: "right" });
    env.label(ctx, `↑ ${L.north}`, 12, 18, { align: "left", size: 12, weight: 500, color: "--muted" });

    // One label per basin, west of it: it follows the basin's middle and fades in as the basin opens.
    const open = [];
    const length = km - STEP;
    SEGMENTS.slice(0, -1).forEach(([, stepKm], i) => {
      const alpha = ramp(length, 6, 20);
      if (alpha > 0.01) {
        ctx.globalAlpha = alpha;
        env.label(ctx, L.basins[i], SEGMENTS[i + 1][0] - 8, Y(stepKm + STEP + Math.max(0, length) / 2) + 4, { align: "right" });
        ctx.globalAlpha = 1;
      }
      if (length > 0) open.push(L.basins[i]);
    });

    const shown = Math.round(km);
    if (shown === 0) return t.before;
    const apart = t.apart.replace("{km}", iso(number(shown)));
    if (shown === spec.slip_km) return `${t.today} ${apart}`;
    return `${t.moving}${open.length ? `: ${list.format(open)}.` : "."} ${apart}`;
  }

  return {
    draw,
    handle: (km) => [290, Y(90) - km * S],
    drag: (point, start) => start.value + (start.point.y - point.y) / S,
  };
}
return { view: [0, 0, W, H], animated: true, valueParts, create };
})();
