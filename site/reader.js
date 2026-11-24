// Web edition features. Each one works on the EPUB-derived DOM and its stable IDs.
// The page reads fully without this script.

const reading = document.getElementById("read");

function byId(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`reader.js: missing #${id}`);
  return el;
}

function goTo(id) {
  const el = document.getElementById(id);
  if (!el) return;
  history.pushState(null, "", `#${id}`);
  el.scrollIntoView({ block: "start" });
  el.classList.remove("flash");
  void el.offsetWidth; // Restart the highlight animation.
  el.classList.add("flash");
  if (!el.matches("a, button, input, [tabindex]")) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
}

// Navigation bar: solid once the hero leaves the viewport.
const nav = byId("nav");
new IntersectionObserver(([entry]) => {
  nav.toggleAttribute("data-solid", !entry.isIntersecting);
}, { rootMargin: "-96px 0px 0px 0px" }).observe(byId("top")); // Solid before the hero shrinks under the bar.
// The bar's download button shows once the hero's download button is out of view (above the bar).
new IntersectionObserver(([entry]) => {
  nav.toggleAttribute("data-download", !entry.isIntersecting && entry.boundingClientRect.top < innerHeight);
}, { rootMargin: "-64px 0px 0px 0px" }).observe(byId("hero-download"));
// The bar shows the full title when it fits and the author's name when it does not.
const navTitle = nav.querySelector(".nav-title");
const navTitleFull = navTitle.querySelector(".nav-title-full");
new ResizeObserver(() => {
  navTitle.removeAttribute("data-short");
  navTitle.toggleAttribute("data-short", navTitleFull.offsetWidth > navTitle.clientWidth);
}).observe(navTitle);

// E-reader menu: one popover, placed under whichever chevron opened it.
const sendMenu = byId("send-menu");
let menuAnchor = null;
for (const button of document.querySelectorAll("[popovertarget='send-menu']")) {
  button.addEventListener("click", () => { menuAnchor = button; });
}
sendMenu.addEventListener("toggle", (e) => {
  if (e.newState !== "open" || !menuAnchor) return;
  const box = menuAnchor.getBoundingClientRect();
  const width = sendMenu.offsetWidth, height = sendMenu.offsetHeight;
  const rtl = document.dir === "rtl";
  const left = Math.min(innerWidth - width - 8, Math.max(8, rtl ? box.left : box.right - width));
  const below = box.bottom + 6 + height <= innerHeight;
  sendMenu.style.left = `${left}px`;
  sendMenu.style.top = `${below ? box.bottom + 6 : Math.max(8, box.top - 6 - height)}px`;
});

// Dialogs
for (const button of document.querySelectorAll("[data-open]:not([data-open='search-dialog'])")) {
  button.addEventListener("click", () => byId(button.dataset.open).showModal());
}
for (const dialog of document.querySelectorAll("dialog")) {
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog || e.target.closest("[data-close]")) dialog.close();
  });
}
byId("toc-dialog").addEventListener("click", (e) => {
  const link = e.target.closest("a[href^='#']");
  if (!link) return;
  e.preventDefault();
  byId("toc-dialog").close();
  goTo(link.getAttribute("href").slice(1));
});

// Deep links on chapter headings and figures
for (const target of reading.querySelectorAll("section[id] > h2, figure[id] > figcaption")) {
  const id = target.closest("[id]:is(section, figure)").id;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "deep-link";
  button.textContent = "קישור";
  button.setAttribute("aria-label", "העתקת קישור לחלק הזה");
  button.addEventListener("click", async () => {
    const url = new URL(`#${id}`, location.href).href;
    history.replaceState(null, "", `#${id}`);
    try { await navigator.clipboard.writeText(url); button.textContent = "הועתק"; }
    catch { button.textContent = "הקישור בשורת הכתובת"; }
    button.dataset.copied = "";
    setTimeout(() => { button.textContent = "קישור"; delete button.dataset.copied; }, 1800);
  });
  target.append(button);
}

