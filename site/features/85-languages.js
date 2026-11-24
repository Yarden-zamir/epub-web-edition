// Languages. Chapters with a translation (translations-data, built by tools/web/87_languages.py) can show it:
// - a reading mode for the whole book: as printed, Hebrew, or English. Kept in ?lang= and localStorage;
// - a switch at each translated chapter, and a small chip beside each element that shows a foreign language.
// A translation replaces the inner HTML of elements by ID, so IDs, links, notes and highlights keep working.
// Marks that the build adds to the printed text (glossary terms, cross-links) stay with the printed text: a translation
// shows its own markup only, and switching back restores the printed content with its marks. The glossary is Hebrew and
// its first-use marks follow the printed paragraphs, so marking a translation would need a second copy of that logic.
const translationIndex = JSON.parse(document.getElementById("translations-data")?.textContent ?? "{}");
const LANG_KEY = `reader-lang:${document.documentElement.dataset.bookId}`;
const LANG_NAME = { he: "עברית", en: "English" };
const LANG_DIR = { he: "rtl", en: "ltr" };
const MACHINE_NOTE = { he: "תרגום מכונה, לא נבדק", en: "Machine translation, not reviewed" };
const pageLang = document.documentElement.lang;
// Children that other features add inside book elements; a swap keeps them.
const SITE_PARTS = ".deep-link";

const translationFiles = new Map(); // Site path -> promise of the translation data.
const bookContent = new Map(); // Element ID -> its printed content, saved before the first swap.
const shownLang = new Map(); // Element ID -> language shown now, when it is not the printed one.
const langOfId = new Map(); // Element ID -> { chapter, unit }.
for (const units of Object.values(translationIndex)) {
  for (const unit of units) for (const id of unit.ids) langOfId.set(id, { chapter: unit.chapter, unit });
}

function readLangChoice() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(LANG_KEY) ?? "{}") ?? {}; } catch { /* Storage blocked: start as printed. */ }
  const fromUrl = new URLSearchParams(location.search).get("lang");
  const mode = fromUrl in LANG_NAME ? fromUrl : saved.mode in LANG_NAME ? saved.mode : "";
  // A shared link sets the mode for this reader; their own chapter choices from before give way to it.
  const chapters = fromUrl in LANG_NAME && fromUrl !== saved.mode ? {} : saved.chapters ?? {};
  return { mode, chapters };
}
let langChoice = readLangChoice();
// The address carries the mode (?lang=), also after Back or Forward to an entry from before the choice.
function syncLangUrl() {
  const url = new URL(location.href);
  if (langChoice.mode) url.searchParams.set("lang", langChoice.mode); else url.searchParams.delete("lang");
  if (url.href !== location.href) history.replaceState(history.state, "", url);
}
function saveLangChoice() {
  try { localStorage.setItem(LANG_KEY, JSON.stringify(langChoice)); } catch { /* Storage blocked: the choice lasts for this page. */ }
  syncLangUrl();
}

function loadTranslation(unit) {
  if (!translationFiles.has(unit.file)) {
    translationFiles.set(unit.file, fetch(unit.file).then((r) => {
      if (!r.ok) throw new Error(`languages: ${unit.file} answered ${r.status}`);
      return r.json();
    }));
  }
  return translationFiles.get(unit.file);
}

function printedLangOf(chapter) { return translationIndex[chapter][0].original; }
function chapterWants(chapter) {
  const units = translationIndex[chapter];
  const chosen = langChoice.chapters[chapter] ?? langChoice.mode;
  return units.some((u) => u.lang === chosen) ? chosen : printedLangOf(chapter);
}

