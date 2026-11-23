// Web-only reading features. Each feature works on the EPUB-derived DOM and its stable IDs.
// The book reads fully without this script.

const root = document.documentElement;
const reading = document.getElementById("reading");
const bookId = root.dataset.bookId ?? "book";
const POSITION_KEY = `position:${bookId}`;

// Browser storage can be absent or throw (private mode, blocked site data). Features degrade to off.
const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* Storage blocked: skip. */ } },
};

function byId(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`reader.js: missing #${id}`);
  return el;
}

// Must match normalize() in tools/build_web.py.
function normalize(text) {
  let out = "";
  for (const c of text.normalize("NFC")) {
    const cp = c.codePointAt(0);
    if (cp < 0x0591 || cp > 0x05c7) out += c;
  }
  return out.toLowerCase();
}

function pageOf(el) {
  // The printed page is the label of the last page marker before the element.
  const markers = reading.querySelectorAll('[data-epub-type="pagebreak"]');
  let page = null;
  for (const m of markers) {
    if (m.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_PRECEDING) break;
    page = m.getAttribute("title");
  }
  return page;
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

// Dialogs
for (const button of document.querySelectorAll("[data-open]")) {
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
  if (!img) return;
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

// Search: the index loads on first use.
let index = null;
const input = byId("search-input");
const results = byId("search-results");
const status = byId("search-status");
async function loadIndex() {
  if (index) return index;
  const response = await fetch("search.json");
  if (!response.ok) throw new Error(`search.json: HTTP ${response.status}`);
  index = await response.json();
  return index;
}
function snippet(text, term) {
  const frag = document.createDocumentFragment();
  const at = normalize(text).indexOf(term);
  // Normalization only removes combining marks, so positions differ when the text has niqqud.
  // Limit: the highlight can shift on pointed text. Revisit if the book has much niqqud.
  const start = Math.max(0, at - 40);
  const before = (start > 0 ? "…" : "") + text.slice(start, Math.max(at, 0));
  const hit = at >= 0 ? text.slice(at, at + term.length) : "";
  const after = text.slice(Math.max(at, 0) + hit.length, Math.max(at, 0) + hit.length + 80) + "…";
  frag.append(before);
  if (hit) { const m = document.createElement("mark"); m.textContent = hit; frag.append(m); }
  frag.append(after);
  return frag;
}
async function runSearch() {
  const terms = normalize(input.value).split(/\s+/).filter(Boolean);
  results.replaceChildren();
  if (terms.length === 0) { status.textContent = ""; return; }
  const entries = await loadIndex();
  const hits = entries.filter((e) => terms.every((t) => e.norm.includes(t)));
  status.textContent = hits.length === 0 ? "לא נמצאו תוצאות" : `${hits.length} תוצאות`;
  for (const hit of hits.slice(0, 100)) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `#${hit.id}`;
    const where = document.createElement("span");
    where.className = "where";
    where.textContent = [hit.section, hit.page && `עמוד ${hit.page}`].filter(Boolean).join(" · ");
    a.append(where, snippet(hit.text, terms[0]));
    a.addEventListener("click", (e) => { e.preventDefault(); byId("search-dialog").close(); goTo(hit.id); });
    li.append(a);
    results.append(li);
  }
}
let searchTimer = 0;
input.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 120); });
byId("search-form").addEventListener("submit", (e) => { e.preventDefault(); results.querySelector("a")?.click(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !e.target.closest("input, textarea, dialog")) {
    e.preventDefault();
    byId("search-dialog").showModal();
    input.focus();
  }
});

// Reading position and current printed page
// Only rendered elements: hidden ones (the in-book nav) report top 0 and break the ordered search below.
const tracked = [...reading.querySelectorAll('p[id], h1[id], h2[id], figure[id], table[id], [data-epub-type="pagebreak"]')]
  .filter((el) => el.getClientRects().length > 0);
const pageLabel = byId("current-page");
function topVisible() {
  const line = 80;
  // Binary search: tracked elements are in document order.
  let lo = 0, hi = tracked.length - 1, best = tracked[0];
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (tracked[mid].getBoundingClientRect().top <= line) { best = tracked[mid]; lo = mid + 1; } else hi = mid - 1;
  }
  return best;
}
let ticking = false;
function onScroll() {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => {
    ticking = false;
    const el = topVisible();
    if (!el) return;
    const page = pageOf(el);
    pageLabel.textContent = page ? `עמוד ${page}` : "";
    if (scrollY > 200) store.set(POSITION_KEY, el.id);
  });
}
addEventListener("scroll", onScroll, { passive: true });
onScroll();

const saved = store.get(POSITION_KEY);
const savedEl = saved && document.getElementById(saved);
if (!location.hash && savedEl) {
  const resume = byId("resume");
  const page = pageOf(savedEl);
  byId("resume-go").textContent = page ? `המשך קריאה מעמוד ${page}` : "המשך קריאה";
  byId("resume-go").addEventListener("click", () => { resume.hidden = true; goTo(saved); });
  byId("resume-close").addEventListener("click", () => { resume.hidden = true; });
  resume.hidden = false;
}
