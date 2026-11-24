// Mount Sodom rises (figure fig-a34-17). A schematic west-east section after the printed figure: salt flows
// from the layer under the rift, up the marginal fault, into a column of upturned layers. The control is the
// rise of the salt in metres. Up to the Lake Lisan rise (lisan_rise_m[1]) the salt dissolves at a flat salt
// mirror under the lake and only the cap rock grows (insoluble_fraction of the dissolved salt). After that the
// lake is dry, and the layers rise since_lisan_m, the centre faster than the flanks, so the mirror breaks.
explorableKit.kinds.diapir = (() => {
const { number, iso, ramp, shape } = explorableKit;

const W = 600, H = 360, TOP = -70; // The drawing starts above y 0: room for the risen mountain.
const MIRROR = 112; // Drawing y of the salt mirror: the floor of Lake Lisan around the mountain.
const CAP_SCALE = 0.9; // Drawing units per metre of cap rock.
const RISE_SCALE = 1.1; // Drawing units per metre of rise after the lake.
const COLUMN = { x: 252, width: 96, bottom: 440 };
const FACTORS = [0.6, 0.78, 0.92, 1, 0.9, 0.74, 0.58]; // Share of the full rise per layer, west to east (schematic).
const RIGHT = COLUMN.x + COLUMN.width;

function valueParts(rise, spec) {
  return { num: number(rise), unit: spec.control.unit, note: rise <= spec.lisan_rise_m[1] ? spec.labels.phase_lake : spec.labels.phase_dry };
}

function create(spec) {
  const L = spec.labels;
  const t = spec.texts;
  const lakeRise = spec.lisan_rise_m[1];
  const { max } = spec.control;
  const strip = COLUMN.width / FACTORS.length;
  const westBlock = shape([[0, MIRROR], [COLUMN.x, MIRROR], [COLUMN.x, H], [0, H]]);
  const eastBlock = shape([[RIGHT, 138], [W, 138], [W, H], [RIGHT, H]]);
  const strata = new Path2D();
  for (const [x0, x1, y0] of [[0, COLUMN.x, MIRROR], [RIGHT, W, 138]])
    for (let i = 1; i <= 4; i++) { strata.moveTo(x0, y0 + i * 22); strata.lineTo(x1, y0 + i * 22); }
  const westSalt = shape([[0, 212], [170, 212], [170, 228], [0, 228]]);
  const eastSalt = new Path2D(`M${RIGHT} 250 C 370 262, 380 285, 400 290 H${W} V346 H400 C 370 346, 350 320, ${RIGHT} 300 Z`);
  const beds = new Path2D();
  for (const y of [302, 314, 326, 338]) { beds.moveTo(400, y); beds.lineTo(W, y); }
  const flow = new Path2D("M392 318 C 378 300, 368 285, 358 270 M356 282 L357 268 L370 274");
  const creep = new Path2D(`M${W} 318 H405 C 380 318, 360 300, ${RIGHT - 8} 280 V180`);

  function draw(ctx, rise, env) {
    const dissolved = Math.min(rise, lakeRise);
    const after = Math.max(0, rise - lakeRise);
    const capM = dissolved * spec.insoluble_fraction;
    const capH = capM * CAP_SCALE;
    const drain = ramp(rise, lakeRise - 4, lakeRise + 12); // The lake drains as the rise passes Lake Lisan's end.

    ctx.fillStyle = env.gradient("sky", 0, TOP, 0, H, [[0, "--xp-sky-top"], [1, "--xp-sky"]]);
    ctx.fillRect(0, TOP, W, H - TOP);
    if (drain < 0.99) {
      const surface = TOP + 10 + drain * 90;
      ctx.globalAlpha = 1 - drain;
      ctx.fillStyle = env.gradient("lake", 0, TOP, 0, 140, [[0, "--xp-fresh"], [1, "--xp-fresh-deep"]]);
      ctx.fillRect(0, surface, W, H - surface);
      ctx.strokeStyle = env.color("--xp-surface");
      ctx.lineWidth = 2;
      ctx.stroke(shape([[0, surface], [W, surface]], false));
      ctx.lineWidth = 1.5;
      ctx.lineCap = "round";
      ctx.globalAlpha = (1 - drain) * 0.55;
      for (let i = 0; i < 7; i++) { // Glints drift slowly across the lake.
        const x = ((i * 89 + env.time * 7) % (W + 20)) - 10, y = surface + 8 + ((i * 13) % 30);
        ctx.stroke(shape([[x - 7, y], [x + 7, y]], false));
      }
      ctx.lineCap = "butt";
      ctx.globalAlpha = 1 - drain;
      ctx.globalAlpha = 1 - ramp(rise, lakeRise - 30, lakeRise);
      env.label(ctx, L.lake, 470, surface + 36);
      ctx.globalAlpha = 1;
    }

    let top = MIRROR;
    FACTORS.forEach((f, i) => {
      const lift = after * RISE_SCALE * f;
      const x = COLUMN.x + i * strip;
      ctx.fillStyle = env.gradient(`layer${i % 2}`, COLUMN.x, 0, RIGHT, 0, i % 2
        ? [[0, "--xp-salt-shade"], [1, "--xp-salt"]] : [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
      ctx.fillRect(x, MIRROR - lift, strip, COLUMN.bottom - MIRROR);
      ctx.strokeStyle = env.color("--xp-salt-edge");
      ctx.lineWidth = 0.8;
      ctx.strokeRect(x, MIRROR - lift, strip, COLUMN.bottom - MIRROR);
      if (capH > 0.05) {
        ctx.fillStyle = env.gradient("cap", 0, MIRROR - 40, 0, MIRROR, [[0, "--xp-cap"], [1, "--xp-land-edge"]]);
        ctx.fillRect(x, MIRROR - lift - capH, strip, capH);
      }
      top = Math.min(top, MIRROR - capH - lift);
    });

    ctx.fillStyle = env.gradient("land", 0, MIRROR, 0, H, [[0, "--xp-land"], [1, "--xp-land-deep"]]);
    ctx.fill(westBlock);
    ctx.fill(eastBlock);
    ctx.strokeStyle = env.color("--xp-land-edge");
    ctx.lineWidth = 1.2;
    ctx.stroke(westBlock);
    ctx.stroke(eastBlock);
    ctx.globalAlpha = 0.18;
    ctx.lineWidth = 1;
    ctx.stroke(strata);
    ctx.globalAlpha = 1;
    ctx.fillStyle = env.gradient("salt", 0, 0, W, 0, [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
    ctx.fill(westSalt);
    ctx.fill(eastSalt);
    ctx.strokeStyle = env.color("--xp-salt-edge");
    ctx.stroke(westSalt);
    ctx.stroke(eastSalt);
    ctx.globalAlpha = 0.6;
    ctx.stroke(beds);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = env.color("--ink");
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke(flow);
    // Salt creeps up the neck: a dashed line that moves slowly toward the mountain.
    ctx.strokeStyle = env.color("--xp-salt-edge");
    ctx.lineWidth = 1.2;
    ctx.setLineDash([4, 6]);
    ctx.lineDashOffset = env.time * 5;
    ctx.stroke(creep);
    ctx.setLineDash([]);
    ctx.lineDashOffset = 0;
    ctx.lineCap = "butt";

    if (drain < 0.99) {
      ctx.globalAlpha = 1 - drain;
      ctx.strokeStyle = env.color("--xp-fresh-ink");
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 4]);
      ctx.stroke(shape([[COLUMN.x - 30, MIRROR], [RIGHT + 30, MIRROR]], false));
      ctx.setLineDash([]);
      env.label(ctx, L.mirror, COLUMN.x - 34, MIRROR + 4, { align: "right" });
      ctx.globalAlpha = 1;
    }
    const small = env.unit > 1.3;
    env.label(ctx, L.west, 6, H - 8, { align: "left", size: 12, weight: 500, color: "--muted" });
    env.label(ctx, L.east, W - 6, H - 8, { align: "right", size: 12, weight: 500, color: "--muted" });
    env.label(ctx, L.amiaz, 120, MIRROR - 8);
    env.label(ctx, L.rift, 480, 130);
    if (!small) { env.label(ctx, L.sand, 120, 175); env.label(ctx, L.sand, 480, 215); }
    env.label(ctx, L.salt, 85, 246);
    env.label(ctx, L.salt, 500, 278);
    const capAlpha = ramp(capM, 6, 12);
    if (capAlpha > 0.01) {
      ctx.globalAlpha = capAlpha;
      env.label(ctx, L.cap, RIGHT + 8, MIRROR - capH / 2 + 4 - after * RISE_SCALE * FACTORS.at(-1), { align: "left" });
      ctx.globalAlpha = 1;
    }
    env.label(ctx, L.sodom, COLUMN.x + COLUMN.width / 2, top - 10);

    const shown = Math.round(rise / 5) * 5;
    if (shown === 0) return t.start;
    if (shown <= lakeRise) return `${t.lake} ${t.cap.replace("{rise}", iso(number(shown))).replace("{cap}", iso(number(Math.round(shown * spec.insoluble_fraction))))}`;
    const rest = shown - lakeRise;
    const years = Math.round((rest / spec.since_lisan_m) * spec.since_lisan_years / 100) * 100;
    const text = t.dry.replace("{rise}", iso(number(rest))).replace("{years}", iso(number(years)));
    return shown === max ? `${text} ${t.today}` : text;
  }

  // The handle sits on the salt column, below its top.
  const topAt = (rise) => MIRROR - Math.min(rise, lakeRise) * spec.insoluble_fraction * CAP_SCALE - Math.max(0, rise - lakeRise) * RISE_SCALE;
  return {
    draw,
    handle: (rise) => [COLUMN.x + COLUMN.width / 2, topAt(rise) + 58],
    // 200 drawing units of drag cover the whole range.
    drag: (point, start) => start.value + ((start.point.y - point.y) * max) / 200,
  };
}
return { view: [0, TOP, W, H - TOP], animated: true, valueParts, create };
})();