// Figure viewer: shows the site-only original when enhancements.json lists one.
const viewer = byId("figure-dialog");
reading.addEventListener("click", (e) => {
  const img = e.target.closest("figure[id] img");
  if (!img || img.closest(".video")) return; // A video thumbnail starts the player instead.
  const figure = img.closest("figure");
  const original = figure.dataset.original;
  const viewerImg = byId("viewer-img");
  viewerImg.src = original ?? img.currentSrc ?? img.src;
  viewerImg.alt = img.alt;
  byId("viewer-caption").replaceChildren(...[...figure.querySelectorAll("figcaption > *")].map((n) => n.cloneNode(true)));
  const link = byId("viewer-original");
  link.hidden = !original;
  if (original) link.href = original;
  viewer.showModal();
});

// Search. Ranking is BM25 (k1 1.2, b 0.75) over text blocks, with a field boost for headings and captions,
// a bonus when the query words appear as an exact phrase, and a smaller bonus when they appear close together.
// Hebrew: niqqud is ignored, and the one-letter prefixes ו ה ב ל מ ש כ may stand before a query word.
// Every query word must match (AND). The index loads on first use.
const PREFIX_LETTERS = "והבלמשכ";
// A two-letter word like "ים" hides inside many words as prefix + word ("מים" is water, not "from the sea"),
// so short words take only the article and the commonest prepositions. Limit: "מהים" ("from the sea") is missed.
const SHORT_PREFIXES = new Set(["ה", "ב", "ל", "ו", "וה", "וב", "ול"]);
const BOOST = { heading: 2.5, figure: 1.5, text: 1 };
const RECENT_KEY = "eli-raz:recent-searches";

// Token: a run of letters, digits and marks, with geresh and gershayim inside words (צה"ל, ג'ורג').
const TOKEN = /[\p{L}\p{N}\p{M}'"׳״]+/gu;
function normalizeWord(word) {
  let out = "";
  for (const c of word.normalize("NFC")) {
    const cp = c.codePointAt(0);
    if ((cp >= 0x0591 && cp <= 0x05c7) || "'\"׳״".includes(c)) continue;
    out += c;
  }
  return out.toLowerCase();
}
function tokenize(text) {
  const tokens = [];
  for (const m of text.matchAll(TOKEN)) {
    const word = normalizeWord(m[0]);
    if (word) tokens.push({ word, start: m.index, end: m.index + m[0].length });
  }
  return tokens;
}
// How well a word in the book matches a query word: 1 exact, 0.8 after allowed prefixes, 0.5 as the start of a
// longer word (only for the last query word, which may still be typed), 0 no match.
function wordMatch(word, term, last) {
  if (word === term) return 1;
  for (let cut = 1; cut <= 3 && cut < word.length; cut++) {
    const prefix = word.slice(0, cut);
    if (![...prefix].every((c) => PREFIX_LETTERS.includes(c))) break;
    if (word.slice(cut) === term && (term.length > 2 || SHORT_PREFIXES.has(prefix))) return 0.8;
    if (last && term.length >= 3 && word.slice(cut).startsWith(term)) return 0.4;
  }
  if (last && term.length >= 3 && word.startsWith(term)) return 0.5;
  return 0;
}

let searchIndex = null;
async function loadIndex() {
  if (searchIndex) return searchIndex;
  const response = await fetch("search.json");
  if (!response.ok) throw new Error(`search.json: HTTP ${response.status}`);
  const { pages, entries } = await response.json();
  const vocabulary = new Map(); // word -> [entry index, ...] (repeats count as term frequency)
  let totalLength = 0;
  entries.forEach((e, i) => {
    e.loc = i + 1;
    e.tokens = tokenize(e.text);
    totalLength += e.tokens.length;
    for (const t of e.tokens) {
      if (!vocabulary.has(t.word)) vocabulary.set(t.word, []);
      vocabulary.get(t.word).push(i);
    }
  });
  searchIndex = { pages, entries, vocabulary, avgLength: totalLength / entries.length };
  return searchIndex;
}

function rank(index, terms) {
  const { entries, vocabulary, avgLength } = index;
  const N = entries.length;
  // For each query word: entry index -> summed match weight, and the matching vocabulary words.
  const perTerm = terms.map((term, ti) => {
    const weights = new Map(), words = new Map();
    for (const [word, postings] of vocabulary) {
      const w = wordMatch(word, term, ti === terms.length - 1);
      if (!w) continue;
      words.set(word, w);
      for (const i of postings) weights.set(i, (weights.get(i) ?? 0) + w);
    }
    return { weights, words };
  });
  if (perTerm.some((t) => t.weights.size === 0)) return [];
  const [first, ...rest] = perTerm;
  const hits = [];
  for (const [i] of first.weights) {
    if (!rest.every((t) => t.weights.has(i))) continue;
    const e = entries[i];
    let score = 0;
    for (const t of perTerm) {
      const tf = t.weights.get(i), df = t.weights.size;
      const idf = Math.log(1 + (N - df + 0.5) / (df + 0.5));
      score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * e.tokens.length / avgLength));
    }
    score *= BOOST[e.kind];
    // Positions of each query word in this entry, for the phrase and proximity bonus and for highlights.
    const positions = perTerm.map((t) => e.tokens.flatMap((tok, p) => (t.words.has(tok.word) ? [p] : [])));
    let phrase = false, span = Infinity;
    if (terms.length > 1) {
      phrase = positions[0].some((p) => positions.every((list, k) => list.includes(p + k)));
      // Smallest window that holds every query word: walk the first word's positions.
      for (const p of positions[0]) {
        let lo = p, hi = p;
        for (const list of positions.slice(1)) {
          const near = list.reduce((best, q) => (Math.abs(q - p) < Math.abs(best - p) ? q : best), list[0]);
          lo = Math.min(lo, near); hi = Math.max(hi, near);
        }
        span = Math.min(span, hi - lo + 1);
      }
      score *= phrase ? 3 : 1 + 1 / Math.max(1, span - terms.length + 1);
    }
    hits.push({ e, score, phrase, marks: positions.flat().map((p) => e.tokens[p]) });
  }
  // Exact phrase hits first, then by score.
  return hits.sort((a, b) => (b.phrase - a.phrase) || (b.score - a.score));
}

