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
const onDialogOpen = {}; // Dialog ID -> function run right after it opens.
for (const button of document.querySelectorAll("[data-open]:not([data-open='search-dialog'])")) {
  button.addEventListener("click", () => {
    byId(button.dataset.open).showModal();
    onDialogOpen[button.dataset.open]?.();
  });
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

// Navigator: chapters (with a filter) and, when the book has one, a timeline tab.
const tocDialog = byId("toc-dialog");
const tabs = [...tocDialog.querySelectorAll("[role='tab']")];
function selectTab(tab) {
  for (const t of tabs) {
    const on = t === tab;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    byId(t.getAttribute("aria-controls")).hidden = !on;
  }
}
for (const tab of tabs) {
  tab.addEventListener("click", () => selectTab(tab));
  tab.addEventListener("keydown", (e) => {
    const step = { ArrowLeft: 1, ArrowRight: -1 }[e.key]; // Right to left: the next tab is on the left.
    if (!step) return;
    const next = tabs[(tabs.indexOf(tab) + (document.dir === "rtl" ? step : -step) + tabs.length) % tabs.length];
    selectTab(next);
    next.focus();
  });
}
const tocFilter = byId("toc-filter");
byId("toc-filter-form").addEventListener("submit", (e) => {
  e.preventDefault();
  tocDialog.querySelector(".toc-item:not([hidden]) a")?.click();
});
tocFilter.addEventListener("input", () => {
  const words = tokenize(tocFilter.value).map((t) => t.word);
  const matches = (el) => {
    const text = tokenize(el.textContent).map((t) => t.word).join(" ");
    return words.every((w) => text.includes(w));
  };
  let shown = 0;
  for (const part of tocDialog.querySelectorAll(".toc-part")) part.hidden = false;
  for (const item of tocDialog.querySelectorAll(".toc-item")) {
    const part = item.closest(".toc-part");
    item.hidden = !(matches(item) || (part && matches(part.querySelector(".toc-part-title"))));
    if (!item.hidden) shown++;
  }
  for (const part of tocDialog.querySelectorAll(".toc-part")) {
    part.hidden = !part.querySelector(".toc-item:not([hidden])") && !matches(part.querySelector(".toc-part-title"));
  }
  byId("toc-empty").hidden = shown > 0;
});
onDialogOpen["toc-dialog"] = () => {
  // The current chapter: the last top-level section that starts above a third of the screen.
  let current = null;
  for (const section of reading.querySelectorAll(".doc > section[id]")) {
    if (section.getBoundingClientRect().top < innerHeight / 3) current = section.id;
    else break;
  }
  for (const link of tocDialog.querySelectorAll("[aria-current]")) link.removeAttribute("aria-current");
  const link = current && tocDialog.querySelector(`[data-chapter="${CSS.escape(current)}"] > a`);
  if (link) {
    link.setAttribute("aria-current", "location");
    if (tabs[0].getAttribute("aria-selected") === "true") link.scrollIntoView({ block: "center" });
  }
};

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
        .bindPopup(() => placePopup(p, map), { maxWidth: Math.min(300, placesMap.clientWidth - 80), autoPanPadding: [16, 16] })
        .bindTooltip(p.name, { direction: "top", offset: [0, -12] })
        .addTo(map);
      markers.set(p.id, marker);
    }
    // The first view holds the book's core region: the places within 110 km of the median place.
    // Places outside it stay on the map; a place marked "far" (abroad) also gets a chip that flies there.
    const near = places.filter((p) => !p.far);
    const median = (values) => values.toSorted((a, b) => a - b)[Math.floor(values.length / 2)];
    const middle = L.latLng(median(near.map((p) => p.lat)), median(near.map((p) => p.lon)));
    const core = near.filter((p) => middle.distanceTo([p.lat, p.lon]) < 110_000);
    const home = L.latLngBounds(core.map((p) => [p.lat, p.lon])).pad(0.05);
    map.fitBounds(home);
    const far = places.filter((p) => p.far);
    if (far.length) {
      const Far = L.Control.extend({ options: { position: "bottomleft" }, onAdd() {
        const box = L.DomUtil.create("div", "map-chips");
        L.DomEvent.disableClickPropagation(box);
        const back = document.createElement("button");
        back.type = "button";
        back.textContent = "חזרה לתצוגה הראשונה";
        back.hidden = true;
        back.addEventListener("click", () => { map.fitBounds(home); back.hidden = true; });
        for (const p of far) {
          const chip = document.createElement("button");
          chip.type = "button";
          chip.style.setProperty("--place", `var(--place-${p.n})`);
          chip.append(document.createElement("i"), `רחוק מכאן: ${p.name}`);
          chip.addEventListener("click", () => { map.setView([p.lat, p.lon], 9); markers.get(p.id).openPopup(); back.hidden = false; });
          box.append(chip);
        }
        box.append(back);
        return box;
      } });
      new Far().addTo(map);
    }
    // Markers closer than a marker's width push each other apart a little, so each stays visible and tappable.
    // The popup and tooltip keep the true position. Limit: a dense group at a far zoom spreads into a small cloud;
    // zooming in brings every marker back to its true spot.
    const declutter = () => {
      const items = [...markers.values()].map((m) => {
        const at = map.latLngToContainerPoint(m.getLatLng());
        return { m, x: at.x, y: at.y, x0: at.x, y0: at.y };
      });
      const gap = 25;
      for (let round = 0; round < 60; round++) {
        let moved = false;
        for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
          const a = items[i], b = items[j];
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
      for (const it of items) it.m.getElement().style.translate = `${(it.x - it.x0).toFixed(1)}px ${(it.y - it.y0).toFixed(1)}px`;
    };
    map.on("zoomend", declutter);
    declutter();
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
  const item = tocDialog.querySelector(`.toc-item[data-chapter="${CSS.escape(chapter)}"] > a`);
  if (item) {
    const dots = document.createElement("span");
    dots.className = "toc-places";
    dots.title = list.map((p) => p.name).join(", ");
    dots.setAttribute("aria-hidden", "true");
    for (const p of list) {
      const dot = document.createElement("i");
      dot.style.setProperty("--place", `var(--place-${p.n})`);
      dots.append(dot);
    }
    item.append(dots);
  }
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

// Charts. One renderer for every chart file: line and point series, one y axis per panel, bands and markers.
// Panels of one figure share the x axis and stack (small multiples), never two y axes on one chart.
// Pointer and keyboard show a crosshair and the value; the tables and the CSV file are the text version.
const MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];
const SVG = "http://www.w3.org/2000/svg";
function svg(tag, attrs, parent) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  parent?.append(el);
  return el;
}
// Unicode minus, isolated left to right, so "-441.53" never shows as "441.53-" inside Hebrew text.
const num = (v, digits = 0) => `⁦${v < 0 ? "−" : ""}${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })}⁩`;
const digitsFor = (step) => Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
// Round ticks. A tight axis keeps the data extent as its ends (x); otherwise the ends round out to a tick (y).
function niceTicks(lo, hi, target, tight = false) {
  const raw = (hi - lo) / target || 1;
  const p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].find((m) => m * p >= raw) * p;
  const first = tight ? Math.ceil(lo / step) * step : Math.floor(lo / step) * step;
  const last = tight ? Math.floor(hi / step) * step : Math.ceil(hi / step) * step;
  const ticks = [];
  for (let v = first; v <= last + step / 1e6; v += step) ticks.push(Number(v.toFixed(10)));
  return { ticks, step, lo: tight ? lo : first, hi: tight ? hi : last };
}
const dateToYear = (d) => {
  const [y, m, day] = d.split("-").map(Number);
  return y + (Date.UTC(y, m - 1, day) - Date.UTC(y, 0, 1)) / (365.25 * 864e5);
};
function prepare(panel) {
  const xOf = panel.x.type === "date" ? dateToYear : (x) => x;
  return { ...panel, series: panel.series.map((s) => ({ ...s, pts: s.points.map(([x, y]) => ({ x: xOf(x), y, raw: x })) })) };
}
function formatX(panel, p, step) {
  if (panel.x.type === "date") { const [y, m] = p.raw.split("-"); return `${MONTHS[Number(m) - 1]} ${y}`; }
  if (panel.x.type === "year") return String(p.raw);
  return `${num(p.raw, Number.isInteger(p.raw) ? 0 : Math.min(2, digitsFor(step) + 1))}${panel.x.unit ? ` ${panel.x.unit}` : ""}`;
}
function markerList(markers) {
  const list = document.createElement("ol");
  list.className = "chart-markers";
  markers.forEach((m) => {
    const li = document.createElement("li");
    // A label may end with the ID of the paragraph that states it, in brackets: link it.
    const open = m.label.lastIndexOf("(");
    const id = m.label.endsWith(")") && open >= 0 ? m.label.slice(open + 1, -1) : "";
    if (id && document.getElementById(id)) {
      const a = document.createElement("a");
      a.href = `#${id}`;
      a.textContent = "בספר";
      a.addEventListener("click", (e) => { e.preventDefault(); goTo(id); });
      li.append(m.label.slice(0, open).trim(), " (", a, ")");
    } else {
      li.textContent = m.label;
    }
    list.append(li);
  });
  return list;
}
function drawFigureChart(area, panels, width) {
  const shared = panels.length > 1;
  const allX = panels.flatMap((p) => p.series.flatMap((s) => s.pts.map((pt) => pt.x)));
  const xt = niceTicks(Math.min(...allX), Math.max(...allX), width < 480 ? 4 : 7, true);
  const W = Math.max(280, width);
  const M = { top: 14, right: 16, bottom: 30, left: 58 };
  const x = (v) => M.left + ((v - xt.lo) / (xt.hi - xt.lo)) * (W - M.left - M.right);
  const views = [];
  const nodes = [];
  panels.forEach((panel, pi) => {
    const H = Math.round(Math.min(shared ? 260 : 360, Math.max(shared ? 170 : 220, W * (shared ? 0.34 : 0.5))));
    const allY = panel.series.flatMap((s) => s.pts.map((pt) => pt.y)).concat(panel.markers.filter((m) => m.axis === "y").map((m) => m.at));
    const yt = niceTicks(Math.min(...allY), Math.max(...allY), 5);
    const y = (v) => M.top + ((yt.hi - v) / (yt.hi - yt.lo)) * (H - M.top - M.bottom);
    const head = document.createElement("div");
    head.className = "chart-head";
    const title = document.createElement("p");
    title.className = "chart-axis-title";
    title.textContent = `${panel.y.label}${panel.y.unit ? ` (${panel.y.unit})` : ""}`;
    head.append(title);
    if (panel.series.length > 1) {
      const legend = document.createElement("ul");
      legend.className = "chart-legend";
      panel.series.forEach((s, si) => {
        const li = document.createElement("li");
        li.innerHTML = `<i class="key s${si + 1} ${s.kind}"></i>`;
        li.append(s.name);
        legend.append(li);
      });
      head.append(legend);
    }
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", tabindex: "0", dir: "ltr" });
    const first = panel.series[0].pts;
    root.setAttribute("aria-label", `${panel.title}. ${panel.series.length} סדרות, ${first.length} נקודות בראשונה. החצים עוברים בין הנקודות.`);
    for (const b of panel.bands) {
      const [a, z] = b.axis === "x" ? [x(b.from), x(b.to)] : [y(b.to), y(b.from)];
      const rect = b.axis === "x" ? { x: a, width: z - a, y: M.top, height: H - M.top - M.bottom } : { y: a, height: z - a, x: M.left, width: W - M.left - M.right };
      svg("rect", { ...rect, class: "band" }, root);
      if (b.axis === "x") svg("text", { x: (a + z) / 2, y: M.top + 12, class: "band-label", "text-anchor": "middle" }, root).textContent = b.label;
    }
    for (const v of yt.ticks) {
      svg("line", { x1: M.left, x2: W - M.right, y1: y(v), y2: y(v), class: "grid" }, root);
      svg("text", { x: M.left - 8, y: y(v), class: "tick", "text-anchor": "end", "dominant-baseline": "middle" }, root).textContent = num(v, digitsFor(yt.step));
    }
    if (!shared || pi === panels.length - 1) {
      for (const v of xt.ticks) svg("text", { x: x(v), y: H - 8, class: "tick", "text-anchor": "middle" }, root).textContent = panel.x.type === "number" ? num(v, digitsFor(xt.step)) : String(v);
    }
    panel.markers.forEach((m, mi) => {
      const line = m.axis === "x" ? { x1: x(m.at), x2: x(m.at), y1: M.top, y2: H - M.bottom } : { x1: M.left, x2: W - M.right, y1: y(m.at), y2: y(m.at) };
      svg("line", { ...line, class: "marker" }, root);
      const at = m.axis === "x" ? { cx: x(m.at), cy: H - M.bottom - 9 } : { cx: W - M.right - 8, cy: y(m.at) };
      svg("circle", { ...at, r: 8, class: "marker-badge" }, root);
      svg("text", { x: at.cx, y: at.cy, class: "marker-n", "text-anchor": "middle", "dominant-baseline": "central" }, root).textContent = mi + 1;
    });
    panel.series.forEach((s, si) => {
      if (s.kind === "line") {
        svg("path", { d: s.pts.map((p, i) => `${i ? "L" : "M"}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`).join(""), class: `line s${si + 1}` }, root);
      } else {
        for (const p of s.pts) svg("circle", { cx: x(p.x).toFixed(1), cy: y(p.y).toFixed(1), r: 2.6, class: `pt s${si + 1}` }, root);
      }
    });
    // Direct labels at the end of each line when there is more than one series.
    if (panel.series.length > 1) {
      panel.series.forEach((s, si) => {
        if (s.kind !== "line") return;
        const last = s.pts.at(-1);
        svg("text", { x: Math.min(x(last.x), W - M.right) - 4, y: y(last.y) - 8, class: `direct s${si + 1}`, "text-anchor": "end" }, root).textContent = s.name;
      });
    }
    const cross = svg("line", { y1: M.top, y2: H - M.bottom, class: "cross", visibility: "hidden" }, root);
    const dot = svg("circle", { r: 5, class: "dot", visibility: "hidden" }, root);
    const box = document.createElement("div");
    box.className = "chart-panel";
    const plot = document.createElement("div");
    plot.className = "chart-plot";
    const tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    tip.setAttribute("aria-live", "polite");
    plot.append(root, tip);
    box.append(head, plot);
    if (!shared || pi === panels.length - 1) {
      const xl = document.createElement("p");
      xl.className = "chart-x-title";
      xl.textContent = `${panel.x.label}${panel.x.unit ? ` (${panel.x.unit})` : ""}`;
      box.append(xl);
    }
    if (panel.markers.length) box.append(markerList(panel.markers));
    nodes.push(box);
    views.push({ panel, root, tip, cross, dot, x, y, W, H, xt });
  });
  // Hover and keyboard. Small multiples follow the pointer's x in every panel; a single panel takes the nearest point.
  let current = { si: 0, i: views[0].panel.series[0].pts.length - 1 };
  const showPoint = (v, si, i) => {
    const s = v.panel.series[si], p = s.pts[i];
    for (const el of [v.cross, v.dot]) el.setAttribute("visibility", "visible");
    v.cross.setAttribute("x1", v.x(p.x)); v.cross.setAttribute("x2", v.x(p.x));
    v.dot.setAttribute("cx", v.x(p.x)); v.dot.setAttribute("cy", v.y(p.y));
    v.dot.setAttribute("class", `dot s${si + 1}`);
    const unit = v.panel.y.unit ? ` ${v.panel.y.unit}` : "";
    const digits = s.pts.every((q) => Number.isInteger(q.y)) ? 0 : Math.abs(p.y) < 10 ? 2 : 1;
    v.tip.textContent = `${v.panel.series.length > 1 ? `${s.name}: ` : ""}${formatX(v.panel, p, v.xt.step)} · ${num(p.y, digits)}${unit}`;
    v.tip.hidden = false;
    const r = v.root.getBoundingClientRect();
    v.tip.style.left = `${(v.x(p.x) / v.W) * r.width}px`;
    v.tip.style.top = `${(v.y(p.y) / v.H) * r.height}px`;
  };
  const hideAll = () => { for (const v of views) { for (const el of [v.cross, v.dot]) el.setAttribute("visibility", "hidden"); v.tip.hidden = true; } };
  const nearestByX = (pts, xv) => pts.reduce((b, p, i) => (Math.abs(p.x - xv) < Math.abs(pts[b].x - xv) ? i : b), 0);
  views.forEach((v) => {
    v.root.addEventListener("pointermove", (e) => {
      const r = v.root.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * v.W, py = ((e.clientY - r.top) / r.height) * v.H;
      if (shared) {
        const xv = v.xt.lo + ((px - v.x(v.xt.lo)) / (v.x(v.xt.hi) - v.x(v.xt.lo))) * (v.xt.hi - v.xt.lo);
        for (const w of views) showPoint(w, 0, nearestByX(w.panel.series[0].pts, xv));
        return;
      }
      let best = null;
      v.panel.series.forEach((s, si) => s.pts.forEach((p, i) => {
        const d = Math.hypot(v.x(p.x) - px, v.y(p.y) - py);
        if (!best || d < best.d) best = { d, si, i };
      }));
      current = best;
      showPoint(v, best.si, best.i);
    });
    v.root.addEventListener("pointerleave", hideAll);
    v.root.addEventListener("focus", () => showPoint(v, Math.min(current.si, v.panel.series.length - 1), Math.min(current.i, v.panel.series[Math.min(current.si, v.panel.series.length - 1)].pts.length - 1)));
    v.root.addEventListener("blur", hideAll);
    v.root.addEventListener("keydown", (e) => {
      const n = v.panel.series.length;
      let { si, i } = current;
      si = Math.min(si, n - 1);
      const len = v.panel.series[si].pts.length;
      const big = Math.max(1, Math.round(len / 20));
      const moves = { ArrowLeft: -1, ArrowRight: 1, PageDown: -big, PageUp: big };
      if (e.key in moves) i += moves[e.key];
      else if (e.key === "Home") i = 0;
      else if (e.key === "End") i = len - 1;
      else if (e.key === "ArrowUp" || e.key === "ArrowDown") { si = (si + (e.key === "ArrowUp" ? 1 : n - 1)) % n; i = Math.min(i, v.panel.series[si].pts.length - 1); }
      else return;
      e.preventDefault();
      current = { si, i: Math.max(0, Math.min(v.panel.series[si].pts.length - 1, i)) };
      showPoint(v, current.si, current.i);
    });
  });
  area.replaceChildren(...nodes);
}
async function setUpChart(figure) {
  const box = figure.querySelector(".chart-box");
  const response = await fetch(box.dataset.chart);
  if (!response.ok) throw new Error(`${box.dataset.chart}: HTTP ${response.status}`);
  const panels = (await response.json()).panels.map(prepare);
  const area = box.querySelector(".chart-area");
  area.hidden = false;
  // Draw at the real width, so labels keep their size on a phone; redraw when the width changes.
  let width = 0;
  new ResizeObserver(() => {
    if (area.clientWidth === width || area.clientWidth === 0) return;
    width = area.clientWidth;
    drawFigureChart(area, panels, width);
  }).observe(area);
}
// Toggle between the interactive chart and the printed image. The chart shows first.
for (const figure of reading.querySelectorAll("figure.has-chart")) {
  const img = figure.querySelector(":scope > img");
  const group = document.createElement("div");
  group.className = "view-toggle";
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "תצוגת האיור");
  const make = (label, chart) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.addEventListener("click", () => setView(chart));
    group.append(b);
    return b;
  };
  const chartButton = make("גרף אינטראקטיבי", true);
  const printButton = make("האיור המודפס", false);
  const setView = (chart) => {
    chartButton.setAttribute("aria-pressed", String(chart));
    printButton.setAttribute("aria-pressed", String(!chart));
    figure.querySelector(".chart-box").hidden = !chart;
    if (img) img.hidden = chart;
  };
  figure.prepend(group);
  setView(true);
  new IntersectionObserver((entries, observer) => {
    if (!entries[0].isIntersecting) return;
    observer.disconnect();
    setUpChart(figure).catch((err) => { setView(false); group.remove(); console.error(err); });
  }, { rootMargin: "300px" }).observe(figure);
}

