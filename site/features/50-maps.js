// Maps. Leaflet loads on first use. Every map shares the same gesture rules:
// - A trackpad pinch (a wheel event with ctrlKey) or Ctrl + wheel zooms around the pointer, not the page.
// - A plain wheel scrolls the page, until the reader clicks or focuses the map; then it pans the map,
//   until the pointer leaves the map or the reader clicks outside it.
// - A mouse drags the map. Arrow keys and + / - work when the map has focus (Leaflet's keyboard handler).
// - On a touch screen one finger scrolls the page and two fingers pan and zoom.
const LEAFLET = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/";
const MAP_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM · &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)';
const WHEEL_HINT = "Ctrl + גלילה להגדלה · לחיצה על המפה כדי להזיז אותה";
const TOUCH_HINT = "שתי אצבעות מזיזות ומגדילות את המפה";
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
function makeMap(el, options = {}) {
  const touch = matchMedia("(pointer: coarse)").matches;
  // Without dragging, Leaflet sets touch-action: pan-x pan-y, so one finger scrolls the page and a pinch reaches the map.
  const map = L.map(el, { scrollWheelZoom: false, zoomSnap: 0, zoomDelta: 0.5, dragging: !touch,
    zoomControl: false, attributionControl: false, ...options });
  L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", { maxZoom: 17, crossOrigin: true }).addTo(map);
  // The tile licences ask for the credit to be reachable, so it is folded into a small ©, not removed.
  const Credit = L.Control.extend({ options: { position: "bottomright" }, onAdd() {
    const box = L.DomUtil.create("div", "map-credit");
    const button = L.DomUtil.create("button", "", box);
    button.type = "button";
    button.textContent = "©";
    button.setAttribute("aria-label", "קרדיט למפה");
    button.setAttribute("aria-expanded", "false");
    box.insertAdjacentHTML("beforeend", `<span>${MAP_CREDIT}</span>`);
    L.DomEvent.disableClickPropagation(box);
    button.addEventListener("click", () => button.setAttribute("aria-expanded", String(box.classList.toggle("open"))));
    return box;
  } });
  new Credit().addTo(map);

  const hint = document.createElement("div");
  hint.className = "map-hint";
  hint.setAttribute("aria-hidden", "true");
  el.append(hint);
  let hintTimer = 0;
  const hintText = document.createElement("span");
  hint.append(hintText);
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

  // Small pinch deltas add up within one frame, so a trackpad zooms smoothly; a mouse notch is one zoom level.
  let zoomBy = 0, zoomAt = null, frame = 0;
  el.addEventListener("wheel", (e) => {
    const scale = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? el.clientHeight : 1; // Lines or pages to pixels.
    if (e.ctrlKey) {
      e.preventDefault();
      zoomBy += Math.max(-1, Math.min(1, (-e.deltaY * scale) / 100));
      zoomAt = map.mouseEventToContainerPoint(e);
      frame ||= requestAnimationFrame(() => {
        map.setZoomAround(zoomAt, map.getZoom() + zoomBy, { animate: false });
        zoomBy = 0;
        frame = 0;
      });
    } else if (engaged) {
      e.preventDefault();
      map.panBy([e.deltaX * scale, e.deltaY * scale], { animate: false });
    } else {
      showHint(WHEEL_HINT);
    }
  }, { passive: false });
  if (touch) {
    el.addEventListener("touchmove", (e) => { if (e.touches.length === 1) showHint(TOUCH_HINT); }, { passive: true });
    el.addEventListener("touchstart", (e) => { if (e.touches.length > 1) el.removeAttribute("data-hint"); }, { passive: true });
  }
  return map;
}

