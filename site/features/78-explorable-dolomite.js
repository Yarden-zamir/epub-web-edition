// The cracked dolomite layer (figure fig-a34-16). A stiff dolomite layer between two salt layers that shear in
// opposite directions, upright as in the printed figure: the salt on the left moves up, the salt on the right down.
// The dolomite cracks into blocks; the plastic salt lets the blocks turn clockwise and flows into the gaps.
// Not a mechanical model: the number of blocks, the turn and the stretch are schematic. The control value is the
// amount of shear in percent of the state in the printed figure.
explorableKit.kinds.dolomite = (() => {
const { number, ramp, shape } = explorableKit;

const W = 360, H = 560;
const AXIS = 180, HALF = 30, MIDY = 280; // The layer: centre line, half width and middle.
const N = 5, BLOCK = 76; // Five blocks, as in the print.
const CRACK = [8, 22], TURN = [22, 100]; // Cracks show over CRACK; blocks turn and move apart over TURN.
const TILT = 0.2, SPIN = 0.48, STRETCH = 0.32; // At full shear: column tilt and block turn (radians), stretch.
const SHIFT = 2.2; // Salt movement far from the layer, drawing units per percent.
const BAND = 24; // Spacing of the salt band lines.
const ARROW_X = 48;

// Fixed wobble, so the cracks and edges look broken and not ruled.
const wobble = (i, k) => Math.sin(i * 12.9898 + k * 78.233) * 3.1 + Math.sin(i * 4.1 + k * 1.7) * 1.4;
const STATES = ["intact", "shear", "cracked", "turning"];
const stateOf = (v) => STATES[v < 4 ? 0 : v < CRACK[1] ? 1 : v < 45 ? 2 : 3];
const valueParts = (v, spec) => ({ num: number(v), unit: spec.control.unit, note: spec.labels.states[stateOf(v)] });

function create(spec, env) {
  const L = spec.labels, t = spec.texts;
  // Crack lines across the layer, in coordinates around the middle of the intact layer: N + 1 lines, the first
  // and the last are the broken ends of the piece.
  const across = [-HALF, -HALF / 2, 0, HALF / 2, HALF];
  const cracks = [...Array(N + 1).keys()].map((j) => across.map((x, k) => [x, (j - N / 2) * BLOCK + x * 0.18 + wobble(j, k)]));
  // Each block: its outline around its own centre, and its centre in the intact layer.
  const side = (x, from, to, seed) => [1, 2, 3].map((k) => [x + wobble(seed, k) * 0.5, from + ((to - from) * k) / 4]);
  const rights = [], lefts = [];
  const blocks = [...Array(N).keys()].map((i) => {
    const cy = (i + 0.5 - N / 2) * BLOCK;
    const top = cracks[i], bottom = [...cracks[i + 1]].reverse();
    rights.push(side(HALF, top.at(-1)[1], bottom[0][1], i + 20));
    lefts.push(side(-HALF, bottom.at(-1)[1], top[0][1], i + 40));
    const outline = [...top, ...rights[i], ...bottom, ...lefts[i]];
    // Straight bands at the same x in every block, so they run unbroken through the intact layer.
    const streaks = [-15, -1, 13].map((x) => shape([[x, -BLOCK], [x, BLOCK]], false));
    return { cy, path: shape(outline.map(([x, y]) => [x, y - cy])), streaks };
  });
  // The intact layer: the outer outline of all blocks together, around the middle of the layer.
  const intact = shape([
    ...cracks[0], ...rights.flatMap((pts, i) => [...pts, cracks[i + 1].at(-1)]),
    ...[...cracks[N]].reverse().slice(1), ...[...lefts].reverse().flatMap((pts, k) => [...pts, cracks[N - 1 - k][0]]),
  ]);
  const crackPaths = cracks.slice(1, -1).map((line) => shape(line, false));
  const arrowUp = shape([[0, -40], [-13, -18], [-5, -18], [-5, 40], [5, 40], [5, -18], [13, -18]]);

  // Salt band lines: far from the layer they move with the salt; near it they bend, so the salt shows the shear.
  function bands(ctx, u) {
    const shift = (x) => -u * Math.tanh((AXIS - x) / 55);
    const path = new Path2D();
    const reach = Math.ceil(u / BAND) + 1;
    for (let k = -reach; k <= H / BAND + reach; k++) {
      for (let x = 0; x <= W; x += 8) (x ? path.lineTo(x, k * BAND + shift(x)) : path.moveTo(x, k * BAND + shift(x)));
    }
    ctx.strokeStyle = env.color("--xp-salt-shade");
    ctx.lineWidth = 1.4;
    ctx.stroke(path);
  }
  // A small arc arrow beside a gap, turning clockwise into it, as in the print.
  function arc(ctx, x, y) {
    const r = 15;
    ctx.beginPath();
    ctx.arc(x, y, r, Math.PI * 0.85, Math.PI * 1.55);
    ctx.stroke();
    const end = Math.PI * 1.55, ex = x + r * Math.cos(end), ey = y + r * Math.sin(end);
    ctx.save();
    ctx.translate(ex, ey);
    ctx.rotate(end + Math.PI / 2);
    ctx.fill(shape([[6, 0], [-3, -5], [-3, 5]]));
    ctx.restore();
  }

  function draw(ctx, v, env) {
    const u = v * SHIFT;
    const turn = ramp(v, ...TURN);
    ctx.fillStyle = env.color("--xp-salt");
    ctx.fillRect(0, 0, W, H);
    bands(ctx, u);

    // Block centres along a column that tilts clockwise and stretches; each block turns further.
    const tilt = TILT * turn, spin = SPIN * turn, stretch = 1 + STRETCH * turn;
    const centres = blocks.map(({ cy }) => [AXIS - cy * stretch * Math.sin(tilt), MIDY + cy * stretch * Math.cos(tilt)]);
    const cracked = ramp(v, ...CRACK);
    if (turn === 0) { // One fill under the blocks, so no salt shows through the seams between their fills.
      ctx.save();
      ctx.translate(AXIS, MIDY);
      ctx.fillStyle = env.color("--xp-dolomite");
      ctx.fill(intact);
      ctx.restore();
    }
    blocks.forEach((block, i) => {
      ctx.save();
      ctx.translate(...centres[i]);
      ctx.rotate(spin);
      ctx.fillStyle = env.color("--xp-dolomite");
      ctx.fill(block.path);
      ctx.save();
      ctx.clip(block.path);
      ctx.strokeStyle = env.color("--xp-dolomite-streak");
      ctx.lineWidth = 2.2;
      for (const streak of block.streaks) ctx.stroke(streak);
      ctx.restore();
      ctx.strokeStyle = env.color("--xp-land-edge");
      ctx.lineWidth = 1.4;
      ctx.lineJoin = "round";
      if (turn > 0) ctx.stroke(block.path);
      ctx.restore();
    });
    // Until the blocks part: one outline for the whole layer, and the cracks fade in through it.
    if (turn === 0) {
      ctx.save();
      ctx.translate(AXIS, MIDY);
      ctx.strokeStyle = env.color("--xp-land-edge");
      ctx.lineWidth = 1.4;
      ctx.lineJoin = "round";
      ctx.stroke(intact);
      ctx.globalAlpha = cracked;
      for (const path of crackPaths) ctx.stroke(path);
      ctx.restore();
    }
    // Arc arrows in the gaps once the salt flows in.
    const flow = ramp(v, 35, 60);
    if (flow > 0) {
      ctx.globalAlpha = flow;
      ctx.strokeStyle = ctx.fillStyle = env.color("--xp-fresh-ink");
      ctx.lineWidth = 3;
      for (let i = 1; i < N; i++) {
        const [x0, y0] = centres[i - 1], [x1, y1] = centres[i];
        arc(ctx, (x0 + x1) / 2 - HALF - 6, (y0 + y1) / 2 + 8);
      }
      ctx.globalAlpha = 1;
    }
    // The big straight arrows move with the salt: up on the left, down on the right.
    ctx.globalAlpha = 0.45 + 0.55 * ramp(v, 0, 6);
    ctx.fillStyle = env.color("--accent");
    ctx.save(); ctx.translate(ARROW_X, MIDY + 40 - u); ctx.fill(arrowUp); ctx.restore();
    ctx.save(); ctx.translate(W - ARROW_X, MIDY - 40 + u); ctx.rotate(Math.PI); ctx.fill(arrowUp); ctx.restore();
    ctx.globalAlpha = 1;

    env.label(ctx, L.salt, 14, H - 16, { align: "left" });
    env.label(ctx, L.salt, W - 14, 24, { align: "right" });
    const [bx, by] = centres[N - 1];
    env.label(ctx, L.dolomite, bx + HALF + 14, by + 4, { align: "left", color: "--soft" });

    const state = stateOf(v);
    if (state === "intact") return t.start;
    if (state === "shear") return t.shear;
    if (state === "cracked") return t.cracked;
    return v >= 95 ? `${t.turning} ${t.print}` : t.turning;
  }

  return {
    draw,
    handle: (v) => [ARROW_X, MIDY + 40 - v * SHIFT],
    drag: (point, start) => start.value + (start.point.y - point.y) / SHIFT,
  };
}
return { view: [0, 0, W, H], valueParts, create };
})();