// Footnotes and glossary terms open in a popover: on hover with a mouse, on tap, click or Enter otherwise.
// The browser handles light dismiss and Escape (popover attribute).
const notePop = byId("note-popover");
const termPop = byId("term-popover");
const glossary = JSON.parse(document.getElementById("glossary-data")?.textContent ?? "[]");
function placePopover(pop, anchor) {
  const box = anchor.getBoundingClientRect();
  const width = pop.offsetWidth, height = pop.offsetHeight;
  const left = Math.min(innerWidth - width - 8, Math.max(8, box.left + box.width / 2 - width / 2));
  const below = box.bottom + 8 + height <= innerHeight || box.top - 8 - height < 0;
  pop.style.left = `${left}px`;
  pop.style.top = `${below ? box.bottom + 8 : box.top - 8 - height}px`;
}
function openPopover(pop, anchor, content) {
  pop.replaceChildren(...content);
  if (!pop.matches(":popover-open")) pop.showPopover();
  placePopover(pop, anchor);
}
function goLink(href, label, pop) {
  const go = document.createElement("a");
  go.href = href;
  go.className = "pop-go";
  go.setAttribute("aria-label", label);
  go.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5m0 0 6-6m-6 6 6 6"/></svg>';
  if (document.dir === "ltr") go.querySelector("svg").style.transform = "scaleX(-1)";
  go.addEventListener("click", (e) => { e.preventDefault(); pop.hidePopover(); goTo(href.slice(1)); });
  return go;
}
function noteContent(ref) {
  const note = document.getElementById(ref.getAttribute("href").slice(1));
  if (!note) throw new Error(`reader.js: note ${ref.getAttribute("href")} is missing`);
  const body = document.createElement("div");
  body.className = "pop-body";
  for (const child of note.cloneNode(true).children) body.append(child);
  for (const el of body.querySelectorAll("[id]")) el.removeAttribute("id");
  for (const back of body.querySelectorAll("a[role='doc-backlink']")) back.remove();
  if (note.lang) { body.lang = note.lang; body.dir = note.dir || "auto"; }
  return [body, goLink(`#${note.id}`, "מעבר להערה בגוף הפרק", notePop)];
}
function termContent(button) {
  const t = glossary[Number(button.dataset.term)];
  if (!t) throw new Error(`reader.js: glossary term ${button.dataset.term} is missing`);
  const body = document.createElement("div");
  body.className = "pop-body";
  const name = document.createElement("strong");
  name.textContent = t.term;
  const text = document.createElement("p");
  text.textContent = t.definition;
  body.append(name, text);
  return [body, goLink(t.source, "מעבר למקור ההגדרה בספר", termPop)];
}
reading.addEventListener("click", (e) => {
  const ref = e.target.closest("a[role='doc-noteref']");
  if (ref) {
    e.preventDefault();
    openPopover(notePop, ref, noteContent(ref));
    if (e.detail === 0) notePop.querySelector("a")?.focus(); // Opened from the keyboard.
  }
});
// A term button toggles the term popover by itself (popovertarget); fill and place it first.
let termAnchor = null;
reading.addEventListener("click", (e) => {
  const term = e.target.closest("button.term");
  if (term) { termAnchor = term; termPop.replaceChildren(...termContent(term)); }
}, true);
termPop.addEventListener("toggle", (e) => { if (e.newState === "open" && termAnchor) placePopover(termPop, termAnchor); });
// Hover with a mouse: open after a short pause, close when the pointer leaves both the anchor and the popover.
let hoverTimer = 0;
function hover(selector, pop, content) {
  reading.addEventListener("pointerover", (e) => {
    const anchor = e.target.closest(selector);
    if (!anchor || e.pointerType !== "mouse") return;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      if (pop === termPop) termAnchor = anchor;
      openPopover(pop, anchor, content(anchor));
    }, 280);
  });
  const leave = (e) => {
    if (e.pointerType !== "mouse" || e.relatedTarget?.closest?.(`${selector}, .note-pop`)) return;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => { if (pop.matches(":popover-open")) pop.hidePopover(); }, 320);
  };
  reading.addEventListener("pointerout", (e) => { if (e.target.closest(selector)) leave(e); });
  pop.addEventListener("pointerout", (e) => { if (!pop.contains(e.relatedTarget)) leave(e); });
  pop.addEventListener("pointerover", () => clearTimeout(hoverTimer));
}
hover("a[role='doc-noteref']", notePop, noteContent);
hover("button.term", termPop, termContent);