function snippet(e, marks) {
  const frag = document.createDocumentFragment();
  const text = e.text;
  const sorted = marks.toSorted((a, b) => a.start - b.start);
  const from = Math.max(0, (sorted[0]?.start ?? 0) - 50);
  const to = Math.min(text.length, from + 220);
  if (from > 0) frag.append("…");
  let at = from;
  for (const m of sorted) {
    if (m.start < at || m.end > to) continue;
    frag.append(text.slice(at, m.start));
    const mark = document.createElement("mark");
    mark.textContent = text.slice(m.start, m.end);
    frag.append(mark);
    at = m.end;
  }
  frag.append(text.slice(at, to) + (to < text.length ? "…" : ""));
  return frag;
}

// "Go to": a number, "עמ' 123" or "עמוד 123" goes to that printed page; "מיקום 123" goes to that location.
function goToTargets(query, index) {
  const q = query.trim();
  const digits = (s) => (/^\d{1,5}$/.test(s) ? Number(s) : null);
  const out = [];
  let page = digits(q), loc = digits(q);
  const pageWord = ["עמוד", "עמ'", "עמ׳", "עמ"].find((w) => q.startsWith(w));
  const locWord = ["מיקום", "loc"].find((w) => q.startsWith(w));
  if (pageWord) { page = digits(q.slice(pageWord.length).trim()); loc = null; }
  if (locWord) { loc = digits(q.slice(locWord.length).trim()); page = null; }
  if (page !== null && index.pages[String(page)]) out.push({ id: index.pages[String(page)], label: `מעבר לעמוד ${page} בספר המודפס` });
  if (loc !== null && loc >= 1 && loc <= index.entries.length) out.push({ id: index.entries[loc - 1].id, label: `מעבר למיקום ${loc}` });
  return out;
}

function readRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]").filter((q) => typeof q === "string"); }
  catch { return []; }
}
function saveRecent(query) {
  const q = query.trim();
  if (!q) return;
  try { localStorage.setItem(RECENT_KEY, JSON.stringify([q, ...readRecent().filter((x) => x !== q)].slice(0, 6))); }
  catch { /* Private mode or blocked storage: recent searches are a convenience only. */ }
}

