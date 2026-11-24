// Figure viewer: a figure's image (or its site-only original) full screen, with its caption.
// Pinch, wheel or double tap zooms; a drag pans when zoomed. Previous and next follow the reading order: in a
// right-to-left book the next image lies to the left (left arrow, or a swipe to the right). A swipe down closes.
// The address carries ?photo=<figure id> while it is open; opening is one history entry, so Back closes it.
const viewer = byId("figure-dialog");
const viewerImg = byId("viewer-img");
const viewerStage = byId("viewer-stage");
const viewerCount = byId("viewer-count");
const rtl = document.dir === "rtl";
// Facsimile pages browse among themselves; every other image figure browses with the rest of the book.
const viewerSets = {
  pages: [...reading.querySelectorAll("figure.facsimile[id]:has(img)")],
  photos: [...reading.querySelectorAll("figure[id]:has(img):not(.facsimile, .video)")],
};
let viewerSet = viewerSets.photos;
let viewerAt = -1;

// Motion comes from the shared tokens in 00-base.css; reduced motion makes them 0 ms.
function motion(token) { return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(token)) || 0; }
const EASE_OUT = "cubic-bezier(0.22, 1, 0.36, 1)";

// Zoom and pan state of the shown image: translate(x, y) scale(s) around the image centre.
const view = { s: 1, x: 0, y: 0 };
const MAX_ZOOM = 4;
let frame = 0;
function render() {
  frame = 0;
  viewerImg.style.transform = `translate3d(${view.x}px, ${view.y}px, 0) scale(${view.s})`;
  viewer.toggleAttribute("data-zoomed", view.s > 1.01);
}
function schedule() { frame ||= requestAnimationFrame(render); }
// Fit the image to the stage, larger than its own size when the stage allows. Known limit: up to 2.5 times, where
// the book's ~1000 px images start to look soft; revisit when the site serves larger originals.
function fitImage() {
  const w = viewerImg.naturalWidth, h = viewerImg.naturalHeight;
  if (!w || !h) return;
  // With a mouse, the previous and next buttons stand beside the image, not on it.
  const pad = viewerStage.clientWidth <= 600 ? 16 : matchMedia("(hover: hover)").matches ? 176 : 48;
  const k = Math.min((viewerStage.clientWidth - pad) / w, (viewerStage.clientHeight - 32) / h, 2.5);
  viewerImg.style.width = `${Math.round(w * k)}px`;
  viewerImg.style.height = `${Math.round(h * k)}px`;
}
viewerImg.addEventListener("load", fitImage);
// Keep the zoomed image covering the stage: it may not leave a gap at an edge that it could cover.
function clampView() {
  const w = viewerImg.offsetWidth * view.s, h = viewerImg.offsetHeight * view.s;
  const mx = Math.max(0, (w - viewerStage.clientWidth) / 2), my = Math.max(0, (h - viewerStage.clientHeight) / 2);
  view.x = Math.min(mx, Math.max(-mx, view.x));
  view.y = Math.min(my, Math.max(-my, view.y));
}
// Zoom to scale s, keeping the screen point (px, py) still.
function zoomAt(s, px, py) {
  const box = viewerStage.getBoundingClientRect();
  const cx = px - (box.left + box.width / 2), cy = py - (box.top + box.height / 2);
  const next = Math.min(MAX_ZOOM, Math.max(1, s));
  view.x = cx - (cx - view.x) * (next / view.s);
  view.y = cy - (cy - view.y) * (next / view.s);
  view.s = next;
  if (next === 1) { view.x = 0; view.y = 0; }
  clampView();
  schedule();
}
function animateView(to) {
  const from = viewerImg.style.transform;
  Object.assign(view, to);
  clampView();
  render();
  viewerImg.animate([{ transform: from }, { transform: viewerImg.style.transform }], { duration: motion("--dur-base"), easing: EASE_OUT });
}

