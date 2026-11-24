// Web edition features. Each one works on the EPUB-derived DOM and its stable IDs.
// The page reads fully without this script.

const reading = document.getElementById("read");

function byId(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`reader.js: missing #${id}`);
  return el;
}

// History. Every jump and every overlay is one history entry, so Back returns to the exact reading position
// or closes the top overlay, and Forward redoes it. Each entry's state holds:
//   y: the scroll position, kept up to date with replaceState while the reader scrolls (never pushState);
//   overlays: IDs of the open overlays, bottom first;
//   target, marks: the element a jump went to and the text to highlight there;
//   back: { id, marks } — what to highlight when the reader comes back to this entry (the link they followed).
history.scrollRestoration = "manual";
let overlayStack = [];
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

// Highlight: the exact cited text when known (CSS Custom Highlight API), else the whole target element.
// About one second, then a short fade; with reduced motion a static highlight that is then removed.
let highlightTimers = [];
function textRanges(el, needle) {
  // Search the element's text with runs of white space collapsed, and map matches back to DOM ranges.
  const nodes = [], walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let text = "";
  const map = []; // Index in text -> [node, offset].
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement.closest(".deep-link, .term-popover")) continue;
    nodes.push(node);
    for (let i = 0; i < node.data.length; i++) {
      const c = /\s/.test(node.data[i]) ? " " : node.data[i];
      if (c === " " && text.endsWith(" ")) continue;
      text += c;
      map.push([node, i]);
    }
  }
  const want = needle.split(/\s+/).filter(Boolean).join(" ");
  const ranges = [];
  if (!want) return ranges;
  for (let at = text.indexOf(want); at >= 0; at = text.indexOf(want, at + want.length)) {
    const range = new Range();
    range.setStart(...map[at]);
    const [endNode, endOffset] = map[at + want.length - 1];
    range.setEnd(endNode, endOffset + 1);
    ranges.push(range);
  }
  return ranges;
}
function highlight(el, marks = []) {
  for (const t of highlightTimers) clearTimeout(t);
  highlightTimers = [];
  const registry = globalThis.CSS?.highlights;
  const ranges = registry && marks.length ? marks.flatMap((m) => textRanges(el, m)) : [];
  if (ranges.length) {
    const steps = reduceMotion.matches ? [["jump-1", 0], [null, 1000]] : [["jump-1", 0], ["jump-2", 900], ["jump-3", 1050], [null, 1200]];
    const show = (name) => {
      for (const n of ["jump-1", "jump-2", "jump-3"]) registry.delete(n);
      if (name) registry.set(name, new Highlight(...ranges));
    };
    for (const [name, at] of steps) {
      if (at === 0) show(name); // At once, so a busy page cannot delay the first frame of the highlight.
      else highlightTimers.push(setTimeout(() => show(name), at));
    }
    return;
  }
  for (const n of ["jump-1", "jump-2", "jump-3"]) registry?.delete(n);
  el.classList.remove("flash");
  void el.offsetWidth; // Restart the highlight animation.
  el.classList.add("flash");
  highlightTimers.push(setTimeout(() => el.classList.remove("flash"), 1200));
}
// Every jump lands its target about 22% down the screen, so the lines before it give context,
// and never less than the fixed bar's height plus 4rem from the top (short phones).
function jumpOffset() {
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
  return Math.max(innerHeight * 0.22, byId("nav").offsetHeight + 4 * rem);
}
// A reading position: the scroll offset plus the block at the jump line and its distance from it. Restoring by
// that block stays exact when content above it changes height later (a chart or the map drawing).
function position() {
  const line = jumpOffset();
  const block = document.elementFromPoint(innerWidth / 2, line)?.closest(".book [id], #places, #read");
  return { y: scrollY, anchor: block?.id ?? null, dy: block ? block.getBoundingClientRect().top - line : 0 };
}
// Place an element `dy` pixels below the jump line. Off-screen chapters render lazily (content-visibility), so their
// height is only an estimate until they come near: scrollIntoView renders the target first (scroll-padding-top in
// 00-base.css equals jumpOffset()), and a second pass on the next frames corrects any shift that rendering caused.
function placeAtJumpLine(el, dy = 0) {
  el.scrollIntoView({ block: "start", behavior: "instant" });
  if (dy) scrollBy({ top: -dy, behavior: "instant" });
  const correct = () => {
    const off = el.getBoundingClientRect().top - jumpOffset() - dy;
    if (Math.abs(off) > 2) scrollBy({ top: off, behavior: "instant" });
  };
  requestAnimationFrame(() => { correct(); requestAnimationFrame(correct); });
}
function restorePosition(state) {
  const block = state.anchor && document.getElementById(state.anchor);
  if (block) placeAtJumpLine(block, state.dy);
  else scrollTo({ top: state.y, behavior: "instant" });
}
function scrollToElement(el) {
  placeAtJumpLine(el);
}