const searchDialog = byId("search-dialog");
const input = byId("search-input");
const results = byId("search-results");
const status = byId("search-status");
function resultItem({ href, where, body, thumb, tile, onPick }) {
  const li = document.createElement("li");
  const a = document.createElement("a");
  a.href = href;
  if (thumb) {
    const img = document.createElement("img");
    Object.assign(img, { src: thumb, alt: "", width: 48, height: 48, loading: "lazy", className: "result-thumb" });
    a.append(img);
  } else if (tile) {
    a.append(tile);
  }
  const text = document.createElement("span");
  text.className = "result-text";
  if (where) {
    const w = document.createElement("span");
    w.className = "where";
    w.textContent = where;
    text.append(w);
  }
  text.append(body);
  a.append(text);
  a.addEventListener("click", (e) => { e.preventDefault(); onPick(); });
  li.append(a);
  return li;
}
function placeTile(chapter) {
  const list = placesByChapter.get(chapter);
  if (!list) return null;
  const tile = document.createElement("span");
  tile.className = "result-tile";
  tile.setAttribute("aria-hidden", "true");
  tile.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 0 1 13 0c0 4.8-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/></svg>';
  tile.style.setProperty("--place", `var(--place-${list[0].n})`);
  return tile;
}
function showRecent() {
  results.replaceChildren();
  const recent = readRecent();
  status.textContent = recent.length ? "חיפושים אחרונים" : "";
  for (const q of recent) {
    results.append(resultItem({ href: "#", body: q, onPick: () => { input.value = q; runSearch(); input.focus(); } }));
  }
}
async function runSearch() {
  const query = input.value;
  const terms = tokenize(query).map((t) => t.word);
  if (!query.trim()) { showRecent(); return; }
  const index = await loadIndex();
  if (input.value !== query) return; // A newer query is on its way.
  results.replaceChildren();
  const pick = (id) => { saveRecent(query); searchDialog.close(); goTo(id); };
  const jumps = goToTargets(query, index);
  for (const j of jumps) results.append(resultItem({ href: `#${j.id}`, body: j.label, onPick: () => pick(j.id) }));
  const hits = terms.length ? rank(index, terms) : [];
  status.textContent = hits.length === 0 && jumps.length === 0 ? "לא נמצאו תוצאות" : hits.length === 1 ? "תוצאה אחת" : hits.length ? `${hits.length} תוצאות` : "";
  for (const { e, marks } of hits.slice(0, 80)) {
    const where = [e.section, e.page ? `עמ' ${e.page}` : null, `מיקום ${e.loc}`].filter(Boolean).join(" · ");
    results.append(resultItem({
      href: `#${e.id}`, where, body: snippet(e, marks), thumb: e.thumb,
      tile: e.kind === "heading" ? placeTile(e.chapter) : null, onPick: () => pick(e.id),
    }));
  }
}
function openSearch() {
  searchDialog.showModal();
  input.focus(); // In the same user gesture, so phones raise the keyboard.
  input.select();
  if (!input.value) showRecent();
}
for (const button of document.querySelectorAll("[data-open='search-dialog']")) button.addEventListener("click", openSearch);
let searchTimer = 0;
input.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 100); });
byId("search-form").addEventListener("submit", (e) => { e.preventDefault(); results.querySelector("a")?.click(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !e.target.closest("input, textarea, dialog")) {
    e.preventDefault();
    openSearch();
  }
});

