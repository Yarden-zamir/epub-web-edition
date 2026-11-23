// Web edition features. Each one works on the EPUB-derived DOM and its stable IDs.
// The page reads fully without this script.

const reading = document.getElementById("read");

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
    where.textContent = hit.section ?? "";
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
