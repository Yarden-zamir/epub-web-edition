// Navigator: chapters, the places index and, when the book has one, a timeline. One filter field serves the
// chapters and places tabs. The last tab used comes back next time.
const tocDialog = byId("toc-dialog");
const placesData = document.getElementById("places-data");
if (!placesData) { byId("tab-places").remove(); byId("toc-places").remove(); }
const tabs = [...tocDialog.querySelectorAll("[role='tab']")];
const TAB_KEY = "reader-navigator-tab";
const FILTER_TEXT = {
  "tab-chapters": ["סינון פרקים", "סינון פרקים לפי שם או כותב"],
  "tab-places": ["סינון מקומות", "סינון מקומות לפי שם או פרק"],
};
function selectTab(tab) {
  for (const t of tabs) {
    const on = t === tab;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    byId(t.getAttribute("aria-controls")).hidden = !on;
  }
  placeTabPill(tab);
  const filter = FILTER_TEXT[tab.id];
  byId("toc-filter-form").hidden = !filter;
  if (filter) {
    [byId("toc-filter").placeholder, byId("toc-filter-label").textContent] = filter;
  }
  if (tab.id === "tab-places") renderPlacesIndex();
  applyFilter();
  try { localStorage.setItem(TAB_KEY, tab.id); } catch { /* Storage blocked: the chapters tab opens first. */ }
}

// The ink pill under the selected tab slides to it (68-navigator.css).
function placeTabPill(tab) {
  const list = tab.parentElement;
  list.style.setProperty("--tab-x", `${tab.offsetLeft}px`);
  list.style.setProperty("--tab-w", `${tab.offsetWidth}px`);
  list.style.setProperty("--tab-h", `${tab.offsetHeight}px`);
  list.style.setProperty("--tab-top", `${tab.offsetTop}px`);
}

// Places index: every place with its colour dot, a one-line description and the chapters that mention it.
// A place opens the map on it (one history entry); a chapter link jumps there and highlights the place name.
let placesOrder = "name";
function renderPlacesIndex() {
  if (!placesData) return;
  const list = JSON.parse(placesData.textContent);
  const collator = new Intl.Collator("he");
  const row = (p) => {
    const li = document.createElement("li");
    li.className = "pi-item";
    li.dataset.filter = [p.name, ...p.chapters.map((c) => c.title)].join(" ");
    li.style.setProperty("--place", `var(--place-${p.n})`);
    const open = document.createElement("button");
    open.type = "button";
    open.className = "pi-place";
    const dot = document.createElement("i");
    dot.setAttribute("aria-hidden", "true");
    const name = Object.assign(document.createElement("span"), { className: "pi-name", textContent: p.name });
    const desc = Object.assign(document.createElement("span"), { className: "pi-desc", textContent: p.description });
    open.append(dot, name);
    if (p.far) open.append(Object.assign(document.createElement("span"), { className: "pi-far", textContent: "מחוץ למפה" }));
    open.append(desc);
    // openPlace jumps with goTo, which closes the navigator and replaces its history entry: Back returns to the page.
    open.addEventListener("click", () => openPlace(p.id).catch((err) => console.error(err)));
    const chapters = document.createElement("span");
    chapters.className = "pi-chapters";
    for (const c of p.chapters) {
      const a = Object.assign(document.createElement("a"), { href: c.href, textContent: c.title });
      a.dataset.quote = p.name; // The jump highlights the place name where the chapter mentions it.
      chapters.append(a);
    }
    li.append(open, chapters);
    return li;
  };
  const box = byId("places-index");
  if (placesOrder === "name") {
    const ol = document.createElement("ol");
    ol.className = "pi-list";
    ol.append(...list.toSorted((a, b) => collator.compare(a.name, b.name)).map(row));
    box.replaceChildren(ol);
  } else {
    // Grouped by chapter, in book order; a place in several chapters appears under each.
    const order = [...tocDialog.querySelectorAll(".toc-item[data-chapter]")].map((li) => li.dataset.chapter);
    const groups = new Map();
    for (const p of list) for (const c of p.chapters) {
      if (!groups.has(c.chapter)) groups.set(c.chapter, { title: c.title, places: [] });
      groups.get(c.chapter).places.push(p);
    }
    box.replaceChildren(...[...groups].toSorted(([a], [b]) => order.indexOf(a) - order.indexOf(b)).map(([, g]) => {
      const section = document.createElement("section");
      section.className = "pi-group";
      const h = Object.assign(document.createElement("h3"), { className: "toc-part-title", textContent: g.title });
      const ol = document.createElement("ol");
      ol.className = "pi-list";
      ol.append(...g.places.toSorted((a, b) => collator.compare(a.name, b.name)).map(row));
      section.append(h, ol);
      return section;
    }));
  }
  applyFilter();
}
for (const button of tocDialog.querySelectorAll(".places-order [data-order]")) {
  button.addEventListener("click", () => {
    placesOrder = button.dataset.order;
    for (const b of tocDialog.querySelectorAll(".places-order [data-order]")) b.setAttribute("aria-pressed", String(b === button));
    renderPlacesIndex();
  });
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
  tocDialog.querySelector(":is(#toc-chapters:not([hidden]) .toc-item, #toc-places:not([hidden]) .pi-item):not([hidden]) :is(a, .pi-place)")?.click();
});
function applyFilter() {
  const words = tokenize(tocFilter.value).map((t) => t.word);
  const matches = (el) => {
    const text = tokenize(el.dataset.filter ?? el.textContent).map((t) => t.word).join(" ");
    return words.every((w) => text.includes(w));
  };
  if (document.getElementById("toc-places") && !byId("toc-places").hidden) {
    let shownPlaces = 0;
    for (const item of tocDialog.querySelectorAll(".pi-item")) {
      item.hidden = !matches(item);
      if (!item.hidden) shownPlaces++;
    }
    for (const group of tocDialog.querySelectorAll(".pi-group")) group.hidden = !group.querySelector(".pi-item:not([hidden])");
    byId("places-empty").hidden = shownPlaces > 0;
    return;
  }
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
}
tocFilter.addEventListener("input", applyFilter);
onDialogOpen["toc-dialog"] = () => {
  placeTabPill(tabs.find((t) => t.getAttribute("aria-selected") === "true") ?? tabs[0]); // Sizes are known once open.
  let saved = null;
  try { saved = localStorage.getItem(TAB_KEY); } catch { /* Storage blocked: keep the current tab. */ }
  const tab = saved && tabs.find((t) => t.id === saved);
  if (tab && tab.getAttribute("aria-selected") !== "true") selectTab(tab);
  // The current chapter: the last top-level section that starts above a third of the screen.
  let current = null;
  for (const section of reading.querySelectorAll(".doc > section[id]")) {
    // The document box: the section of a skipped document has no layout, and reading it would force one (84-rail.js).
    if (section.closest(".book > *").getBoundingClientRect().top < innerHeight / 3) current = section.id;
    else break;
  }
  for (const link of tocDialog.querySelectorAll("[aria-current]")) link.removeAttribute("aria-current");
  const link = current && tocDialog.querySelector(`[data-chapter="${CSS.escape(current)}"] > a`);
  if (link) {
    link.setAttribute("aria-current", "location");
    // Scroll the panel only: scrollIntoView would also move the page under the dialog.
    const panel = byId("toc-chapters");
    if (!panel.hidden) panel.scrollTop += link.getBoundingClientRect().top - panel.getBoundingClientRect().top - panel.clientHeight / 2;
  }
};