// Jump to an element: one new history entry. From inside overlays, the jump replaces the top overlay's entry,
// so Back returns to where the reader was before opening it. options.marks: text to highlight at the target;
// options.from: the link followed, highlighted again when the reader comes back.
function goTo(id, options = {}) {
  const el = document.getElementById(id);
  if (!el) return;
  const from = options.from?.closest?.(".book [id], #places [id]");
  const back = from && !from.closest("dialog, [popover]") ? { id: from.id, marks: [options.from.textContent.trim()].filter(Boolean) } : null;
  const entry = { y: null, overlays: [], target: id, marks: options.marks ?? [] };
  if (overlayStack.length) {
    const open = overlayStack;
    overlayStack = []; // Closing them now must not move history.
    for (const oid of open.toReversed()) closeOverlayElement(byId(oid));
    history.replaceState(entry, "", `#${id}`);
  } else {
    // options.keepOrigin: the caller already saved where the reader came from (the chapter rail does, before it scrubs).
    if (!options.keepOrigin) history.replaceState({ ...history.state, ...position(), back }, "");
    history.pushState(entry, "", `#${id}`);
  }
  scrollToElement(el);
  highlight(el, entry.marks);
  if (!el.matches("a, button, input, [tabindex]")) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
  history.replaceState({ ...history.state, ...position() }, "");
  // Features can react to a jump that followed a link in the text (the back chip names where Back goes).
  if (back) dispatchEvent(new CustomEvent("reader:jump", { detail: { back } }));
}

// One shared IntersectionObserver for every "do this once when it comes near" (charts, maps, explainers): one pass per
// frame for all targets instead of one observer each, and each target leaves the list after its first use.
const nearCallbacks = new Map();
const nearObserver = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    nearObserver.unobserve(entry.target);
    const callback = nearCallbacks.get(entry.target);
    nearCallbacks.delete(entry.target);
    callback();
  }
}, { rootMargin: "400px 0px" });
function onNear(el, callback) {
  if (nearCallbacks.has(el)) throw new Error("reader.js: onNear called twice for one element");
  nearCallbacks.set(el, callback);
  nearObserver.observe(el);
}

