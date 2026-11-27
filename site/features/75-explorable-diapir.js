// Mount Sodom rises (figure fig-a34-17): what the lakes did to it. A schematic west-east section after the printed
// figure; the control is time, from 300,000 years ago to today (spec.timeline: Weinberger et al. 2006, GSA Special
// Paper 401; Bartov et al. 2002 for Lake Lisan; the book, a34-p038 to a34-p053). Salt keeps rising from below; while a
// lake covers it, the lake dissolves what comes up, so the top stays flat at a "salt mirror" and only the insoluble
// grains pile up as cap rock. Since Lake Lisan fell (14,000 years ago) the salt rises above the plain: the mountain.
explorableKit.kinds.diapir = (() => {
const { number, iso, ramp, interpolate, shape } = explorableKit;

const W = 600, H = 360, TOP = -70;
const Y = (elev) => -60 + (-140 - elev) * 1.19; // Metres below sea level to drawing y, in the upper band (to scale).
const PLAIN = -254, RIFT_FLOOR_Y = 112; // The Amiaz plain today (90 m below the summit); the rift floor east (schematic).
const COLUMN = { x: 252, width: 96, bottom: 440 };
const RIGHT = COLUMN.x + COLUMN.width;
const LEAN = 0.08, LAYERS = 7;
// The control: four even stretches of the slider, each a span of years ago.
const STAGES = [300000, 150000, 40000, 14000, 0];
const yearsAt = (pos) => { const i = Math.min(3, Math.floor(pos)); return STAGES[i] + (STAGES[i + 1] - STAGES[i]) * (pos - i); };
const along = (points, years) => interpolate(points.map(([y, m]) => [-y, m]), -years); // Points of [years ago, value].

function valueParts(pos, spec) {
  const years = yearsAt(pos);
  return { num: number(years >= 1000 ? Math.round(years / 1000) * 1000 : Math.round(years / 100) * 100), unit: spec.control.unit, note: spec.stages[Math.min(3, Math.floor(pos))].short };
}

function create(spec) {
  const L = spec.labels, data = spec.timeline;
  const lean = (y) => (Y(PLAIN) - y) * LEAN;
  const strip = COLUMN.width / LAYERS;
  // A lake in the frame: the old lake while the cap rock formed, then Lake Lisan; between and after, none.
  const lakeAt = (years) => {
    if (years >= data.old_lake_years[1] && years <= data.old_lake_years[0]) return data.old_lake_m;
    if (years <= data.lisan_level[0][0] && years >= data.lisan_level.at(-1)[0]) return along(data.lisan_level, years);
    return null;
  };
  const topAt = (years) => along(data.salt_top, years);
  const capAt = (years) => along(data.cap_m, years);
  const dissolvedAt = (years) => along(data.dissolved_m, years);
  const lisanEnd = data.lisan_level.at(-1)[0];
  const sinceLisan = (years) => (years < lisanEnd ? Math.max(0, topAt(years) - topAt(lisanEnd)) : 0);
  // Rock around: the Amiaz plain west, the rift floor east, the marginal faults, the salt layers at depth.
  const WF = [[44, Y(PLAIN) - 22], [16, H + 10]], EF = [[556, RIFT_FLOOR_Y - 22], [584, H + 10]];
  const faultX = ([[x0, y0], [x1, y1]], y) => x0 + ((x1 - x0) * (y - y0)) / (y1 - y0);
  const westBlock = shape([[faultX(WF, Y(PLAIN)), Y(PLAIN)], [COLUMN.x + lean(Y(PLAIN)), Y(PLAIN)], [COLUMN.x + lean(H + 10), H + 10], [WF[1][0], H + 10]]);
  const eastBlock = shape([[RIGHT + lean(RIFT_FLOOR_Y), RIFT_FLOOR_Y], [faultX(EF, RIFT_FLOOR_Y), RIFT_FLOOR_Y], [EF[1][0], H + 10], [RIGHT + lean(H + 10), H + 10]]);
  const shoulders = [shape([[-10, WF[0][1]], WF[0], WF[1], [-10, H + 10]]), shape([EF[0], [W + 10, EF[0][1]], [W + 10, H + 10], EF[1]])];
  const westSalt = shape([[faultX(WF, 212), 212], [170, 212], [170, 228], [faultX(WF, 228), 228]]);
  const eastSalt = new Path2D(`M${RIGHT - 6} 250 C 370 262, 380 285, 400 290 H${faultX(EF, 290)} L${faultX(EF, 346)} 346 H400 C 370 346, 350 320, ${RIGHT - 8} 300 Z`);
  const FLOWS = [[338, 9], [322, 6.5], [306, 4.5]].map(([y, speed]) => // Lower layers move faster (a34-p048).
    ({ path: new Path2D(`M${faultX(EF, y) - 4} ${y} H410 C 385 ${y}, ${RIGHT - 10} ${y - 20}, ${RIGHT - 14} ${y - 60} V ${Y(PLAIN) + 60}`), speed }));
  const openArrow = new Path2D("M0 -9 V5 M-5 0 L0 7 L5 0");
  // Insoluble grains in the salt (about 5%, a34-p051): fixed places in the upright layers, carried up as the salt rises.
  const grains = Array.from({ length: 70 }, (_, k) => [((k * 37) % 89) / 89, (((k * 53) % 97) / 97) * 420]);
  const cave = [[0.42, 0], [0.55, 0.25], [0.48, 0.45], [0.62, 0.62], [0.8, 0.7], [1.06, 0.74]];

  function draw(ctx, pos, env) {
    const small = env.unit > 1.3, flowing = !reduceMotion.matches;
    const years = yearsAt(pos), stage = Math.min(3, Math.floor(pos));
    const lake = lakeAt(years), top = topAt(years), capM = capAt(years);
    const topY = Y(top), capH = capM * 1.19;
    const risen = pos * 150; // How far the salt has moved up on the drawing: for the grains only (schematic).
    const view = [0, TOP, W, H - TOP];
    ctx.drawImage(env.layer("sky", view, (c) => {
      c.fillStyle = env.gradient("sky", 0, TOP, 0, H, [[0, "--xp-sky-top"], [1, "--xp-sky"]]);
      c.fillRect(0, TOP, W, H - TOP);
    }), ...view);

    // The lake, when there is one: its surface at its level, its water down to the floor around the mountain.
    if (lake !== null) {
      const surface = Y(lake);
      ctx.fillStyle = env.gradient("lake", 0, TOP, 0, 140, [[0, "--xp-fresh"], [1, "--xp-fresh-deep"]]);
      ctx.fillRect(0, surface, W, H - surface);
      ctx.strokeStyle = env.color("--xp-surface");
      ctx.lineWidth = 2;
      ctx.stroke(shape([[0, surface], [W, surface]], false));
      ctx.lineWidth = 1.5;
      ctx.lineCap = "round";
      ctx.globalAlpha = 0.5;
      for (let i = 0; i < 6; i++) { // Glints drift slowly across the lake.
        const x = ((i * 97 + env.time * 7) % (W + 20)) - 10, y = surface + 8 + ((i * 13) % 24);
        ctx.stroke(shape([[x - 7, y], [x + 7, y]], false));
      }
      ctx.globalAlpha = 1;
      ctx.lineCap = "butt";
      env.label(ctx, stage === 0 ? L.old_lake : L.lisan, 480, surface + 24, { size: 13 });
    }

    // The salt column: upright layers, leaning east, up to the salt top; grains travel up inside it.
    const body = shape([[COLUMN.x + lean(topY), topY], [RIGHT + lean(topY), topY], [RIGHT + lean(COLUMN.bottom), COLUMN.bottom], [COLUMN.x + lean(COLUMN.bottom), COLUMN.bottom]]);
    ctx.fillStyle = env.gradient("salt-col", COLUMN.x, 0, RIGHT, 0, [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
    ctx.fill(body);
    ctx.save();
    ctx.clip(body);
    ctx.strokeStyle = env.color("--xp-salt-edge");
    ctx.lineWidth = 0.8;
    for (let i = 1; i < LAYERS; i++) ctx.stroke(shape([[COLUMN.x + i * strip + lean(topY - 20), topY - 20], [COLUMN.x + i * strip + lean(COLUMN.bottom), COLUMN.bottom]], false));
    ctx.fillStyle = env.color("--xp-cap");
    for (const [fx, y0] of grains) {
      const y = COLUMN.bottom - ((y0 + risen) % 420);
      ctx.beginPath(); ctx.arc(COLUMN.x + 4 + fx * (COLUMN.width - 8) + lean(y), y, 1.5, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
    ctx.strokeStyle = env.color("--xp-salt-edge");
    ctx.lineWidth = 1;
    ctx.stroke(body);

    // The cap rock on the salt top: the grains left when the salt around them dissolved.
    if (capH > 0.5) {
      const capTop = topY - capH;
      const cap = shape([[COLUMN.x + lean(capTop), capTop], [RIGHT + lean(capTop), capTop], [RIGHT + lean(topY), topY], [COLUMN.x + lean(topY), topY]]);
      ctx.fillStyle = env.gradient("cap", 0, capTop, 0, topY, [[0, "--xp-cap"], [1, "--xp-land-edge"]]);
      ctx.fill(cap);
      ctx.strokeStyle = env.color("--xp-land-edge");
      ctx.lineWidth = 0.8;
      ctx.stroke(cap);
      if (years < lisanEnd + 1) { // Lisan sediments and alluvium on the cap rock ride up with it since the lake fell.
        ctx.fillStyle = env.color("--xp-marl");
        ctx.fillRect(COLUMN.x + lean(capTop), capTop - 4, COLUMN.width, 4);
      }
    }

    // The rock around, the faults and the deep salt (fixed).
    ctx.drawImage(env.layer("frame", view, (c) => {
      c.fillStyle = env.gradient("land", 0, Y(PLAIN), 0, H, [[0, "--xp-land"], [1, "--xp-land-deep"]]);
      c.fill(westBlock);
      c.fill(eastBlock);
      c.fillStyle = env.color("--xp-land-deep");
      for (const shoulder of shoulders) c.fill(shoulder);
      c.strokeStyle = env.color("--xp-land-edge");
      c.lineWidth = 1.2;
      c.stroke(westBlock);
      c.stroke(eastBlock);
      c.fillStyle = env.gradient("salt", 0, 0, W, 0, [[0, "--xp-salt"], [1, "--xp-salt-shade"]]);
      c.fill(westSalt);
      c.fill(eastSalt);
      c.strokeStyle = env.color("--xp-salt-edge");
      c.stroke(westSalt);
      c.stroke(eastSalt);
      c.strokeStyle = env.color("--ink");
      c.lineWidth = 3;
      c.lineCap = "round";
      for (const fault of [WF, EF]) c.stroke(shape(fault, false));
      c.lineWidth = 1.5;
      for (const fault of [WF, EF]) { const y = 182; c.save(); c.translate(faultX(fault, y) + (fault === WF ? 14 : -14), y); c.stroke(openArrow); c.restore(); }
      env.label(c, L.west, 6, H - 8, { align: "left", size: 12, weight: 500, color: "--muted" });
      env.label(c, L.east, W - 6, H - 8, { align: "right", size: 12, weight: 500, color: "--muted" });
      env.label(c, L.rift, small ? 505 : 480, RIFT_FLOOR_Y - 8);
      env.label(c, L.salt, 92, 246);
      env.label(c, L.salt, 500, 278);
      if (!small) env.label(c, L.sand, 480, 200);
    }), ...view);
    env.label(ctx, L.amiaz, 140, Y(PLAIN) - 8);

    // Salt flows up from under the rift: dashes that move slowly, the lower lines faster.
    ctx.lineCap = "round";
    ctx.strokeStyle = env.color("--xp-salt-edge");
    ctx.lineWidth = 1.2;
    ctx.setLineDash([4, 7]);
    for (const { path, speed } of FLOWS) { ctx.lineDashOffset = flowing ? env.time * speed : 0; ctx.stroke(path); }
    ctx.setLineDash([]);
    ctx.lineDashOffset = 0;
    ctx.lineCap = "butt";

    // Under a lake: the salt mirror, and the salt dissolving at it into the water.
    if (lake !== null && Y(lake) < topY - capH) {
      ctx.strokeStyle = env.color("--xp-fresh-ink");
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 4]);
      ctx.stroke(shape([[COLUMN.x - 26 + lean(topY), topY], [RIGHT + 26 + lean(topY), topY]], false));
      ctx.setLineDash([]);
      env.label(ctx, L.mirror, COLUMN.x - 30 + lean(topY), topY + 16, { align: "right", size: 12 });
      if (flowing) {
        ctx.fillStyle = env.color("--xp-fresh-ink");
        for (let k = 0; k < 8; k++) {
          const phase = (env.time * 0.35 + k * 0.41) % 1;
          ctx.globalAlpha = 0.5 * (1 - phase);
          ctx.beginPath();
          ctx.arc(COLUMN.x + 10 + ((k * 23) % (COLUMN.width - 20)) + lean(topY), topY - capH - 4 - phase * 18, 1.6, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }
    }

    // Since the lake fell: rain, cracks and a growing cave (a34-p053, a34-p039).
    const dry = years < lisanEnd ? ramp(lisanEnd - years, 300, 3000) : 0;
    if (dry > 0.01) {
      ctx.globalAlpha = dry;
      ctx.strokeStyle = env.color("--xp-void");
      ctx.lineWidth = 1.1;
      for (let i = 1; i < LAYERS; i += 2) {
        const depth = 16 + 30 * dry;
        ctx.stroke(shape([[COLUMN.x + i * strip + lean(topY), topY], [COLUMN.x + i * strip + lean(topY + depth), topY + depth]], false));
      }
      const grow = ramp(lisanEnd - years, 3000, 12000);
      if (grow > 0.01) {
        const pts = cave.slice(0, 1 + Math.ceil(grow * (cave.length - 1))).map(([fx, fy]) => { const y = topY + 10 + fy * 70; return [COLUMN.x + fx * COLUMN.width + lean(y), y]; });
        ctx.lineWidth = 4;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.stroke(shape(pts, false));
        ctx.lineCap = "butt";
        if (grow > 0.6) { const [cx, cy] = pts.at(-1); env.label(ctx, L.caves, cx + 8, cy + (small ? 22 : 4), { align: "left", size: 12 }); }
      }
      if (flowing) {
        ctx.globalAlpha = dry * 0.5;
        ctx.strokeStyle = env.color("--xp-fresh-ink");
        ctx.lineWidth = 1;
        for (let k = 0; k < 14; k++) {
          const phase = (env.time * 0.9 + k * 0.29) % 1, x = COLUMN.x - 20 + ((k * 53) % (COLUMN.width + 40));
          const y = TOP + 70 + phase * (topY - capH - TOP - 80);
          ctx.stroke(shape([[x, y], [x - 1.5, y + 6]], false));
        }
      }
      ctx.globalAlpha = 1;
    }

    // Heights, to scale in the upper band: metres below sea level, from Lake Lisan on (older levels are not known).
    const scale = ramp(pos, 1.7, 2);
    if (scale > 0.01) {
      ctx.globalAlpha = scale;
      ctx.strokeStyle = env.color("--muted");
      ctx.lineWidth = 0.8;
      for (const m of [-150, -200, -250]) {
        ctx.stroke(shape([[W - 34, Y(m)], [W - 26, Y(m)]], false));
        env.label(ctx, `${m}`.replace("-", "−"), W - 38, Y(m) + 4, { align: "right", size: 10, weight: 500, color: "--muted" });
      }
      ctx.globalAlpha = 1;
    }

    // The mountain's name; today with its summit height.
    const summitY = topY - capH - (years < lisanEnd ? 4 : 0);
    env.label(ctx, years < 200 ? `${L.sodom}: ${L.summit}` : L.sodom, COLUMN.x + COLUMN.width / 2 + lean(summitY), Math.max(TOP + 52, summitY - 8), { size: 13 });

    // Stage title and live numbers: on wider screens only. On phones the drawing is too small for them; the value
    // line names the stage and the text under the slider gives the numbers.
    if (!small) {
      // Stage title, top centre: what happens now.
      const [head, tail] = spec.stages[stage].title.split(" / ");
      env.label(ctx, head, W / 2, TOP + 16, { size: 13, weight: 800 });
      if (tail) env.label(ctx, tail, W / 2, TOP + 16 + 16 * env.unit, { size: 12, weight: 600 });

      // Live numbers, left: salt dissolved, cap rock, and the rise since Lake Lisan fell.
      const rows = [[L.row_dissolved, dissolvedAt(years)], [L.row_cap, capM], [L.row_rise, sinceLisan(years)]];
      const size = 12, gap = (size + 5) * env.unit, panelW = 160 * env.unit, panelH = gap * rows.length + 8 * env.unit;
      const panelY = TOP + 46 * env.unit;
      ctx.fillStyle = env.color("--paper");
      ctx.globalAlpha = 0.88;
      ctx.beginPath(); ctx.roundRect(6, panelY, panelW, panelH, 6 * env.unit); ctx.fill();
      ctx.globalAlpha = 1;
      rows.forEach(([name, value], i) => {
        const y = panelY + gap * (i + 1) - 2 * env.unit;
        env.label(ctx, `${name}:`, 6 + panelW - 4 * env.unit, y, { align: "right", size, weight: 600 });
        env.label(ctx, `${number(Math.round(value))} ${L.m}`, 12 * env.unit, y, { align: "left", size, weight: 700 });
      });
    }

    if (years < 200) return spec.stages[3].text_today;
    return spec.stages[stage].text.replace("{years}", iso(number(Math.round(years / 1000) * 1000))).replace("{rise}", iso(number(Math.round(sinceLisan(years)))));
  }

  return {
    draw,
    // The handle sits on the salt column, below its top; dragging up moves time forward.
    handle: (pos) => { const y = Y(topAt(yearsAt(pos))) + 50; return [COLUMN.x + COLUMN.width / 2 + lean(y), y]; },
    drag: (point, start) => start.value + (start.point.y - point.y) / 60,
  };
}
return { view: [0, TOP, W, H - TOP], animated: true, valueParts, create };
})();