// One element in a language: the printed content (lang = null) or a translation. A figure swaps its caption
// and image alt texts; other elements swap their inner HTML.
function bookImages(figure) { return figure.querySelectorAll("img[data-shape]"); } // Not video thumbnails.
function setAttr(el, name, value) { if (value == null) el.removeAttribute(name); else el.setAttribute(name, value); }
function saveBookContent(el) {
  if (bookContent.has(el.id)) return;
  if (el.matches("figure")) {
    const caption = el.querySelector(":scope > figcaption");
    const copy = caption?.cloneNode(true);
    copy?.querySelectorAll(SITE_PARTS).forEach((part) => part.remove());
    bookContent.set(el.id, { caption: copy?.innerHTML ?? null, lang: caption?.getAttribute("lang"), dir: caption?.getAttribute("dir"),
      alts: [...bookImages(el)].map((img) => img.alt) });
  } else {
    const copy = el.cloneNode(true);
    copy.querySelectorAll(`:scope > :is(${SITE_PARTS})`).forEach((part) => part.remove());
    bookContent.set(el.id, { html: copy.innerHTML, lang: el.getAttribute("lang"), dir: el.getAttribute("dir") });
  }
}
function fillElement(el, html, lang, dir) {
  const kept = [...el.children].filter((child) => child.matches(SITE_PARTS));
  el.innerHTML = html;
  el.append(...kept);
  setAttr(el, "lang", lang);
  setAttr(el, "dir", dir);
}
function showElement(el, lang, data) {
  saveBookContent(el);
  const book = bookContent.get(el.id);
  const translated = lang ? (el.matches("figure") ? data.figures[el.id] : data.items[el.id]) : null;
  if (lang && translated === undefined) throw new Error(`languages: no ${lang} text for #${el.id}`);
  if (el.matches("figure")) {
    const caption = el.querySelector(":scope > figcaption");
    if (caption) fillElement(caption, lang ? translated.caption : book.caption, lang ?? book.lang, lang ? LANG_DIR[lang] : book.dir);
    const alts = lang ? translated.alts : book.alts;
    bookImages(el).forEach((img, i) => { img.alt = alts[i]; });
  } else {
    fillElement(el, lang ? translated : book.html, lang ?? book.lang, lang ? LANG_DIR[lang] : book.dir);
  }
  if (lang) shownLang.set(el.id, lang); else shownLang.delete(el.id);
}

// Swap content without moving the reader: the block at the reading line stays where it was (position() and
// restorePosition() in 00-core.js). A short cross-fade, unless the reader asked for reduced motion.
function swapInPlace(change) {
  const run = () => { const at = position(); change(); restorePosition(at); };
  if (reduceMotion.matches || !document.startViewTransition) { run(); return Promise.resolve(); }
  document.documentElement.classList.add("lang-swap");
  const transition = document.startViewTransition(run);
  return transition.finished.finally(() => document.documentElement.classList.remove("lang-swap"));
}

// Show a chapter in a language. Elements that the reader switched one by one follow the chapter again.
async function showChapter(chapter, lang, { animate = true } = {}) {
  const printed = printedLangOf(chapter);
  const unit = translationIndex[chapter].find((u) => u.lang === lang);
  const data = lang === printed ? null : await loadTranslation(unit);
  const ids = translationIndex[chapter].flatMap((u) => u.ids);
  const change = () => {
    for (const id of ids) {
      const want = lang === printed || !unit.ids.includes(id) ? null : lang;
      if ((shownLang.get(id) ?? null) !== want) showElement(byId(id), want, data);
      byId(id).classList.remove("lang-single");
    }
    updateChapterBar(chapter);
  };
  if (animate) await swapInPlace(change); else { const at = position(); change(); restorePosition(at); }
}

async function toggleElement(el) {
  const { chapter, unit } = langOfId.get(el.id);
  const target = shownLang.has(el.id) ? null : unit.lang;
  const data = target ? await loadTranslation(unit) : null;
  await swapInPlace(() => {
    showElement(el, target, data);
    // Marked when it differs from its chapter, so the reader sees which parts they switched.
    el.classList.toggle("lang-single", (target ?? printedLangOf(chapter)) !== chapterWants(chapter));
    updateChapterBar(chapter);
  });
}