// Overlays: dialogs and popovers that Back closes. Opening one pushes an entry; closing it any other way
// (its button, Escape, a click outside) steps history back over its entry, so entries never pile up.
function isOverlayOpen(el) { return el.matches("dialog") ? el.open : el.matches(":popover-open"); }
function closeOverlayElement(el) {
  if (!isOverlayOpen(el)) return;
  if (el.matches("dialog")) el.close(); else el.hidePopover();
}
function openOverlay(el, show) {
  const here = position(); // Before the overlay covers the page, which would hide the reading position.
  show();
  if (overlayStack.includes(el.id)) return;
  overlayStack = [...overlayStack, el.id];
  history.replaceState({ ...history.state, ...here }, "");
  history.pushState({ ...history.state, overlays: overlayStack, target: null, marks: [], back: null }, "");
}
function overlayClosed(el) {
  const at = overlayStack.indexOf(el.id);
  if (at < 0) return; // Closed by history or by a jump.
  const steps = overlayStack.length - at;
  overlayStack = overlayStack.slice(0, at);
  history.go(-steps);
}
const overlayOpeners = {}; // Overlay ID -> function that shows it again when Forward returns to its entry.
addEventListener("popstate", (e) => {
  const state = e.state ?? {};
  const want = state.overlays ?? [];
  const changed = want.join() !== overlayStack.join();
  const before = overlayStack;
  overlayStack = want;
  for (const id of before.toReversed()) if (!want.includes(id)) closeOverlayElement(byId(id));
  for (const id of want) if (!before.includes(id)) overlayOpeners[id]?.();
  if (changed) return; // Opening or closing an overlay leaves the page where it is.
  const target = state.target && document.getElementById(state.target);
  if (typeof state.y === "number") restorePosition(state);
  else if (target) scrollToElement(target);
  const mark = state.back?.id ? { el: document.getElementById(state.back.id), marks: state.back.marks } : target ? { el: target, marks: state.marks ?? [] } : null;
  if (mark?.el) highlight(mark.el, mark.marks);
});
// Keep the current entry's scroll position up to date, without adding entries.
let positionSave = 0;
addEventListener("scroll", () => {
  clearTimeout(positionSave);
  positionSave = setTimeout(() => {
    // A feature that moves the page on its own (the chapter rail while scrubbing) sets data-scrubbing, so the
    // entry keeps the place the reader started from.
    if (!document.documentElement.hasAttribute("data-scrubbing")) history.replaceState({ ...history.state, ...position() }, "");
  }, 200);
}, { passive: true });
// Exact sizes for skipped documents. content-visibility (02-book.css) lets off-screen chapters skip layout, but then
// the browser places them by an estimate; a wrong estimate moves every position below it (native anchor jumps,
// find-in-page, test tools). So render every document once, measure it, and keep that height as its estimate.
// Again after fonts load and when the width changes. Later changes near the reader (a chart drawing) update by
// themselves, because the estimate is "auto" (the last rendered size).
function sizeDocuments() {
  const root = document.documentElement;
  root.setAttribute("data-sizing", "");
  const docs = [...reading.querySelectorAll(":scope > .doc, :scope > .fx-set")];
  const heights = docs.map((d) => d.getBoundingClientRect().height);
  docs.forEach((d, i) => { d.style.containIntrinsicSize = `auto ${Math.ceil(heights[i])}px`; });
  root.removeAttribute("data-sizing");
}
sizeDocuments();
document.fonts.ready.then(sizeDocuments);
{
  let width = innerWidth, timer = 0;
  addEventListener("resize", () => {
    if (innerWidth === width) return; // Height-only changes (a phone's bar) keep the sizes.
    width = innerWidth;
    clearTimeout(timer);
    timer = setTimeout(sizeDocuments, 300);
  });
}

// Arrival: a reload returns to its saved position; a deep link from outside lands on and highlights its element.
{
  const state = history.state;
  if (typeof state?.y === "number") restorePosition(state);
  else if (location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)))) {
    const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    scrollToElement(el);
    highlight(el);
  }
  history.replaceState({ overlays: [], target: null, marks: [], back: null, ...state, ...position() }, "");
  if (state?.overlays?.length) history.replaceState({ ...history.state, overlays: [] }, ""); // Overlays do not survive a reload.
}
// Any other in-page link (printed contents, cross-links, note back links, bibliography, hero and footer links).
document.addEventListener("click", (e) => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const link = e.target.closest("a[href^='#']");
  const id = link && decodeURIComponent(link.getAttribute("href").slice(1));
  if (!id || !document.getElementById(id)) return;
  e.preventDefault();
  goTo(id, { from: link });
});

