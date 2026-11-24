// Maps inside printed figures (build: tools/web/72_map_figures.py): figure maps and the then-and-now view.
// Each figure gets a toggle between the map and the printed image. The map draws when the figure nears the view;
// until it works, the printed image stays and the toggle stays hidden.
(() => {
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
const number = (value) => value.toLocaleString("he-IL", { maximumFractionDigits: 1 });
// "1848-05" or "2026-11-01" -> "מאי 1848".
const monthYear = (date) => `${MONTHS[Number(date.slice(5, 7)) - 1]} ${date.slice(0, 4)}`;
// The map box takes the shape of the printed image, within the height of the window.
function sizeLike(box, img) {
  box.style.aspectRatio = img ? `${img.getAttribute("width")} / ${img.getAttribute("height")}` : "4 / 5";
}

// Figure map: pins with names, lines with a legend, areas with a label.
function figureMap(box, spec, img) {
  const head = el("p", "mf-title", spec.title);
  const stage = el("div", "mf-map");
  sizeLike(stage, img);
  const legend = el("ul", "mf-legend");
  spec.legend.forEach((name, i) => {
    const li = el("li");
    li.innerHTML = `<svg viewBox="0 0 28 8" aria-hidden="true"><path class="mf-line slot-${i + 1}" d="M2 4H26"/></svg>`;
    li.append(name);
    legend.append(li);
  });
  for (const area of spec.areas) {
    const li = el("li");
    li.innerHTML = '<svg viewBox="0 0 28 14" aria-hidden="true"><rect class="mf-area" x="3" y="2" width="22" height="10" rx="5"/></svg>';
    li.append(area.name);
    legend.append(li);
  }
  box.replaceChildren(head, stage, legend);
  legend.hidden = !legend.children.length;
  box.hidden = false;
  const map = makeMap(stage, { label: spec.title, credit: spec.credit });
  map.fitBounds(spec.bounds);
  for (const area of spec.areas) {
    L.polygon(area.coords, { className: "mf-area", interactive: false }).addTo(map)
      .bindTooltip(area.name, { permanent: true, direction: "center", className: "mf-area-label" });
  }
  for (const line of spec.lines) {
    L.polyline(line.coords, { className: "mf-line-halo", interactive: false }).addTo(map);
    L.polyline(line.coords, { className: `mf-line slot-${line.slot}`, interactive: false }).addTo(map);
  }
  let selected = null;
  const pins = addPins(map, spec.markers.map((m, i) => ({ ...m, id: i, weight: -i })), { onSelect(m) {
    selected?.getElement()?.classList.remove("selected");
    selected = pins.markers.get(m.id);
    selected.getElement().classList.add("selected");
    if (!m.target) return;
    const card = el("div", "mf-card");
    card.dir = "rtl";
    const link = el("a", "", "בספר");
    link.href = `#${m.target}`;
    link.addEventListener("click", (e) => { e.preventDefault(); map.closePopup(); goTo(m.target, { from: link }); });
    card.append(el("strong", "", m.name), link);
    const [dx, dy] = pins.offset(selected);
    L.popup({ className: "mf-popup", offset: [dx, dy - 8], autoPanPadding: [16, 16] }).setLatLng(selected.getLatLng()).setContent(card).openOn(map);
  } });
  map.on("popupclose", () => { selected?.getElement()?.classList.remove("selected"); selected = null; });
}

// Then and now: dated map layers over today's base map, with a time control that fades between them,
// and a side-by-side mode with a layer picker in each pane.
function thenNow(box, spec, img) {
  const layers = spec.layers;
  const last = layers.length - 1;
  const head = el("p", "mf-title", spec.title);
  const modes = el("div", "view-toggle tn-modes");
  modes.setAttribute("role", "group");
  modes.setAttribute("aria-label", "אופן ההשוואה");
  const fadeButton = el("button", "", "מעבר בזמן");
  const sideButton = el("button", "", "זו לצד זו");
  for (const b of [fadeButton, sideButton]) b.type = "button";
  modes.append(fadeButton, sideButton);
  const stage = el("div", "tn-stage");
  const fadeBox = el("div", "tn-map");
  sizeLike(stage, img);
  stage.append(fadeBox);

  // Time control: a range from the first layer (0) to the last; whole numbers are the layers.
  const time = el("div", "tn-time");
  const input = el("input");
  const inputId = `${box.closest("figure").id}-time`;
  Object.assign(input, { type: "range", id: inputId, min: 0, max: last, step: "any", value: 0 });
  input.dir = "ltr"; // Old on the left, like the chart axes of this site.
  input.setAttribute("aria-label", "שנה");
  const stops = el("div", "tn-stops");
  stops.dir = "ltr";
  const stopButtons = layers.map((layer, i) => {
    const b = el("button", "", layer.year);
    b.type = "button";
    b.setAttribute("aria-label", layer.label);
    b.addEventListener("click", () => glide(i));
    stops.append(b);
    return b;
  });
  time.append(input, stops);
  const readout = el("div", "tn-readout");
  box.replaceChildren(head, modes, stage, time, readout);
  box.hidden = false;

  // What one layer shows: its name (with the full label), the lake level then with its source, and the map credit.
  // The level reads "מפלס ים המלח: −401.3 מ' (מאי 1848)", with the number kept left to right.
  const levelNote = (layer, withName) => {
    const { value, date, source, url } = layer.level;
    const said = el("p", "tn-level");
    said.setAttribute("aria-live", "polite");
    if (withName) said.append(el("strong", "", layer.label), el("br"));
    const figure = el("bdi", "", `${value < 0 ? "−" : ""}${number(Math.abs(value))}`);
    figure.dir = "ltr";
    const link = Object.assign(el("a", "", "מקור"), { href: url, rel: "noopener", title: source });
    said.append("מפלס ים המלח: ", figure, ` מ' (${monthYear(date)}) · `, link);
    return said;
  };
  const creditNote = (layer) => {
    const credit = el("p", "tn-credit");
    credit.dir = "ltr";
    credit.append(Object.assign(el("a", "", layer.credit.text), { href: layer.credit.url, rel: "noopener" }));
    return credit;
  };

  // Fade mode. The first layer loads at once. The others load when the browser is idle after it, or at once when the
  // reader moves the time control, so the first view waits for one image only. The note shows while a layer that
  // the control shows is not in yet.
  const fadeMap = makeMap(fadeBox, { label: `${spec.title}: מעבר בזמן`, maxBounds: L.latLngBounds(layers[0].bounds).pad(0.6) });
  fadeMap.fitBounds(layers[0].bounds);
  const overlay = (layer, opacity = 1) => L.imageOverlay(layer.image, layer.bounds, { className: "tn-layer", interactive: false, alt: "", opacity });
  const loading = el("p", "tn-loading", "טוען את המפות…");
  stage.append(loading);
  const fadeLayers = layers.map((layer) => overlay(layer, 0)); // Clear until render sets it, so a late layer never flashes.
  const ready = new Set();
  const add = (o) => {
    o.once("load error", () => { ready.add(o); frame ||= requestAnimationFrame(render); });
    o.addTo(fadeMap);
  };
  let restAdded = false;
  const addRest = () => {
    if (restAdded) return;
    restAdded = true;
    fadeLayers.slice(1).forEach(add);
  };
  add(fadeLayers[0]);
  fadeLayers[0].once("load error", () => whenIdle(addRest));
  // Between layers i and i + 1 the newer one fades in first, then the older one fades out, so the middle of the
  // move never shows two half-clear maps. An older layer outside a newer one's bounds fades out with it.
  const ease = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  const opacity = (i, t) => {
    const d = t - i;
    if (d <= -1 || d >= 1) return 0;
    return d < 0 ? ease(0, 0.6, 1 + d) : 1 - ease(0.4, 1, d);
  };
  let t = 0, frame = 0, shown = -1;
  const render = () => {
    frame = 0;
    fadeLayers.forEach((o, i) => { const img = o.getElement(); if (img) img.style.opacity = opacity(i, t).toFixed(3); });
    loading.hidden = fadeLayers.every((o, i) => opacity(i, t) === 0 || ready.has(o));
    const near = Math.round(t);
    input.setAttribute("aria-valuetext", layers[near].label);
    stopButtons.forEach((b, i) => b.setAttribute("aria-pressed", String(i === near)));
    if (near !== shown) {
      shown = near;
      readout.replaceChildren(levelNote(layers[near], true), creditNote(layers[near]));
    }
  };
  const setT = (value) => {
    t = Math.min(last, Math.max(0, value));
    if (t > 0) addRest();
    input.value = String(t);
    frame ||= requestAnimationFrame(render);
  };
  let glideFrame = 0;
  const glide = (to) => {
    cancelAnimationFrame(glideFrame);
    const from = t, ms = reduceMotion.matches ? 0 : 450 + 250 * Math.abs(to - from);
    const start = performance.now();
    const step = (now) => {
      const k = ms ? Math.min(1, (now - start) / ms) : 1;
      setT(from + (to - from) * (1 - (1 - k) ** 3));
      if (k < 1) glideFrame = requestAnimationFrame(step);
    };
    glideFrame = requestAnimationFrame(step);
  };
  input.addEventListener("input", () => { cancelAnimationFrame(glideFrame); setT(Number(input.value)); });
  // Arrow keys move one layer at a time; a free range step would move a hair.
  input.addEventListener("keydown", (e) => {
    const later = Math.floor(t) + 1, earlier = Math.ceil(t) - 1;
    const to = { ArrowRight: later, ArrowUp: later, ArrowLeft: earlier, ArrowDown: earlier, Home: 0, End: last }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    glide(Math.min(last, Math.max(0, to)));
  });
  input.addEventListener("change", () => glide(Math.round(t))); // A drag ends on the nearest layer.
  setT(0);

  // Side-by-side mode: two maps of the same size that move together, each with its own layer.
  let panes = null;
  const paneLayers = [layers[0], layers[last]]; // The layer in each pane; below the panes go their credits.
  const sideCredits = () => readout.replaceChildren(...[...new Set(paneLayers)].map(creditNote));
  const makePanes = () => {
    const grid = el("div", "tn-panes");
    const center = fadeMap.getCenter(), zoom = fadeMap.getZoom();
    const made = [0, last].map((start, n) => {
      const pane = el("div", "tn-pane");
      // Layer picker: one button per year, like the time control.
      const pick = el("div", "tn-pick");
      pick.setAttribute("role", "group");
      pick.setAttribute("aria-label", n ? "שכבה במפה השמאלית" : "שכבה במפה הימנית");
      pick.dir = "ltr";
      const years = layers.map((layer) => {
        const b = el("button", "", layer.year);
        b.type = "button";
        b.setAttribute("aria-label", layer.label);
        pick.append(b);
        return b;
      });
      const level = el("div", "tn-pane-notes");
      const mapBox = el("div", "tn-map");
      pane.append(pick, mapBox, level);
      grid.append(pane);
      return { start, years, level, mapBox };
    });
    stage.append(grid);
    const maps = made.map(({ start, years, level, mapBox }, n) => {
      const map = makeMap(mapBox, { label: `${spec.title}: ${n ? "מפה שמאלית" : "מפה ימנית"}` });
      map.setView(center, zoom, { animate: false });
      let current = null;
      const show = (i) => {
        current?.remove();
        current = overlay(layers[i]).addTo(map);
        years.forEach((b, j) => b.setAttribute("aria-pressed", String(i === j)));
        level.replaceChildren(levelNote(layers[i], false));
        paneLayers[n] = layers[i];
        sideCredits();
      };
      years.forEach((b, i) => b.addEventListener("click", () => show(i)));
      show(start);
      return map;
    });
    // Each move of one map sets the other, without animation, so they stay in step frame by frame.
    let syncing = false;
    for (const [a, b] of [maps, maps.toReversed()]) {
      a.on("move zoom", () => {
        if (syncing) return;
        syncing = true;
        b.setView(a.getCenter(), a.getZoom(), { animate: false });
        syncing = false;
      });
    }
    return { grid, maps };
  };
  const setMode = (side) => {
    fadeButton.setAttribute("aria-pressed", String(!side));
    sideButton.setAttribute("aria-pressed", String(side));
    panes ??= side ? makePanes() : null;
    stage.classList.toggle("side", side);
    fadeBox.hidden = side;
    time.hidden = side;
    if (side) sideCredits(); else { shown = -1; render(); }
    if (panes) {
      panes.grid.hidden = !side;
      const [a, b] = panes.maps;
      if (side) {
        for (const m of panes.maps) m.invalidateSize({ animate: false });
        a.setView(fadeMap.getCenter(), fadeMap.getZoom(), { animate: false });
        b.setView(fadeMap.getCenter(), fadeMap.getZoom(), { animate: false });
      } else {
        fadeMap.invalidateSize({ animate: false });
        fadeMap.setView(a.getCenter(), a.getZoom(), { animate: false });
      }
    }
  };
  fadeButton.addEventListener("click", () => setMode(false));
  sideButton.addEventListener("click", () => setMode(true));
  setMode(false);
}

async function loadMapSpec(box) {
  const response = await fetch(box.dataset.map);
  if (!response.ok) throw new Error(`${box.dataset.map}: HTTP ${response.status}`);
  return response.json();
}
function drawMap(figure, box, spec) {
  const img = figure.querySelector(":scope > img");
  if (spec.kind === "figure-map") figureMap(box, spec, img);
  else if (spec.kind === "then-now") thenNow(box, spec, img);
  else throw new Error(`${box.dataset.map}: unknown map kind ${spec.kind}`);
}

for (const figure of document.querySelectorAll("figure.has-map")) {
  const box = figure.querySelector(":scope > .map-figure");
  const img = figure.querySelector(":scope > img");
  const group = el("div", "view-toggle");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "תצוגת האיור");
  const make = (text, live) => {
    const b = el("button", "", text);
    b.type = "button";
    b.addEventListener("click", () => keepFigureTop(figure, () => setView(live)));
    group.append(b);
    return b;
  };
  const mapButton = make(box.dataset.kind === "then-now" ? "אז והיום" : "מפה אינטראקטיבית", true);
  const printButton = make("המפה בספר", false);
  const setView = (live) => {
    mapButton.setAttribute("aria-pressed", String(live));
    printButton.setAttribute("aria-pressed", String(!live));
    box.hidden = !live;
    if (img) img.hidden = live;
  };
  group.hidden = true;
  figure.prepend(group);
  whenNear(figure, async () => {
    const spec = await loadMapSpec(box);
    keepFigureTop(figure, () => { drawMap(figure, box, spec); group.hidden = false; setView(true); });
  }).catch((err) => { box.hidden = true; group.remove(); console.error(err); });
}
})();