// Chapter switch: the printed language and each translation, with the AI translation note.
const chapterBars = new Map(); // Chapter ID -> its switch.
function makeChapterBar(chapter) {
  const section = byId(chapter);
  const bar = document.createElement("div");
  bar.className = "lang-bar";
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", "שפת הפרק");
  const toggle = document.createElement("div");
  toggle.className = "lang-switch";
  const langs = [printedLangOf(chapter), ...translationIndex[chapter].map((u) => u.lang)];
  toggle.style.setProperty("--count", langs.length);
  for (const lang of langs) {
    const button = document.createElement("button");
    button.type = "button";
    button.lang = lang;
    button.dataset.lang = lang;
    button.textContent = LANG_NAME[lang];
    button.addEventListener("click", () => {
      langChoice.chapters[chapter] = lang;
      saveLangChoice();
      showChapter(chapter, lang);
    });
    toggle.append(button);
  }
  const note = document.createElement("span");
  note.className = "lang-note";
  bar.append(toggle, note);
  const heading = section.querySelector(":scope > :is(h1, h2, h3)");
  section.insertBefore(bar, heading);
  chapterBars.set(chapter, bar);
  updateChapterBar(chapter);
}
function updateChapterBar(chapter) {
  const bar = chapterBars.get(chapter);
  if (!bar) return;
  const ids = translationIndex[chapter].flatMap((u) => u.ids);
  const shown = ids.map((id) => shownLang.get(id)).filter(Boolean);
  // The switch shows the chapter's language: the translation when most of its elements show it.
  const lang = shown.length * 2 > ids.length ? shown[0] : printedLangOf(chapter);
  const buttons = [...bar.querySelectorAll("button")];
  buttons.forEach((b, i) => {
    b.setAttribute("aria-pressed", String(b.dataset.lang === lang));
    if (b.dataset.lang === lang) bar.firstChild.style.setProperty("--at", i);
  });
  const note = bar.querySelector(".lang-note");
  const noteLang = shown[0];
  note.hidden = !noteLang;
  if (noteLang) { note.textContent = MACHINE_NOTE[noteLang]; note.lang = noteLang; note.dir = LANG_DIR[noteLang]; }
}

// Element chip: on an element that shows a foreign language (or one the reader switched), a small button switches
// that element alone. With a mouse it sits in the margin beside the element and shows on hover. On a narrow
// screen a tap on the element shows it as a pill at the bottom of the screen, and the element gets a soft mat.
const langChip = document.createElement("button");
langChip.type = "button";
langChip.className = "lang-chip";
langChip.hidden = true;
let chipFor = null, chipTimer = 0;
function chipTarget(node) {
  const el = node?.closest?.("[id]");
  for (let at = el; at && at !== reading; at = at.parentElement?.closest("[id]")) {
    if (langOfId.has(at.id)) return at;
  }
  return null;
}
function markTarget(el) {
  for (const old of reading.querySelectorAll(".lang-target")) if (old !== el) old.classList.remove("lang-target");
  el?.classList.add("lang-target");
}
function showChip(el) {
  const shown = shownLang.get(el.id);
  const { unit } = langOfId.get(el.id);
  const now = shown ?? unit.original;
  if (now === pageLang && !el.classList.contains("lang-single")) return hideChip();
  const to = shown ? unit.original : unit.lang;
  clearTimeout(chipTimer);
  chipFor = el;
  const label = `הצגת הקטע ב${to === "he" ? "עברית" : "אנגלית"}`;
  langChip.setAttribute("aria-label", label);
  langChip.hidden = false;
  const column = el.closest(".doc").getBoundingClientRect();
  const rtl = document.dir === "rtl";
  const room = rtl ? innerWidth - column.right : column.left;
  const docked = room < 7 * parseFloat(getComputedStyle(document.documentElement).fontSize);
  langChip.classList.toggle("docked", docked);
  langChip.textContent = docked ? label : LANG_NAME[to];
  langChip.lang = docked ? pageLang : to;
  if (docked) {
    langChip.style.left = langChip.style.top = "";
    markTarget(el);
  } else {
    // In the margin, beside the first line, on the page's start side.
    const chip = langChip.getBoundingClientRect();
    const box = el.getBoundingClientRect();
    langChip.style.left = `${(rtl ? column.right + 12 : column.left - 12 - chip.width) + scrollX}px`;
    langChip.style.top = `${box.top + 4 + scrollY}px`;
  }
  requestAnimationFrame(() => langChip.classList.add("shown"));
}
function hideChip() {
  chipFor = null;
  markTarget(null);
  langChip.classList.remove("shown");
  clearTimeout(chipTimer);
  chipTimer = setTimeout(() => { if (!chipFor) langChip.hidden = true; }, 250);
}
langChip.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") markTarget(chipFor); });
langChip.addEventListener("pointerleave", (e) => {
  if (e.pointerType !== "mouse") return;
  if (chipTarget(e.relatedTarget) !== chipFor) hideChip(); else markTarget(null);
});
langChip.addEventListener("click", () => {
  const el = chipFor;
  if (!el) return;
  toggleElement(el).then(() => { if (chipFor === el) showChip(el); });
});