function figureImage(figure) {
  const img = figure.querySelector("img");
  return { src: figure.dataset.original ?? (img.currentSrc || img.src), alt: img.alt }; // A lazy image not yet loaded has no currentSrc.
}
function preload(at) {
  const figure = viewerSet[at];
  if (figure) new Image().src = figureImage(figure).src;
}
// Show figure number `at` of the current set. dir: -1 or 1 slides the new image in from that side, 0 fades.
async function showFigure(at, dir = 0) {
  const figure = viewerSet[at];
  if (!figure) throw new Error(`figure viewer: no figure ${at} in its set`);
  viewerAt = at;
  const { src, alt } = figureImage(figure);
  if (dir) { // A step waits for the new image, so the slide never shows a half-drawn picture.
    const next = new Image();
    next.src = src;
    await next.decode().catch(() => {}); // A broken image still shows its alt text.
    if (viewerAt !== at) return; // A newer request won.
  }
  Object.assign(view, { s: 1, x: 0, y: 0 });
  viewerImg.style.width = viewerImg.style.height = "";
  viewerImg.src = src;
  viewerImg.alt = alt;
  if (viewerImg.complete) fitImage();
  render();
  const caption = figure.querySelector("figcaption");
  const viewerCaption = byId("viewer-caption");
  viewerCaption.replaceChildren(...[...(caption?.childNodes ?? [])].map((n) => n.cloneNode(true)));
  // The caption's own language and direction; else its text decides, so an English caption reads left to right.
  const marked = caption?.closest("[lang]:not(html)") ?? caption?.querySelector("[lang]");
  viewerCaption.lang = marked?.lang ?? "";
  viewerCaption.dir = marked?.dir || "auto";
  const link = byId("viewer-original");
  link.hidden = !figure.dataset.original;
  if (figure.dataset.original) link.href = figure.dataset.original;
  viewerCount.textContent = viewerSet.length > 1 ? `${at + 1} מתוך ${viewerSet.length}` : "";
  byId("viewer-prev").disabled = at === 0;
  byId("viewer-next").disabled = at === viewerSet.length - 1;
  const url = new URL(location.href);
  url.searchParams.set("photo", figure.id);
  history.replaceState(history.state, "", url);
  const shift = dir * Math.min(120, viewerStage.clientWidth * 0.15);
  viewerImg.animate([{ opacity: 0, transform: `translate3d(${shift}px, 0, 0)` }, { opacity: 1, transform: "none" }],
    { duration: motion("--dur-slow"), easing: EASE_OUT });
  preload(at + 1);
  preload(at - 1);
}
// step 1 = next in reading order. The slide direction follows the page: next comes from the left in a right-to-left book.
async function stepFigure(step) {
  const at = viewerAt + step;
  if (at < 0 || at >= viewerSet.length) {
    viewerImg.animate([{ transform: viewerImg.style.transform }, { transform: `translate3d(${(rtl ? 1 : -1) * step * 24}px, 0, 0)` }, { transform: viewerImg.style.transform }],
      { duration: motion("--dur-slow"), easing: EASE_OUT }); // The end of the set: a small bounce.
    return;
  }
  const out = (rtl ? 1 : -1) * step * Math.min(120, viewerStage.clientWidth * 0.15);
  await viewerImg.animate([{ transform: viewerImg.style.transform, opacity: 1 }, { transform: `translate3d(${out + view.x}px, ${view.y}px, 0) scale(${view.s})`, opacity: 0 }],
    { duration: motion("--dur-quick"), easing: "ease-in", fill: "forwards" }).finished;
  await showFigure(at, -Math.sign(out));
  for (const a of viewerImg.getAnimations()) if (a.effect.getComputedTiming().fill === "forwards") a.cancel();
}

