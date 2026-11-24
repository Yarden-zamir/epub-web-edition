// Errata page: filters, search, the "as printed" switch and the side-by-side viewer.
// The page reads fully without this script.

// Shared with the book page (site/features/75-errata.js): "printed" shows the text as printed.
const TEXT_KEY = "eli-raz:text";
function readTextMode() {
  try { return localStorage.getItem(TEXT_KEY) === "printed"; } catch { return false; }
}
function saveTextMode(printed) {
  try { printed ? localStorage.setItem(TEXT_KEY, "printed") : localStorage.removeItem(TEXT_KEY); }
  catch { /* Private mode or blocked storage: the switch then lasts for this page only. */ }
}
function need(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`errata.js: missing #${id}`);
  return el;
}

const printedSwitch = need("er-printed");
printedSwitch.checked = readTextMode();
printedSwitch.addEventListener("change", () => saveTextMode(printedSwitch.checked));
addEventListener("pageshow", () => { printedSwitch.checked = readTextMode(); }); // Back from the book.

// Filters and search. Words match anywhere in a row's text, ignoring niqqud, geresh and case.
const rows = [...document.querySelectorAll(".er-row")];
const sections = [...document.querySelectorAll(".er-section")];
const filters = [...document.querySelectorAll(".er-filter")];
const searchInput = need("er-search");
function fold(text) {
  let out = "";
  for (const c of text.normalize("NFD")) {
    const cp = c.codePointAt(0);
    if ((cp >= 0x0591 && cp <= 0x05c7) || (cp >= 0x0300 && cp <= 0x036f) || "'\"׳״".includes(c)) continue;
    out += c;
  }
  return out.toLowerCase();
}
const rowText = new Map(rows.map((r) => [r, fold(r.dataset.search)]));
let filter = "";
function apply() {
  const words = fold(searchInput.value).split(" ").filter(Boolean);
  let shown = 0;
  for (const row of rows) {
    row.hidden = !((!filter || row.dataset.status === filter) && words.every((w) => rowText.get(row).includes(w)));
    if (!row.hidden) shown++;
  }
  for (const section of sections) section.hidden = !section.querySelector(".er-row:not([hidden])");
  need("er-empty").hidden = shown > 0;
  need("er-status").textContent = filter || words.length ? (shown === 1 ? "ממצא אחד" : `${shown} ממצאים`) : "";
}
for (const button of filters) {
  button.addEventListener("click", () => {
    filter = button.dataset.filter;
    for (const b of filters) b.setAttribute("aria-pressed", String(b === button));
    apply();
  });
}
searchInput.addEventListener("input", apply);
need("er-search-form").addEventListener("submit", (e) => e.preventDefault());

// Viewer: the print image (the line or the whole page) beside our text of the same element.
// Opening pushes a history entry, so Back closes it.
const viewer = need("er-viewer");
const viewerImg = need("erv-img");
const imagePane = need("erv-image");
const tabs = viewer.querySelector(".erv-tabs");
let opener = null;
function showImage(button) {
  for (const t of tabs.children) t.setAttribute("aria-pressed", String(t.dataset.view === button.dataset.view));
  imagePane.dataset.kind = button.dataset.kind;
  imagePane.classList.remove("zoomed", "ready");
  viewerImg.style.width = "";
  viewerImg.alt = button.dataset.kind === "page" ? `${button.textContent} בספר המודפס` : "השורה בספר המודפס";
  viewerImg.onload = () => imagePane.classList.add("ready");
  viewerImg.src = button.dataset.view;
  if (viewerImg.complete) imagePane.classList.add("ready");
  imagePane.scrollTo(0, 0);
  // A wide line scrolls sideways on a phone: start at the edge where the printed line starts.
  if (button.dataset.kind === "line" && viewer.dataset.dir !== document.dir) {
    imagePane.scrollLeft = document.dir === "rtl" ? -imagePane.scrollWidth : imagePane.scrollWidth;
    viewerImg.addEventListener("load", () => { imagePane.scrollLeft = document.dir === "rtl" ? -imagePane.scrollWidth : imagePane.scrollWidth; }, { once: true });
  }
}
function openViewer(pill) {
  const row = pill.closest(".er-row");
  opener = pill;
  viewer.dataset.dir = row.dataset.dir;
  tabs.replaceChildren(...[...row.querySelectorAll(".er-pill")].map((p) => {
    const tab = p.cloneNode(true);
    tab.className = "erv-tab";
    tab.addEventListener("click", () => showImage(tab));
    return tab;
  }));
  const text = need("erv-text");
  const head = document.createElement("p");
  head.className = "erv-row";
  head.textContent = `${row.querySelector(".er-num").textContent} · ${row.querySelector(".er-where").textContent}`;
  text.replaceChildren(head, row.querySelector("template.er-compare").content.cloneNode(true));
  text.scrollTo(0, 0);
  showImage([...tabs.children].find((t) => t.dataset.view === pill.dataset.view));
  viewer.showModal();
  history.pushState({ viewer: true }, "");
}
document.addEventListener("click", (e) => {
  const pill = e.target.closest(".er-row .er-pill");
  if (pill) openViewer(pill);
});
viewer.addEventListener("click", (e) => {
  if (e.target === viewer || e.target.closest("[data-close]")) viewer.close();
});
viewer.addEventListener("close", () => {
  if (history.state?.viewer) history.back();
  opener?.focus();
});
addEventListener("popstate", () => { if (viewer.open) viewer.close(); });

// A page image opens fitted to the pane; a click or tap zooms it in at that point, and again back out.
imagePane.addEventListener("click", (e) => {
  if (imagePane.dataset.kind !== "page" || e.target !== viewerImg) return;
  const box = viewerImg.getBoundingClientRect();
  const fx = (e.clientX - box.left) / box.width, fy = (e.clientY - box.top) / box.height;
  const zoomed = imagePane.classList.toggle("zoomed");
  // Known limit: the page images are small (book.toml [facsimile] dpi = 56), so zoom stops at 1.6 times their
  // own size, where the text still reads. Revisit when the site gets sharper page images.
  viewerImg.style.width = zoomed ? `${Math.max(viewerImg.naturalWidth * 1.6, imagePane.clientWidth)}px` : "";
  if (!zoomed) return;
  const next = viewerImg.getBoundingClientRect();
  // Keep the clicked point under the pointer. Scroll offsets are negative in a right-to-left pane.
  const left = fx * next.width - (e.clientX - imagePane.getBoundingClientRect().left);
  imagePane.scrollTo({ top: fy * next.height - (e.clientY - imagePane.getBoundingClientRect().top),
    left: document.dir === "rtl" ? left - (next.width - imagePane.clientWidth) : left, behavior: "instant" });
});