// Videos: a printed QR code that links to YouTube gets a player on the web.
// Nothing loads from YouTube until the reader presses play (privacy and page weight).
function youtubeTarget(href) {
  let url;
  try { url = new URL(href); } catch { return null; }
  if (url.hostname !== "www.youtube.com" && url.hostname !== "youtube.com") return null;
  const id = url.searchParams.get("v");
  if (!id || !/^[\w-]{11}$/.test(id)) return null;
  const start = Number.parseInt(url.searchParams.get("t") ?? "0", 10);
  return { id, start: Number.isFinite(start) ? start : 0 };
}
for (const link of reading.querySelectorAll("figure a.qr-link")) {
  const target = youtubeTarget(link.href);
  if (!target) continue;
  const figure = link.closest("figure");
  const label = figure.querySelector("figcaption .caption")?.textContent.trim() || "סרטון";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "video-play";
  button.setAttribute("aria-label", `הפעלת הסרטון: ${label}`);
  const thumb = document.createElement("img");
  thumb.src = `https://i.ytimg.com/vi/${target.id}/hqdefault.jpg`;
  thumb.alt = "";
  thumb.loading = "lazy";
  const icon = document.createElement("span");
  icon.className = "video-icon";
  icon.setAttribute("aria-hidden", "true");
  button.append(thumb, icon);
  const box = document.createElement("div");
  box.className = "video";
  box.append(button);
  button.addEventListener("click", () => {
    const frame = document.createElement("iframe");
    frame.src = `https://www.youtube-nocookie.com/embed/${target.id}?autoplay=1&start=${target.start}`;
    frame.title = label;
    frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    frame.allowFullscreen = true;
    box.replaceChildren(frame);
    frame.focus();
  });
  figure.classList.add("has-video");
  figure.insertBefore(box, figure.querySelector("figcaption"));
}

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
  const showHint = (text) => {
    hint.textContent = text;
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

// Places map, right after the printed contents. The numbered list under it works without JavaScript.
const placesMap = document.getElementById("places-map");
const places = placesMap ? JSON.parse(byId("places-data").textContent) : [];
const placeById = new Map(places.map((p) => [p.id, p]));
let placesReady = null;
function placePopup(p, map) {
  const box = document.createElement("div");
  box.className = "map-popup";
  box.style.setProperty("--place", `var(--place-${p.n})`);
  box.style.setProperty("--ink", `var(--place-ink-${p.n})`);
  const title = document.createElement("strong");
  const badge = document.createElement("span");
  badge.className = "place-n";
  badge.textContent = p.n;
  title.append(badge, p.name);
  const text = document.createElement("p");
  const source = document.createElement("a");
  source.href = p.source;
  source.textContent = "מתוך הספר";
  text.append(`${p.description} `, source);
  const chapters = document.createElement("ul");
  for (const c of p.chapters) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = c.href;
    a.textContent = c.title;
    li.append(a);
    chapters.append(li);
  }
  box.append(title, text, chapters);
  if (p.figures.length) {
    const thumbs = document.createElement("div");
    thumbs.className = "thumbs";
    for (const f of p.figures) {
      const a = document.createElement("a");
      a.href = f.href;
      const img = document.createElement("img");
      Object.assign(img, { src: f.thumb, alt: f.alt, width: 64, height: 64, loading: "lazy" });
      a.append(img);
      thumbs.append(a);
    }
    box.append(thumbs);
  }
  box.addEventListener("click", (e) => {
    const link = e.target.closest("a[href^='#']");
    if (!link) return;
    e.preventDefault();
    map.closePopup();
    goTo(link.getAttribute("href").slice(1));
  });
  return box;
}
if (placesMap) {
  placesReady = whenNear(byId("places"), () => { // The map box is hidden until drawn, so watch its section.
    placesMap.hidden = false;
    const map = makeMap(placesMap);
    const markers = new Map();
    for (const p of places) {
      const icon = L.divIcon({ className: "", iconSize: [24, 24], iconAnchor: [12, 12], popupAnchor: [0, -12],
        html: `<div class="place-marker" style="--place: var(--place-${p.n}); --ink: var(--place-ink-${p.n}); width: 24px; height: 24px">${p.n}</div>` });
      const marker = L.marker([p.lat, p.lon], { icon, title: p.name, alt: p.name, riseOnHover: true })
        .bindPopup(() => placePopup(p, map), { maxWidth: 300 })
        .bindTooltip(p.name, { direction: "top", offset: [0, -12] })
        .addTo(map);
      markers.set(p.id, marker);
    }
    // Fit the first view to the places near the median, so one far place (a mountain abroad) does not shrink the rest.
    const median = (values) => values.toSorted((a, b) => a - b)[Math.floor(values.length / 2)];
    const middle = L.latLng(median(places.map((p) => p.lat)), median(places.map((p) => p.lon)));
    const near = places.filter((p) => middle.distanceTo([p.lat, p.lon]) < 120_000);
    map.fitBounds(L.latLngBounds(near.map((p) => [p.lat, p.lon])).pad(0.08));
    return { map, markers };
  });
  placesReady.catch((err) => { placesMap.hidden = true; console.error(err); });
  byId("places").querySelector(".places-list").setAttribute("data-live", "");
}
// Show one place: scroll the map into view, centre it and open its popup.
async function openPlace(id) {
  const p = placeById.get(id);
  if (!p) throw new Error(`reader.js: unknown place ${id}`);
  byId("places").scrollIntoView({ block: "start" });
  // The map draws when it comes near the viewport; scrolling there triggers it.
  const { map, markers } = await placesReady;
  map.setView([p.lat, p.lon], Math.max(map.getZoom(), 11), { animate: false });
  markers.get(id).openPopup();
}
// The numbered list: each name opens its place on the map.
for (const li of document.querySelectorAll(".places-list[data-live] li")) {
  const name = li.querySelector(".place-name");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "place-name";
  button.textContent = name.textContent;
  button.addEventListener("click", () => openPlace(li.id.slice("place-".length)));
  name.replaceWith(button);
}
// Printed contents: a dot per place after each chapter that has places; the dots open pills that open the map.
const placesByChapter = new Map();
for (const p of places) for (const c of p.chapters) {
  if (!placesByChapter.has(c.chapter)) placesByChapter.set(c.chapter, []);
  if (!placesByChapter.get(c.chapter).includes(p)) placesByChapter.get(c.chapter).push(p);
}
for (const [chapter, list] of placesByChapter) {
  for (const link of reading.querySelectorAll(`ol.contents a[href="#${CSS.escape(chapter)}"]`)) {
    const li = link.closest("li");
    const dots = document.createElement("button");
    dots.type = "button";
    dots.className = "place-dots";
    dots.setAttribute("aria-expanded", "false");
    dots.setAttribute("aria-label", `מקומות בפרק: ${list.map((p) => p.name).join(", ")}`);
    const pills = document.createElement("div");
    pills.className = "place-pills";
    pills.hidden = true;
    for (const p of list) {
      const dot = document.createElement("i");
      dot.style.setProperty("--place", `var(--place-${p.n})`);
      dots.append(dot);
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "place-pill";
      pill.style.setProperty("--place", `var(--place-${p.n})`);
      pill.append(document.createElement("i"), p.name);
      pill.addEventListener("click", () => openPlace(p.id));
      pills.append(pill);
    }
    dots.addEventListener("click", () => {
      pills.hidden = !pills.hidden;
      dots.setAttribute("aria-expanded", String(!pills.hidden));
    });
    li.append(dots, pills);
  }
}