function openFigure(figure) {
  viewerSet = figure.matches(".facsimile") ? viewerSets.pages : viewerSets.photos;
  const at = viewerSet.indexOf(figure);
  if (at < 0) throw new Error(`figure viewer: #${figure.id} is not an image figure`);
  openOverlay(viewer, () => viewer.showModal());
  viewer.animate([{ opacity: 0 }, { opacity: 1 }], { duration: motion("--dur-base"), easing: EASE_OUT });
  showFigure(at);
}
// Forward to a viewer entry opens it again at the figure in the address.
overlayOpeners["figure-dialog"] = () => {
  const figure = document.getElementById(new URLSearchParams(location.search).get("photo") ?? "");
  if (!figure) return;
  viewerSet = figure.matches(".facsimile") ? viewerSets.pages : viewerSets.photos;
  viewer.showModal();
  showFigure(viewerSet.indexOf(figure));
};
async function closeViewer() {
  if (!viewer.open) return;
  await viewer.animate([{ opacity: 1 }, { opacity: 0 }], { duration: motion("--dur-quick"), easing: "ease-in", fill: "forwards" }).finished;
  viewer.close();
  for (const a of viewer.getAnimations()) a.cancel();
}
viewer.addEventListener("close", () => {
  // A jump from inside the viewer replaces its history entry: the address must not keep the photo.
  const url = new URL(location.href);
  if (url.searchParams.has("photo")) { url.searchParams.delete("photo"); history.replaceState(history.state, "", url); }
  viewerImg.getAnimations().forEach((a) => a.cancel());
  viewer.removeAttribute("data-zoomed");
});
byId("viewer-close").addEventListener("click", closeViewer);
byId("viewer-prev").addEventListener("click", () => stepFigure(-1));
byId("viewer-next").addEventListener("click", () => stepFigure(1));
reading.addEventListener("click", (e) => {
  const img = e.target.closest("figure[id] img");
  if (!img || img.closest(".video, .explorable")) return; // A video thumbnail starts the player; an explainer is live.
  openFigure(img.closest("figure"));
});
viewer.addEventListener("keydown", (e) => {
  const step = { ArrowLeft: rtl ? 1 : -1, ArrowRight: rtl ? -1 : 1 }[e.key];
  if (step) { e.preventDefault(); stepFigure(step); return; }
  const box = viewerStage.getBoundingClientRect();
  const zoom = { "+": 1.5, "=": 1.5, "-": 1 / 1.5 }[e.key];
  if (zoom) { e.preventDefault(); zoomAt(view.s * zoom, box.left + box.width / 2, box.top + box.height / 2); }
  if (e.key === "0") animateView({ s: 1, x: 0, y: 0 });
});