// Continue reading: remember the block at the top of the screen, and offer to return to it on the next visit.
const POSITION_KEY = `reader-position:${document.documentElement.dataset.bookId}`;
function blockAtTop() {
  const el = document.elementFromPoint(innerWidth / 2, Math.min(innerHeight / 3, 200));
  return el?.closest(".book .doc :is(p, h2, h3, figure, li)[id]") ?? null;
}
let positionTimer = 0;
addEventListener("scroll", () => {
  clearTimeout(positionTimer);
  positionTimer = setTimeout(() => {
    const block = blockAtTop();
    if (!block) return;
    const id = block.closest(".doc > section[id]")?.id;
    const chapter = id ? tocDialog.querySelector(`[data-chapter="${CSS.escape(id)}"] :is(.toc-name, .toc-part-title)`)?.textContent ?? "" : "";
    try { localStorage.setItem(POSITION_KEY, JSON.stringify({ id: block.id, chapter })); }
    catch { /* Storage blocked: the reader simply starts at the top next time. */ }
  }, 800);
}, { passive: true });
function offerResume() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(POSITION_KEY) ?? "null"); } catch { return; }
  if (!saved?.id || location.hash || !document.getElementById(saved.id)) return;
  const bar = document.createElement("div");
  bar.className = "resume";
  const go = document.createElement("a");
  go.href = `#${saved.id}`;
  go.textContent = saved.chapter ? `להמשיך לקרוא: ${saved.chapter}` : "להמשיך מהמקום שעצרתי";
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "×";
  close.setAttribute("aria-label", "סגירה");
  const remove = () => bar.remove();
  go.addEventListener("click", (e) => { e.preventDefault(); remove(); goTo(saved.id); });
  close.addEventListener("click", remove);
  bar.append(go, close);
  document.body.append(bar);
  // The offer fades away once the reader starts somewhere else.
  addEventListener("scroll", () => { if (scrollY > innerHeight * 1.5) remove(); }, { passive: true });
}
offerResume();