// Data tables: a header button sorts by its column; a second press reverses the order.
for (const table of reading.querySelectorAll("table.data-table")) {
  const body = table.tBodies[0];
  for (const button of table.querySelectorAll("button[data-sort]")) {
    button.addEventListener("click", () => {
      const col = Number(button.dataset.sort);
      const th = button.parentElement;
      const descending = th.getAttribute("aria-sort") !== "descending";
      for (const other of table.querySelectorAll("th[aria-sort]")) other.removeAttribute("aria-sort");
      th.setAttribute("aria-sort", descending ? "descending" : "ascending");
      const key = (row) => {
        const cell = row.children[col];
        return cell.dataset.value !== undefined ? Number(cell.dataset.value) : cell.textContent.trim();
      };
      const rows = [...body.rows].sort((a, b) => {
        const x = key(a), y = key(b);
        const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "he");
        return descending ? -order : order;
      });
      body.append(...rows);
    });
  }
}

// Live charts: one line, one axis, crosshair and tooltip on pointer and keyboard. The yearly table is the fallback.
const MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];
const SVG = "http://www.w3.org/2000/svg";
function svg(tag, attrs, parent) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  parent?.append(el);
  return el;
}
async function drawChart(figure) {
  const response = await fetch(figure.dataset.chart);
  if (!response.ok) throw new Error(`${figure.dataset.chart}: HTTP ${response.status}`);
  const { points } = await response.json();
  const data = points.map(([d, v]) => ({ t: Date.parse(d), d, v }));
  const area = figure.querySelector(".chart-area");
  area.hidden = false;
  // Draw at the real width, so labels keep their size on a phone; redraw when the width changes.
  let width = 0;
  new ResizeObserver(() => {
    if (area.clientWidth === width) return;
    width = area.clientWidth;
    renderChart(figure, area, data, width);
  }).observe(area);
}
function renderChart(figure, area, data, width) {
  const W = Math.max(280, width), H = Math.round(Math.min(360, Math.max(220, W * 0.5)));
  const M = { top: 16, right: 12, bottom: 30, left: 52 };
  const t0 = data[0].t, t1 = data.at(-1).t;
  const vMin = Math.floor(Math.min(...data.map((p) => p.v)) / 10) * 10;
  const vMax = Math.ceil(Math.max(...data.map((p) => p.v)) / 10) * 10;
  const x = (t) => M.left + ((t - t0) / (t1 - t0)) * (W - M.left - M.right);
  const y = (v) => M.top + ((vMax - v) / (vMax - vMin)) * (H - M.top - M.bottom);
  const unit = figure.dataset.unit;
  // Unicode minus, isolated left to right, so "-441.53" never shows as "441.53-" inside Hebrew text.
  const num = (v, digits = 0) => `\u2066${v < 0 ? "\u2212" : ""}${Math.abs(v).toFixed(digits)}\u2069`;
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", tabindex: "0",
    "aria-label": `${unit}: ${num(data[0].v, 2)} ב־${data[0].d.slice(0, 4)}, ${num(data.at(-1).v, 2)} ב־${data.at(-1).d.slice(0, 4)}. החצים עוברים בין המדידות.` });
  root.setAttribute("dir", "ltr");
  for (let v = vMin; v <= vMax; v += 10) {
    svg("line", { x1: M.left, x2: W - M.right, y1: y(v), y2: y(v), class: "grid" }, root);
    svg("text", { x: M.left - 8, y: y(v), class: "tick", "text-anchor": "end", "dominant-baseline": "middle" }, root).textContent = num(v);
  }
  const yearStep = W < 480 ? 20 : 10;
  for (let year = Math.ceil(new Date(t0).getUTCFullYear() / yearStep) * yearStep; Date.UTC(year, 0) <= t1; year += yearStep) {
    svg("text", { x: x(Date.UTC(year, 0)), y: H - 8, class: "tick", "text-anchor": "middle" }, root).textContent = year;
  }
  svg("path", { d: data.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(""), class: "line" }, root);
  const cross = svg("line", { y1: M.top, y2: H - M.bottom, class: "cross", visibility: "hidden" }, root);
  const dot = svg("circle", { r: 5, class: "dot", visibility: "hidden" }, root);
  const tip = document.createElement("div");
  tip.className = "chart-tip";
  tip.hidden = true;
  tip.setAttribute("aria-live", "polite");
  let current = data.length - 1;
  const show = (i) => {
    current = Math.max(0, Math.min(data.length - 1, i));
    const p = data[current];
    for (const el of [cross, dot]) el.setAttribute("visibility", "visible");
    cross.setAttribute("x1", x(p.t)); cross.setAttribute("x2", x(p.t));
    dot.setAttribute("cx", x(p.t)); dot.setAttribute("cy", y(p.v));
    const [yy, mm] = p.d.split("-");
    tip.textContent = `${MONTHS[Number(mm) - 1]} ${yy}: ${num(p.v, 2)} מטר`;
    tip.hidden = false;
    const box = root.getBoundingClientRect();
    tip.style.left = `${(x(p.t) / W) * box.width}px`;
    tip.style.top = `${(y(p.v) / H) * box.height}px`;
  };
  const hide = () => { for (const el of [cross, dot]) el.setAttribute("visibility", "hidden"); tip.hidden = true; };
  root.addEventListener("pointermove", (e) => {
    const box = root.getBoundingClientRect();
    const t = t0 + (((e.clientX - box.left) / box.width) * W - M.left) / (W - M.left - M.right) * (t1 - t0);
    let best = 0;
    for (let i = 1; i < data.length; i++) if (Math.abs(data[i].t - t) < Math.abs(data[best].t - t)) best = i;
    show(best);
  });
  root.addEventListener("pointerleave", hide);
  root.addEventListener("focus", () => show(current));
  root.addEventListener("blur", hide);
  root.addEventListener("keydown", (e) => {
    const step = { ArrowLeft: -1, ArrowRight: 1, PageDown: -12, PageUp: 12 }[e.key];
    if (step === undefined && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    show(e.key === "Home" ? 0 : e.key === "End" ? data.length - 1 : current + step);
  });
  area.replaceChildren(root, tip);
}
for (const figure of reading.querySelectorAll("figure.web-chart[data-chart]")) {
  new IntersectionObserver((entries, observer) => {
    if (!entries[0].isIntersecting) return;
    observer.disconnect();
    drawChart(figure).catch((err) => console.error(err));
  }, { rootMargin: "300px" }).observe(figure);
}
