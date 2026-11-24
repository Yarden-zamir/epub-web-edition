// Interactive explainers inside printed figures (build: tools/web/45_explorables.py).
// Each figure gets a toggle between the explainer and the printed image. The explainer loads when it nears the view.
// A native range input is the one control: it gives keyboard, touch and screen reader support. Drawing modules
// (<kind>.js) may add direct dragging in the drawing; it sets the same input.
//
// A drawing file (7N-explorable-<kind>.js) registers explorableKit.kinds[kind] = {
//   valueText(value, spec) -> string             what the control value means, for the readout and screen readers
//   mount(svg, spec, api) -> update(value) -> string   draws once, then redraws for a value and returns the summary
// }  api: { setValue(value), drag(element, onMove(point, start)), commit() }
// All feature scripts share one scope (site/features/README.md): only explorableKit is global here.
const explorableKit = (() => {
const NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs = {}, parent = null) {
  const el = document.createElementNS(NS, tag);
  for (const [name, value] of Object.entries(attrs)) el.setAttribute(name, String(value));
  if (parent) parent.append(el);
  return el;
}

function svgText(text, attrs, parent) {
  const el = svgEl("text", attrs, parent);
  el.textContent = text;
  return el;
}

// Linear interpolation in a list of [x, y] points sorted by x; clamps at both ends.
function interpolate(points, x) {
  if (!points.length) throw new Error("interpolate: no points");
  if (x <= points[0][0]) return points[0][1];
  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = points[i];
    if (x <= x1) {
      const [x0, y0] = points[i - 1];
      return x1 === x0 ? y1 : y0 + ((y1 - y0) * (x - x0)) / (x1 - x0);
    }
  }
  return points[points.length - 1][1];
}

const number = (value, digits = 0) =>
  value.toLocaleString("he-IL", { minimumFractionDigits: digits, maximumFractionDigits: digits });

function svgPoint(svg, event) {
  const matrix = svg.getScreenCTM();
  if (!matrix) throw new Error("explorable: the drawing has no screen matrix");
  return new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
}

async function setUp(figure, box) {
  const response = await fetch(box.dataset.explorable);
  if (!response.ok) throw new Error(`${box.dataset.explorable}: HTTP ${response.status}`);
  const spec = await response.json();
  const kind = kinds[spec.kind];
  if (!kind) throw new Error(`explorable ${figure.id}: no drawing for kind ${spec.kind}`);
  const c = spec.control;

  const head = document.createElement("div");
  head.className = "xp-head";
  const title = document.createElement("p");
  title.className = "xp-title";
  title.textContent = spec.title;
  const instruction = document.createElement("p");
  instruction.className = "xp-instruction";
  instruction.textContent = spec.instruction;
  head.append(title, instruction);

  const stage = document.createElement("div");
  stage.className = "xp-stage";
  const svg = svgEl("svg", { class: "xp-svg", role: "img", "aria-label": spec.title });

  const controls = document.createElement("div");
  controls.className = "xp-controls";
  const id = `${figure.id}-xp`;
  const label = document.createElement("label");
  label.htmlFor = id;
  label.textContent = c.label;
  const input = document.createElement("input");
  Object.assign(input, { type: "range", id, min: c.min, max: c.max, step: c.step, value: c.start });
  input.dir = "ltr"; // Same direction as the chart axes on this site: the start of the process on the left.
  const output = document.createElement("output");
  output.htmlFor = id;
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "xp-reset";
  reset.textContent = "איפוס";
  controls.append(label, input, output, reset);

  const readout = document.createElement("p");
  readout.className = "xp-readout";
  // Screen readers hear the summary when a move ends, not on every step of a drag.
  const live = document.createElement("p");
  live.className = "visually-hidden";
  live.setAttribute("aria-live", "polite");

  stage.append(svg);
  box.prepend(head, stage, controls, readout, live);
  box.hidden = false;

  let frame = 0;
  let summary = "";
  const update = kind.mount(svg, spec, {
    setValue(value) {
      input.value = String(value); // The input clamps and rounds to its step.
      render();
    },
    drag(element, onMove) {
      element.classList.add("xp-handle");
      element.addEventListener("pointerdown", (down) => {
        if (down.button !== 0) return;
        down.preventDefault();
        element.setPointerCapture(down.pointerId);
        stage.classList.add("dragging");
        const start = { point: svgPoint(svg, down), value: Number(input.value) };
        const move = (e) => onMove(svgPoint(svg, e), start);
        const end = () => {
          element.removeEventListener("pointermove", move);
          stage.classList.remove("dragging");
          commit();
        };
        element.addEventListener("pointermove", move);
        element.addEventListener("pointerup", end, { once: true });
        element.addEventListener("pointercancel", end, { once: true });
      });
    },
    commit: () => commit(),
  });
  function render() {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const value = Number(input.value);
      const text = kind.valueText(value, spec);
      output.textContent = text;
      input.setAttribute("aria-valuetext", text);
      summary = update(value);
      readout.textContent = summary;
    });
  }
  function commit() {
    requestAnimationFrame(() => requestAnimationFrame(() => { live.textContent = summary; }));
  }
  input.addEventListener("input", render);
  input.addEventListener("change", commit);
  reset.addEventListener("click", () => {
    input.value = String(c.start);
    render();
    commit();
  });
  // Labels keep about 13 CSS pixels at any width: one CSS pixel is --xp-unit drawing units.
  new ResizeObserver(() => {
    if (!svg.clientWidth) return;
    const unit = svg.viewBox.baseVal.width / svg.clientWidth;
    svg.style.setProperty("--xp-unit", unit.toFixed(3));
    svg.classList.toggle("xp-narrow", unit > 1.3); // Phones: labels marked xp-minor hide.
  }).observe(svg);
  render();
}

const kinds = {}; // Filled by the drawing files, which run after this one; set-up waits for the figure to scroll near.
for (const figure of document.querySelectorAll("figure.has-explorable")) {
  const box = figure.querySelector(":scope > .explorable");
  const img = figure.querySelector(":scope > img");
  const group = document.createElement("div");
  group.className = "view-toggle";
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "תצוגת האיור");
  const make = (text, explain) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.addEventListener("click", () => setView(explain));
    group.append(b);
    return b;
  };
  const explainButton = make("הדגמה אינטראקטיבית", true);
  const printButton = make("האיור המודפס", false);
  let ready = false;
  const setView = (explain) => {
    explainButton.setAttribute("aria-pressed", String(explain));
    printButton.setAttribute("aria-pressed", String(!explain));
    box.hidden = !explain || !ready;
    if (img) img.hidden = explain && ready;
    figure.classList.toggle("showing-print", !explain);
  };
  figure.prepend(group);
  group.hidden = true; // Shown once the explainer works; until then the printed image stays.
  new IntersectionObserver((entries, observer) => {
    if (!entries[0].isIntersecting) return;
    observer.disconnect();
    setUp(figure, box)
      .then(() => { ready = true; group.hidden = false; setView(true); })
      .catch((err) => { box.hidden = true; group.remove(); console.error(err); });
  }, { rootMargin: "400px" }).observe(figure);
}
return { kinds, svgEl, svgText, interpolate, number };
})();
