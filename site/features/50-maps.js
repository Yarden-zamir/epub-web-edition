// Maps. Leaflet loads on first use. Every map (places, then and now, figure maps) shares these parts:
// makeMap (tiles, credit, gestures), addPins (dots with names) and whenNear (draw on approach).
// Gesture rules, the same on every map:
// - A trackpad pinch (a wheel event with ctrlKey) or Ctrl + wheel zooms around the pointer, not the page.
// - A plain wheel scrolls the page, until the reader clicks or focuses the map; then it pans the map,
//   until the pointer leaves the map or the reader clicks outside it.
// - A mouse drags the map. Arrow keys and + / - work when the map has focus (Leaflet's keyboard handler).
// - On a touch screen one finger scrolls the page and two fingers pan and zoom.
// - A blocked gesture shows a short hint.
const LEAFLET = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/";
const MAP_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM · &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)';
const WHEEL_HINT = "Ctrl + גלילה להגדלה · לחיצה על המפה כדי להזיז אותה";
const TOUCH_HINT = "שתי אצבעות מזיזות ומגדילות את המפה";
// Animation length in seconds for map moves; the CSS twin is --motion in 50-maps.css.
const mapMotion = () => (reduceMotion.matches ? 0 : 0.35);
let leafletReady = null;
function loadLeaflet() {
  const load = (tag, attrs) => new Promise((resolve, reject) => {
    const el = Object.assign(document.createElement(tag), attrs, { crossOrigin: "anonymous" });
    el.onload = resolve;
    el.onerror = () => reject(new Error(`map: ${attrs.src ?? attrs.href} did not load`));
    document.head.append(el);
  });
  leafletReady ??= Promise.all([
    load("link", { rel: "stylesheet", href: `${LEAFLET}leaflet.css`, integrity: "sha512-Zcn6bjR/8RZbLEpLIeOwNtzREBAJnUKESxces60Mpoj+2okopSAcSUIUOseddDm0cxnGQzxIR7vJgsLZbdLE3w==" }),
    load("script", { src: `${LEAFLET}leaflet.js`, integrity: "sha512-BwHfrr4c9kmRkLw6iXFdzcdWV/PGkVgiIyIWLLlTSXzWQzxuSg4DiQUCpauz/EWjgk5TYQqX/kvn9pG1NpYfqg==" }),
  ]);
  return leafletReady;
}
// Draw a map once its box comes near the viewport. Returns a promise of the draw result.
function whenNear(el, draw) {
  return new Promise((resolve, reject) => {
    new IntersectionObserver((entries, observer) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      observer.disconnect();
      loadLeaflet().then(draw).then(resolve, reject);
    }, { rootMargin: "400px" }).observe(el);
  });
}
// One map in el. label names the map for screen readers; credit is HTML for the folded © control.
function makeMap(el, { label, credit = MAP_CREDIT, ...options }) {
  if (!label) throw new Error("makeMap: a map needs a label");
  const touch = matchMedia("(pointer: coarse)").matches;
  const still = reduceMotion.matches;
  // Without dragging, Leaflet sets touch-action: pan-x pan-y, so one finger scrolls the page and a pinch reaches the map.
  const map = L.map(el, { scrollWheelZoom: false, zoomSnap: 0, zoomDelta: 0.5, dragging: !touch,
    zoomAnimation: !still, fadeAnimation: !still, markerZoomAnimation: !still,
    zoomControl: false, attributionControl: false, ...options });
  el.classList.add("map-box");
  el.setAttribute("role", "region");
  el.setAttribute("aria-label", `${label}. חיצים מזיזים את המפה, פלוס ומינוס מגדילים ומקטינים.`);
  L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", { maxZoom: 17, crossOrigin: true, className: "map-tiles" }).addTo(map);
  // The tile licences ask for the credit to be reachable, so it is folded into a small ©, not removed.
  const Credit = L.Control.extend({ options: { position: "bottomright" }, onAdd() {
    const box = L.DomUtil.create("div", "map-credit");
    const button = L.DomUtil.create("button", "", box);
    button.type = "button";
    button.textContent = "©";
    button.setAttribute("aria-label", "קרדיט למפה");
    button.setAttribute("aria-expanded", "false");
    box.insertAdjacentHTML("beforeend", `<span dir="ltr">${credit}</span>`);
    L.DomEvent.disableClickPropagation(box);
    button.addEventListener("click", () => button.setAttribute("aria-expanded", String(box.classList.toggle("open"))));
    return box;
  } });
  new Credit().addTo(map);
  // Leaflet measures its box once; a box that was hidden or changed size needs a new measure.
  let measure = 0;
  new ResizeObserver(() => { measure ||= requestAnimationFrame(() => { measure = 0; map.invalidateSize({ animate: false }); }); }).observe(el);

  const hint = document.createElement("div");
  hint.className = "map-hint";
  hint.setAttribute("aria-hidden", "true");
  const hintText = document.createElement("span");
  hint.append(hintText);
  el.append(hint);
  let hintTimer = 0;
  const showHint = (text) => {
    hintText.textContent = text;
    el.setAttribute("data-hint", "");
    clearTimeout(hintTimer);
    hintTimer = setTimeout(() => el.removeAttribute("data-hint"), 1300);
  };
  let engaged = false;
  const engage = (on) => { engaged = on; el.toggleAttribute("data-engaged", on); if (on) el.removeAttribute("data-hint"); };
  el.addEventListener("pointerdown", () => engage(true));
  el.addEventListener("focusin", () => engage(true));
  el.addEventListener("focusout", (e) => { if (!el.contains(e.relatedTarget)) engage(false); });
  el.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") engage(false); });
  document.addEventListener("pointerdown", (e) => { if (!el.contains(e.target)) engage(false); });

  // Wheel deltas add up within one frame and apply once, so a trackpad pinch zooms smoothly at the display rate.
  let zoomBy = 0, panBy = [0, 0], zoomAt = null, frame = 0;
  const flush = () => {
    frame = 0;
    if (zoomBy) map.setZoomAround(zoomAt, map.getZoom() + zoomBy, { animate: false });
    if (panBy[0] || panBy[1]) map.panBy(panBy, { animate: false });
    zoomBy = 0;
    panBy = [0, 0];
  };
  el.addEventListener("wheel", (e) => {
    if (e.target.closest(".map-sheet, .leaflet-popup, .leaflet-control")) return; // Cards scroll on their own.
    const scale = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? el.clientHeight : 1; // Lines or pages to pixels.
    if (e.ctrlKey) {
      e.preventDefault();
      zoomBy += Math.max(-1, Math.min(1, (-e.deltaY * scale) / 100));
      zoomAt = map.mouseEventToContainerPoint(e);
    } else if (engaged) {
      e.preventDefault();
      panBy = [panBy[0] + e.deltaX * scale, panBy[1] + e.deltaY * scale];
    } else {
      showHint(WHEEL_HINT);
      return;
    }
    frame ||= requestAnimationFrame(flush);
  }, { passive: false });
  if (touch) {
    el.addEventListener("touchmove", (e) => { if (e.touches.length === 1) showHint(TOUCH_HINT); }, { passive: true });
    el.addEventListener("touchstart", (e) => { if (e.touches.length > 1) el.removeAttribute("data-hint"); }, { passive: true });
  }
  return map;
}
// Run fn once the map rests: a pinch fires zoomend on every frame.
function onSettle(map, fn) {
  let timer = 0;
  map.on("zoomend moveend resize", () => { clearTimeout(timer); timer = setTimeout(fn, 120); });
}