// Reading mode for the whole book, in a menu behind a small button at the side of the screen.
const langFab = document.createElement("button");
langFab.type = "button";
langFab.className = "lang-fab";
langFab.innerHTML = '<span class="lang-glyph" aria-hidden="true"></span>'; // Letters drawn in CSS: the label is the name.
langFab.setAttribute("aria-haspopup", "true");
const langMenu = document.createElement("div");
langMenu.id = "lang-menu";
langMenu.className = "menu lang-menu";
langMenu.popover = "auto";
langMenu.setAttribute("role", "dialog");
langMenu.setAttribute("aria-label", "שפת הקריאה");
langFab.setAttribute("aria-controls", "lang-menu");
function chapterCount(lang) {
  return Object.keys(translationIndex).filter((c) => translationIndex[c].some((u) => u.lang === lang)).length;
}
const MODES = [
  { mode: "", title: "כפי שנדפס", meta: "כל פרק בשפה שבה נכתב" },
  { mode: "he", title: "עברית", meta: "פרקים באנגלית, בתרגום מכונה" },
  { mode: "en", title: "English", meta: "Machine translation, not reviewed", lang: "en" },
].filter((m) => !m.mode || chapterCount(m.mode) > 0);
function buildLangMenu() {
  const head = document.createElement("p");
  head.className = "menu-note";
  head.textContent = "שפת הקריאה";
  const list = document.createElement("div");
  list.className = "lang-modes";
  list.setAttribute("role", "radiogroup");
  list.setAttribute("aria-label", "שפת הקריאה");
  for (const m of MODES) {
    const option = document.createElement("button");
    option.type = "button";
    option.setAttribute("role", "radio");
    option.dataset.mode = m.mode;
    const title = document.createElement("span");
    title.className = "lang-mode-title";
    title.textContent = m.title;
    const meta = document.createElement("span");
    meta.className = "menu-meta";
    meta.textContent = m.meta;
    if (m.lang) { title.lang = meta.lang = m.lang; title.dir = meta.dir = LANG_DIR[m.lang]; }
    option.append(title, meta);
    option.addEventListener("click", () => {
      setLangMode(m.mode);
      setTimeout(() => langMenu.hidePopover(), 160); // After the radio settles, so the choice is seen.
    });
    list.append(option);
  }
  const chapters = document.createElement("ul");
  for (const chapter of Object.keys(translationIndex)) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `#${chapter}`;
    a.textContent = tocDialog.querySelector(`[data-chapter="${CSS.escape(chapter)}"] :is(.toc-name, .toc-part-title)`)?.textContent
      ?? byId(chapter).querySelector("h2")?.textContent ?? chapter;
    const langs = document.createElement("span");
    langs.className = "menu-meta";
    langs.textContent = translationIndex[chapter].map((u) => `תרגום: ${LANG_NAME[u.lang]}`).join(" · ");
    a.addEventListener("click", (e) => { e.preventDefault(); langMenu.hidePopover(); goTo(chapter); });
    a.append(langs);
    li.append(a);
    chapters.append(li);
  }
  langMenu.append(head, list, chapters);
}
function updateLangMenu() {
  for (const option of langMenu.querySelectorAll("[data-mode]")) option.setAttribute("aria-checked", String(option.dataset.mode === langChoice.mode));
  const current = MODES.find((m) => m.mode === langChoice.mode);
  langFab.setAttribute("aria-label", `שפת הקריאה: ${current.title}`);
  langFab.toggleAttribute("data-active", langChoice.mode !== "");
}
async function setLangMode(mode) {
  langChoice = { mode, chapters: {} };
  saveLangChoice();
  updateLangMenu();
  const visible = Object.keys(translationIndex).filter((c) => {
    const box = byId(c).getBoundingClientRect();
    return box.bottom > 0 && box.top < innerHeight;
  });
  // Chapters on screen cross-fade; the others change without animation.
  for (const chapter of Object.keys(translationIndex)) await showChapter(chapter, chapterWants(chapter), { animate: visible.includes(chapter) });
}
overlayOpeners["lang-menu"] = () => langMenu.showPopover();
langMenu.addEventListener("toggle", (e) => {
  langFab.setAttribute("aria-expanded", String(e.newState === "open"));
  if (e.newState === "closed") { overlayClosed(langMenu); return; }
  if (!overlayStack.includes("lang-menu")) openOverlay(langMenu, () => {});
  const box = langFab.getBoundingClientRect();
  const width = langMenu.offsetWidth, height = langMenu.offsetHeight;
  const rtl = document.dir === "rtl";
  langMenu.style.left = `${Math.min(innerWidth - width - 8, Math.max(8, rtl ? box.left : box.right - width))}px`;
  langMenu.style.top = `${Math.max(8, box.top - 8 - height)}px`;
});
langFab.addEventListener("click", () => langMenu.togglePopover());

