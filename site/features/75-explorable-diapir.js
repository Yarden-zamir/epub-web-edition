// Mount Sodom rises (figure fig-a34-17). A schematic west-east section after the printed figure: the rift between its
// marginal faults; salt flows from the deep layer under the rift, the lower layers faster (a34-p047, a34-p048), up the
// western marginal fault into a column of upright layers, which breaks through the Amora formation (a34-p050). The
// control is the rise of the salt in metres. Up to the Lake Lisan rise (lisan_rise_m[1]) the salt dissolves at a flat
// salt mirror under the lake, the centre layers rising faster below it, and the cap rock grows from below with the
// insoluble share (a34-p051). After that the lake is dry: the layers rise since_lisan_m, the centre faster than the
// flanks, carrying the cap rock and Lisan marl; the mirror breaks, rain seeps into the cracks and dissolves caves
// (a34-p053, a34-p039).
explorableKit.kinds.diapir = (() => {
const { number, iso, ramp, shape } = explorableKit;

const W = 600, H = 360, TOP = -70; // The drawing starts above y 0: room for the risen mountain.
const MIRROR = 112; // Drawing y of the salt mirror: the floor of Lake Lisan around the mountain.
const RIFT_FLOOR = 138; // The rift east of the mountain lies lower than the Amiaz plain.
const CAP_SCALE = 0.9; // Drawing units per metre of cap rock.
const RISE_SCALE = 1.1; // Drawing units per metre of rise after the lake.
const COLUMN = { x: 252, width: 96, bottom: 440 };
const LEAN = 0.08; // The upright layers lean east: drawing units east per unit up (schematic, after the print).
const FACTORS = [0.6, 0.78, 0.92, 1, 0.9, 0.74, 0.58]; // Share of the full rise per layer, west to east (schematic).
const RIGHT = COLUMN.x + COLUMN.width;
const COVER_M = 40; // Metres of rise in which the column breaks through the Amora formation (schematic).
const BAND_M = 5; // A band of cap rock for every 5 m of it, so its growth from below shows.

function valueParts(rise, spec) {
  return { num: number(rise), unit: spec.control.unit, note: rise <= spec.lisan_rise_m[1] ? spec.labels.phase_lake : spec.labels.phase_dry };
}

function create(spec) {
  const L = spec.labels;
  const t = spec.texts;
  const lakeRise = spec.lisan_rise_m[1];
  const { max } = spec.control;
  const strip = COLUMN.width / FACTORS.length;
  const lean = (y) => (MIRROR - y) * LEAN; // East shift of a layer at height y, zero at the mirror.
  // Marginal faults of the rift (after the print), dipping toward it; beyond them the shoulders stand higher.
  const WF = [[44, MIRROR - 22], [16, H + 10]], EF = [[556, RIFT_FLOOR - 22], [584, H + 10]];
  const faultX = ([[x0, y0], [x1, y1]], y) => x0 + ((x1 - x0) * (y - y0)) / (y1 - y0);
  const westBlock = shape([[faultX(WF, MIRROR), MIRROR], [COLUMN.x + lean(MIRROR), MIRROR], [COLUMN.x + lean(H + 10), H + 10], [WF[1][0], H + 10]]);
  const eastBlock = shape([[RIGHT + lean(RIFT_FLOOR), RIFT_FLOOR], [faultX(EF, RIFT_FLOOR), RIFT_FLOOR], [EF[1][0], H + 10], [RIGHT + lean(H + 10), H + 10]]);
  const shoulders = [shape([[-10, WF[0][1]], WF[0], WF[1], [-10, H + 10]]), shape([EF[0], [W + 10, EF[0][1]], [W + 10, H + 10], EF[1]])];
  const strata = new Path2D();
  for (const [x0, x1, y0] of [[44, COLUMN.x - 10, MIRROR], [RIGHT + 10, 556, RIFT_FLOOR]])
    for (let i = 1; i <= 4; i++) { strata.moveTo(x0, y0 + i * 22); strata.lineTo(x1, y0 + i * 22); }
  const westSalt = shape([[faultX(WF, 212), 212], [170, 212], [170, 228], [faultX(WF, 228), 228]]);
  const eastSalt = new Path2D(`M${RIGHT - 6} 250 C 370 262, 380 285, 400 290 H${faultX(EF, 290)} L${faultX(EF, 346)} 346 H400 C 370 346, 350 320, ${RIGHT - 8} 300 Z`);
  const beds = new Path2D();
  for (const y of [302, 314, 326, 338]) { beds.moveTo(400, y); beds.lineTo(faultX(EF, y) - 2, y); }
  // Salt flow: from under the rift, west, then up the column. Lower layers move faster (a34-p048).
  const FLOWS = [[338, 9], [322, 6.5], [306, 4.5]].map(([y, speed]) =>
    ({ path: new Path2D(`M${faultX(EF, y) - 4} ${y} H410 C 385 ${y}, ${RIGHT - 10} ${y - 20}, ${RIGHT - 14} ${y - 60} V ${MIRROR + 40}`), speed }));
  const faults = [WF, EF];
  const openArrow = new Path2D("M0 -9 V5 M-5 0 L0 7 L5 0");
  const cave = [[0.42, 0], [0.55, 0.25], [0.48, 0.45], [0.62, 0.62], [0.8, 0.7], [1.06, 0.74]]; // Share of width, depth.

  function slicePath(i, lift) { // One upright layer, lifted, leaning east.
    const x = COLUMN.x + i * strip, y = MIRROR - lift;
    return shape([[x + lean(y), y], [x + strip + lean(y), y], [x + strip + lean(COLUMN.bottom), COLUMN.bottom], [x + lean(COLUMN.bottom), COLUMN.bottom]]);
  }

  function draw(ctx, rise, env) {
    const small = env.unit > 1.3;
    const dissolved = Math.min(rise, lakeRise);
    const after = Math.max(0, rise - lakeRise);
    const capM = dissolved * spec.insoluble_fraction;
    const capH = capM * CAP_SCALE;
    const drain = ramp(rise, lakeRise - 4, lakeRise + 12); // The lake drains as the rise passes Lake Lisan's end.
    const flowing = !reduceMotion.matches;

    const view = [0, TOP, W, H - TOP];
    ctx.drawImage(env.layer("sky", view, (c) => {
      c.fillStyle = env.gradient("sky", 0, TOP, 0, H, [[0, "--xp-sky-top"], [1, "--xp-sky"]]);
      c.fillRect(0, TOP, W, H - TOP);
    }), ...view);
    let surface = TOP;
    if (drain < 0.99) {
      surface = TOP + 10 + drain * 90;
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
      ctx.globalAlpha = 1 - ramp(rise, lakeRise - 30, lakeRise);
      env.label(ctx, L.lake, 470, surface + 36);
      ctx.globalAlpha = 1;
    }

    // The column: each layer lifted by its share after the lake; under the lake every layer ends at the mirror.
    let top = MIRROR;
    const lifts = FACTORS.map((f) => after * RISE_SCALE * f);
    FACTORS.forEach((f, i) => {
      const lift = lifts[i];
      const body = slicePath(i, lift);
      ctx.fillStyle = env.gradient(`layer${i % 2}`, COLUMN.x, 0, RIGHT, 0, i % 2
        ? [[0, "--xp-salt-shade"], [1, "--xp-salt"]] : [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
      ctx.fill(body);
      ctx.strokeStyle = env.color("--xp-salt-edge");
      ctx.lineWidth = 0.8;
      ctx.stroke(body);
      const y = MIRROR - lift, x = COLUMN.x + i * strip + lean(y);
      if (capH > 0.05) { // The cap rock on this layer, banded: a band per BAND_M metres, the youngest at the bottom.
        const capTop = y - capH;
        ctx.fillStyle = env.gradient("cap", 0, MIRROR - 40, 0, MIRROR, [[0, "--xp-cap"], [1, "--xp-land-edge"]]);
        ctx.fill(shape([[x + lean(capTop) - lean(y), capTop], [x + strip + lean(capTop) - lean(y), capTop], [x + strip, y], [x, y]]));
        ctx.strokeStyle = env.color("--xp-land-edge");
        ctx.globalAlpha = 0.5;
        ctx.lineWidth = 0.6;
        for (let b = BAND_M * CAP_SCALE; b < capH - 0.5; b += BAND_M * CAP_SCALE)
          ctx.stroke(shape([[x + lean(capTop + b) - lean(y), capTop + b], [x + strip + lean(capTop + b) - lean(y), capTop + b]], false));
        ctx.globalAlpha = 1;
        if (after > 0) { // Lisan marl, left on the cap rock when the lake dried, rides up with it.
          ctx.fillStyle = env.color("--xp-marl");
          ctx.fillRect(x + lean(capTop) - lean(y), capTop - 3, strip, 3);
        }
      }
      top = Math.min(top, y - capH - (after > 0 ? 3 : 0));
    });

    // The rock around: blocks, strata, the salt layers, and the marginal faults.
    ctx.drawImage(env.layer("frame", view, (c) => {
      c.fillStyle = env.gradient("land", 0, MIRROR, 0, H, [[0, "--xp-land"], [1, "--xp-land-deep"]]);
      c.fill(westBlock);
      c.fill(eastBlock);
      c.fillStyle = env.color("--xp-land-deep");
      for (const shoulder of shoulders) c.fill(shoulder);
      c.strokeStyle = env.color("--xp-land-edge");
      c.lineWidth = 1.2;
      c.stroke(westBlock);
      c.stroke(eastBlock);
      c.globalAlpha = 0.18;
      c.lineWidth = 1;
      c.stroke(strata);
      c.globalAlpha = 1;
      c.fillStyle = env.gradient("salt", 0, 0, W, 0, [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
      c.fill(westSalt);
      c.fill(eastSalt);
      c.strokeStyle = env.color("--xp-salt-edge");
      c.stroke(westSalt);
      c.stroke(eastSalt);
      c.globalAlpha = 0.6;
      c.stroke(beds);
      c.globalAlpha = 1;
      c.strokeStyle = env.color("--ink");
      c.lineWidth = 3;
      c.lineCap = "round";
      for (const [a, b] of faults) c.stroke(shape([a, b], false));
      c.lineWidth = 1.5;
      for (const fault of faults) { // An open arrow on the rift side of each fault: that side went down.
        const y = 182, x = faultX(fault, y) + (fault === WF ? 14 : -14);
        c.save(); c.translate(x, y); c.stroke(openArrow); c.restore();
      }
      env.label(c, L.west, 6, H - 8, { align: "left", size: 12, weight: 500, color: "--muted" });
      env.label(c, L.east, W - 6, H - 8, { align: "right", size: 12, weight: 500, color: "--muted" });
      env.label(c, L.rift, small ? 505 : 480, RIFT_FLOOR - 8);
      if (!small) { env.label(c, L.sand, 130, 175); env.label(c, L.sand, 480, 215); }
      env.label(c, L.salt, 92, 246);
      env.label(c, L.salt, 500, 278);
      env.label(c, L.fault, faultX(WF, H - 40) + 8, H - 40, { align: "left", size: 11, weight: 500 });
    }), ...view);

    // The Amiaz plain's name; on phones above the mirror's name while the lake stands.
    env.label(ctx, L.amiaz, 130, MIRROR - (small && drain < 0.5 ? 26 : 8));

    // Lisan marl on the plains: laid down while the lake stood (thin, at its floor around the mountain).
    const marl = ramp(rise, 20, 120);
    if (marl > 0.01) {
      ctx.globalAlpha = marl;
      ctx.fillStyle = env.color("--xp-marl");
      ctx.fillRect(faultX(WF, MIRROR), MIRROR - 3, COLUMN.x - faultX(WF, MIRROR) + lean(MIRROR), 3);
      ctx.fillRect(RIGHT + lean(RIFT_FLOOR), RIFT_FLOOR - 3, faultX(EF, RIFT_FLOOR) - RIGHT - lean(RIFT_FLOOR), 3);
      ctx.globalAlpha = 1;
    }

    // Salt flows up from under the rift: dashes that move slowly, the lower lines faster.
    ctx.lineCap = "round";
    ctx.strokeStyle = env.color("--xp-salt-edge");
    ctx.lineWidth = 1.2;
    ctx.setLineDash([4, 7]);
    for (const { path, speed } of FLOWS) {
      ctx.lineDashOffset = flowing ? env.time * speed : 0;
      ctx.stroke(path);
    }
    ctx.setLineDash([]);
    ctx.lineDashOffset = 0;
    ctx.lineCap = "butt";

    // The Amora formation over the column: broken through in the first metres of the rise (a34-p050).
    const broken = ramp(rise, 0, COVER_M);
    if (broken < 0.99) {
      ctx.globalAlpha = 1 - broken;
      ctx.fillStyle = env.color("--xp-land-deep");
      ctx.strokeStyle = env.color("--xp-land-edge");
      ctx.lineWidth = 1;
      const mid = COLUMN.x + COLUMN.width / 2, gap = broken * 30, tilt = broken * 0.35;
      for (const side of [-1, 1]) { // Two plates of the cover, pushed apart and tilted as the salt rises through.
        ctx.save();
        ctx.translate(mid + side * gap, MIRROR - 1);
        ctx.rotate(side * -tilt);
        const half = shape(side < 0 ? [[-62, -9], [0, -9], [0, 0], [-62, 0]] : [[0, -9], [62, -9], [62, 0], [0, 0]]);
        ctx.fill(half);
        ctx.stroke(half);
        ctx.restore();
      }
      env.label(ctx, L.amora, mid, MIRROR - 18 - broken * 10, { size: 12 });
      ctx.globalAlpha = 1;
    }

    // Under the lake: the mirror, the layers rising at different rates below it, and grains joining the cap rock.
    const underLake = (1 - drain) * ramp(rise, COVER_M * 0.6, COVER_M);
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
    if (underLake > 0.01) {
      ctx.globalAlpha = underLake;
      ctx.strokeStyle = env.color("--ink");
      ctx.lineWidth = 1.4;
      ctx.lineCap = "round";
      FACTORS.forEach((f, i) => { // Arrows in proportion to each layer's rate: the centre rises fastest.
        const x = COLUMN.x + (i + 0.5) * strip + lean(MIRROR + 60), y = MIRROR + 74, len = 8 + 16 * f;
        ctx.stroke(shape([[x, y], [x, y - len], [x - 3, y - len + 4], [x, y - len], [x + 3, y - len + 4]], false));
      });
      ctx.lineCap = "butt";
      if (flowing && capH > 1) { // Insoluble grains rise from the mirror into the base of the cap rock.
        ctx.fillStyle = env.color("--xp-cap");
        for (let k = 0; k < 9; k++) {
          const phase = (env.time * 0.4 + k * 0.37) % 1;
          ctx.globalAlpha = underLake * (1 - phase);
          ctx.beginPath();
          ctx.arc(COLUMN.x + 8 + ((k * 41) % (COLUMN.width - 16)), MIRROR + 3 - phase * 5, 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    }

    // After the lake: rain, cracks between the upright layers, and a salt cave that grows along them (a34-p053).
    const dry = ramp(after, 2, 20);
    if (dry > 0.01) {
      ctx.globalAlpha = dry;
      ctx.strokeStyle = env.color("--xp-void");
      ctx.lineWidth = 1.1;
      for (let i = 1; i < FACTORS.length; i++) { // A crack opens where neighbouring layers have moved apart.
        const y = MIRROR - Math.min(lifts[i - 1], lifts[i]) - capH, depth = Math.abs(lifts[i - 1] - lifts[i]) * 2 + 14 * dry;
        const x = COLUMN.x + i * strip + lean(y);
        ctx.stroke(shape([[x, y], [x + lean(y + depth) - lean(y), y + depth]], false));
      }
      const grow = ramp(after, 15, 65);
      if (grow > 0.01) { // The cave: from a crack near the top, down and out to the east flank.
        const pts = cave.slice(0, 1 + Math.ceil(grow * (cave.length - 1))).map(([fx, fy]) => {
          const y = MIRROR - lifts[3] * 0.6 + fy * 80;
          return [COLUMN.x + fx * COLUMN.width + lean(y), y];
        });
        ctx.strokeStyle = env.color("--xp-void");
        ctx.lineWidth = 4;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.stroke(shape(pts, false));
        ctx.lineCap = "butt";
        if (grow > 0.6) {
          ctx.globalAlpha = dry * ramp(grow, 0.6, 0.9);
          const [cx, cy] = pts.at(-1);
          env.label(ctx, L.caves, cx + 8, cy + (small ? 22 : 4), { align: "left", size: 12 }); // Phones: below the rift's name.
        }
      }
      if (flowing) { // Rain falls on the mountain.
        ctx.globalAlpha = dry * 0.5;
        ctx.strokeStyle = env.color("--xp-fresh-ink");
        ctx.lineWidth = 1;
        for (let k = 0; k < 14; k++) {
          const phase = (env.time * 0.9 + k * 0.29) % 1, x = COLUMN.x - 20 + ((k * 53) % (COLUMN.width + 40));
          const y = TOP + 6 + phase * (top - TOP - 10);
          ctx.stroke(shape([[x, y], [x - 1.5, y + 6]], false));
        }
      }
      // The Lisan marl on the mountain against the marl on the plain: the rise since the lake (a34-p053).
      if (after > 8) {
        ctx.globalAlpha = dry;
        const yTop = MIRROR - lifts[0] - capH - 3, x = COLUMN.x - 18 + lean(yTop);
        ctx.strokeStyle = env.color("--ink");
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.stroke(shape([[COLUMN.x - 40, yTop], [COLUMN.x + lean(yTop), yTop]], false));
        ctx.setLineDash([]);
        ctx.stroke(shape([[x, MIRROR - 3], [x, yTop]], false));
        env.label(ctx, `${number(Math.round(after))} ${spec.control.unit}`, x - 5, (MIRROR + yTop) / 2 + 4, { align: "right", size: 12, weight: 700 });
      }
      ctx.globalAlpha = 1;
    }

    // Labels for the cap rock and the mountain.
    const capAlpha = ramp(capM, 6, 12);
    if (capAlpha > 0.01) {
      ctx.globalAlpha = capAlpha;
      const y = MIRROR - capH / 2 + 4 - lifts.at(-1);
      env.label(ctx, L.cap, RIGHT + lean(y) + 8, y, { align: "left" });
      // Once the cap rock is thick enough: it grows from below, so its youngest layer touches the salt (a34-p051).
      const young = ramp(capM, 14, 22) * (1 - drain);
      if (young > 0.01) {
        ctx.globalAlpha = young;
        const [first, second] = L.cap_young.split(" / ");
        // East of the mountain; on phones over the west block, where the sandstone's name is left out.
        const [lx, align, from, size] = small ? [140, "center", [214, MIRROR + 40], 11] : [RIGHT + 60, "left", [RIGHT + 56, MIRROR + 44], 12];
        env.label(ctx, first, lx, MIRROR + 50, { align, size, weight: 700 });
        env.label(ctx, second, lx, MIRROR + 50 + (size + 3) * env.unit, { align, size, weight: 700 });
        ctx.strokeStyle = env.color("--ink");
        ctx.lineWidth = 1;
        ctx.stroke(shape([from, small ? [COLUMN.x + lean(MIRROR) + 4, MIRROR - 2] : [RIGHT + lean(MIRROR) + 4, MIRROR - 2]], false));
      }
      ctx.globalAlpha = 1;
    }
    // The mountain's name, above the Amora formation's name while that still covers it.
    env.label(ctx, L.sodom, COLUMN.x + COLUMN.width / 2 + lean(top), Math.max(TOP + 16, top - 10 - (1 - broken) * 22));

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
    handle: (rise) => [COLUMN.x + COLUMN.width / 2 + lean(topAt(rise) + 58), topAt(rise) + 58],
    // 200 drawing units of drag cover the whole range.
    drag: (point, start) => start.value + ((start.point.y - point.y) * max) / 200,
  };
}
return { view: [0, TOP, W, H - TOP], animated: true, valueParts, create };
})();