// Pins: a dot with its name beside it, on a halo so the name reads on any tile.
// items: [{ id, name, lat, lon, weight }]; weight orders the labels (a heavier pin keeps its name when two overlap).
// Returns { markers: Map id -> marker, offset(marker) -> [dx, dy] where the dot is drawn, relayout() }.
function addPins(map, items, { className = "", onSelect }) {
  const markers = new Map();
  const shift = new Map();
  for (const item of items) {
    const icon = L.divIcon({ className: `map-pin ${className}`, iconSize: [14, 14], iconAnchor: [7, 7],
      html: '<span class="pin-dot"></span><span class="pin-label" dir="rtl"></span>' });
    const marker = L.marker([item.lat, item.lon], { icon, keyboard: true, riseOnHover: true }).addTo(map);
    const el = marker.getElement();
    el.querySelector(".pin-label").textContent = item.name;
    el.setAttribute("role", "button");
    el.setAttribute("aria-label", item.name);
    marker.on("click", () => onSelect(item));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(item); } });
    markers.set(item.id, marker);
  }
  // Pins closer than a dot push each other apart a little, so each stays visible and tappable. Popups keep the
  // true position. Limit: a dense group at a far zoom spreads into a small cloud; zooming in brings every pin
  // back to its spot. Revisit if a map gets more than about 100 pins (the loop is quadratic).
  // Label sizes, read once: placing labels from the map's own pixel math needs no layout read on each move,
  // and a layout read on this long page costs a frame. Limit: a label keeps the size read after the book font loads;
  // revisit if label text size ever changes with the window.
  const measure = () => new Map([...markers].map(([id, m]) => {
    const label = m.getElement().querySelector(".pin-label");
    return [id, [label.offsetWidth, label.offsetHeight]];
  }));
  let sizes = measure();
  const spread = () => {
    const all = [...markers].map(([id, m]) => {
      const at = map.latLngToContainerPoint(m.getLatLng());
      return { id, m, x: at.x, y: at.y, x0: at.x, y0: at.y };
    });
    const gap = 16;
    for (let round = 0; round < 60; round++) {
      let moved = false;
      for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
        const a = all[i], b = all[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.hypot(dx, dy);
        if (d >= gap) continue;
        if (d < 0.01) { dx = Math.cos(i + j); dy = Math.sin(i + j); } // Same spot: pick a direction.
        const push = (gap - d) / 2 / Math.max(d, 0.01);
        a.x -= dx * push; a.y -= dy * push; b.x += dx * push; b.y += dy * push;
        moved = true;
      }
      if (!moved) break;
    }
    for (const it of all) {
      shift.set(it.m, [it.x - it.x0, it.y - it.y0]);
      it.m.getElement().style.translate = `${(it.x - it.x0).toFixed(1)}px ${(it.y - it.y0).toFixed(1)}px`;
    }
    return new Map(all.map((it) => [it.id, it]));
  };
  // A label that would overlap a shown label or another dot, or leave the map, stays hidden;
  // it shows on hover, focus or selection. The label sits 4px left of the 14px dot (.pin-label in 50-maps.css).
  const order = items.toSorted((a, b) => b.weight - a.weight);
  const labels = (at) => {
    const size = map.getSize();
    const dot = (p) => ({ left: p.x - 7, right: p.x + 7, top: p.y - 7, bottom: p.y + 7 });
    const label = (id) => {
      const p = at.get(id), [w, h] = sizes.get(id);
      return { left: p.x - 11 - w, right: p.x - 11, top: p.y - h / 2, bottom: p.y + h / 2 };
    };
    const dots = [...at.values()].map((p) => [p.id, dot(p)]);
    const hit = (a, b) => a.left < b.right + 2 && b.left < a.right + 2 && a.top < b.bottom + 1 && b.top < a.bottom + 1;
    const shown = [];
    for (const item of order) {
      const r = label(item.id);
      const inside = r.left >= 0 && r.right <= size.x && r.top >= 0 && r.bottom <= size.y;
      const clash = !inside || shown.some((s) => hit(r, s)) || dots.some(([id, d]) => id !== item.id && hit(r, d));
      markers.get(item.id).getElement().classList.toggle("label-hidden", clash);
      if (!clash) shown.push(r);
    }
  };
  const relayout = () => labels(spread());
  onSettle(map, relayout);
  relayout();
  document.fonts.ready.then(() => { sizes = measure(); relayout(); }); // The book font may arrive after the pins.
  return { markers, offset: (marker) => shift.get(marker) ?? [0, 0], relayout };
}