if (Object.keys(translationIndex).length) {
  buildLangMenu();
  document.body.append(langChip, langFab, langMenu);
  updateLangMenu();
  langFab.setAttribute("aria-expanded", "false");
  for (const chapter of Object.keys(translationIndex)) makeChapterBar(chapter);
  if (new URLSearchParams(location.search).has("lang") || langChoice.mode) saveLangChoice(); // Keep ?lang= in the address.
  for (const chapter of Object.keys(translationIndex)) {
    const lang = chapterWants(chapter);
    if (lang !== printedLangOf(chapter)) showChapter(chapter, lang, { animate: false });
  }
  addEventListener("popstate", syncLangUrl);
  // The button appears once the reader is past the cover, like the bar's own buttons. On a narrow screen it steps
  // aside while the reader scrolls down through the text, and comes back when they scroll up.
  new IntersectionObserver(([entry]) => langFab.toggleAttribute("data-shown", !entry.isIntersecting), { rootMargin: "-96px 0px 0px 0px" })
    .observe(byId("top"));
  const narrow = matchMedia("(max-width: 40rem)");
  let lastY = scrollY;
  addEventListener("scroll", () => {
    const dy = scrollY - lastY;
    if (Math.abs(dy) < 12) return;
    langFab.toggleAttribute("data-tucked", narrow.matches && dy > 0 && !langMenu.matches(":popover-open"));
    lastY = scrollY;
  }, { passive: true });
  // Chips: hover with a mouse; tap on a touch screen.
  reading.addEventListener("pointerover", (e) => {
    if (e.pointerType !== "mouse") return;
    const el = chipTarget(e.target);
    if (el && el !== chipFor) showChip(el);
    else if (!el && chipFor) hideChip();
  });
  reading.addEventListener("pointerleave", (e) => { if (e.relatedTarget !== langChip) hideChip(); });
  reading.addEventListener("click", (e) => {
    if (matchMedia("(pointer: fine)").matches || e.target.closest("a, button")) return;
    const el = chipTarget(e.target);
    if (el) showChip(el); else hideChip();
  });
  addEventListener("scroll", () => {
    if (chipFor && langChip.classList.contains("docked")) {
      const box = chipFor.getBoundingClientRect();
      if (box.bottom < 0 || box.top > innerHeight) hideChip();
    }
  }, { passive: true });
}