// Gestures on the stage. One pointer: pan when zoomed, else a swipe (sideways: previous or next; down: close).
// Two pointers: pinch. Work happens in one animation frame per screen update.
const pointers = new Map();
let gesture = null; // { kind: "pan" | "swipe" | "pinch", ... }
let lastTap = { t: 0, x: 0, y: 0 };
viewerStage.addEventListener("pointerdown", (e) => {
  if (e.button !== 0 || e.target.closest("button, a")) return;
  viewerStage.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    gesture = { kind: "pinch", dist: Math.hypot(a.x - b.x, a.y - b.y), s: view.s, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
  } else if (pointers.size === 1) {
    gesture = { kind: view.s > 1.01 ? "pan" : "swipe", x0: e.clientX, y0: e.clientY, vx: view.x, vy: view.y, t0: e.timeStamp, axis: null };
  }
  viewerImg.style.willChange = "transform";
});
viewerStage.addEventListener("pointermove", (e) => {
  const p = pointers.get(e.pointerId);
  if (!p || !gesture) return;
  p.x = e.clientX; p.y = e.clientY;
  if (gesture.kind === "pinch" && pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    view.x += mx - gesture.mx; view.y += my - gesture.my;
    gesture.mx = mx; gesture.my = my;
    zoomAt(gesture.s * Math.hypot(a.x - b.x, a.y - b.y) / gesture.dist, mx, my);
  } else if (gesture.kind === "pan") {
    view.x = gesture.vx + e.clientX - gesture.x0;
    view.y = gesture.vy + e.clientY - gesture.y0;
    clampView();
    schedule();
  } else if (gesture.kind === "swipe") {
    const dx = e.clientX - gesture.x0, dy = e.clientY - gesture.y0;
    gesture.axis ??= Math.hypot(dx, dy) > 8 ? (Math.abs(dx) > Math.abs(dy) ? "x" : "y") : null;
    if (gesture.axis === "x") { view.x = dx; view.y = 0; }
    if (gesture.axis === "y") { view.x = 0; view.y = Math.max(0, dy); viewer.style.setProperty("--drag", String(Math.min(1, Math.max(0, dy) / 300))); }
    schedule();
  }
});
function endPointer(e) {
  if (!pointers.delete(e.pointerId) || !gesture) return;
  if (gesture.kind === "pinch") {
    if (pointers.size === 1) { // Continue as a pan with the finger that stays.
      const [p] = [...pointers.values()];
      gesture = { kind: view.s > 1.01 ? "pan" : "swipe", x0: p.x, y0: p.y, vx: view.x, vy: view.y, t0: e.timeStamp, axis: view.s > 1.01 ? null : "none" };
    } else gesture = null;
    if (view.s < 1.01) animateView({ s: 1, x: 0, y: 0 });
    return;
  }
  if (pointers.size) return;
  const g = gesture;
  gesture = null;
  viewerImg.style.willChange = "";
  const dx = e.clientX - g.x0, dy = e.clientY - g.y0, dt = Math.max(1, e.timeStamp - g.t0);
  if (g.kind === "swipe" && g.axis === "x") {
    const fast = Math.abs(dx) / dt > 0.5;
    if (Math.abs(dx) > viewerStage.clientWidth * 0.18 || (fast && Math.abs(dx) > 30)) {
      stepFigure((dx > 0) === rtl ? 1 : -1); // In a right-to-left book the next image comes in from the left.
    } else animateView({ x: 0, y: 0 });
    return;
  }
  if (g.kind === "swipe" && g.axis === "y") {
    viewer.style.removeProperty("--drag");
    if (dy > 120 || (dy > 40 && dy / dt > 0.5)) closeViewer();
    else animateView({ x: 0, y: 0 });
    return;
  }
  // A tap: a second tap soon after, near the first, toggles zoom there.
  if (Math.hypot(dx, dy) < 10 && e.pointerType !== "mouse") {
    if (e.timeStamp - lastTap.t < 300 && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < 30) {
      toggleZoom(e.clientX, e.clientY);
      lastTap = { t: 0, x: 0, y: 0 };
    } else lastTap = { t: e.timeStamp, x: e.clientX, y: e.clientY };
  }
}
viewerStage.addEventListener("pointerup", endPointer);
viewerStage.addEventListener("pointercancel", endPointer);
function toggleZoom(px, py) {
  const from = viewerImg.style.transform;
  if (view.s > 1.01) Object.assign(view, { s: 1, x: 0, y: 0 });
  else zoomAt(2.5, px, py);
  render();
  viewerImg.animate([{ transform: from }, { transform: viewerImg.style.transform }], { duration: motion("--dur-base"), easing: EASE_OUT });
}
// Pointer capture makes the stage the target of the click, so hit-test the point itself.
viewerStage.addEventListener("dblclick", (e) => { if (document.elementFromPoint(e.clientX, e.clientY) === viewerImg) toggleZoom(e.clientX, e.clientY); });
// Wheel and trackpad pinch (the browser sends ctrl+wheel) zoom at the pointer.
viewerStage.addEventListener("wheel", (e) => {
  e.preventDefault();
  const delta = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
  zoomAt(view.s * Math.exp(-delta * (e.ctrlKey ? 0.01 : 0.0025)), e.clientX, e.clientY);
}, { passive: false });
addEventListener("resize", () => { if (viewer.open) { fitImage(); clampView(); schedule(); } });

// Arrival with ?photo=<figure id>: the book opens at that figure with the viewer on top. Back closes the viewer.
{
  const url = new URL(location.href);
  const figure = document.getElementById(url.searchParams.get("photo") ?? "");
  if (url.searchParams.has("photo")) {
    url.searchParams.delete("photo");
    history.replaceState(history.state, "", url);
  }
  if (figure && (viewerSets.photos.includes(figure) || viewerSets.pages.includes(figure))) {
    scrollToElement(figure);
    history.replaceState({ ...history.state, ...position() }, "");
    openFigure(figure);
  }
}
