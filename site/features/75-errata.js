// Edition corrections. Each corrected run (span.edition-correction, with the printed form in data-printed) is
// followed by a † mark (a.edition-mark, data-row = its row on the errata page). The † opens the note popover
// (70-popovers.js asks correctionContent for its content). "As printed" mode shows every printed form instead.
const errataWhy = JSON.parse(document.getElementById("errata-data")?.textContent ?? "{}"); // Row -> explanation.
const TEXT_MODE_KEY = "eli-raz:text"; // Shared with the errata page (site/pages/errata.js).

function correctionContent(mark) {
  const span = mark.previousElementSibling;
  if (!span?.matches("span.edition-correction") || !mark.dataset.row) throw new Error("reader.js: a † mark needs its correction and row");
  const body = document.createElement("div");
  body.className = "pop-body corr-pop";
  const head = document.createElement("p");
  head.className = "corr-head";
  const was = document.createElement("bdi");
  was.className = "corr-was";
  was.textContent = span.dataset.printed;
  head.append("תיקון של מהדורה זו. בדפוס: ", was);
  const why = document.createElement("p");
  why.className = "corr-why";
  why.textContent = errataWhy[mark.dataset.row] ?? "";
  const actions = document.createElement("div");
  actions.className = "corr-actions";
  const all = document.createElement("a");
  all.href = `errata/#row-${mark.dataset.row}`;
  all.textContent = "כל תיקוני המהדורה";
  const asPrinted = document.createElement("button");
  asPrinted.type = "button";
  asPrinted.textContent = "הצגת הנוסח המודפס";
  asPrinted.addEventListener("click", () => { notePop.hidePopover(); setTextMode(true); });
  actions.append(all, asPrinted);
  body.append(head, why, actions);
  return [body];
}
// The corrected words get a dotted underline while their popover is open.
notePop.addEventListener("toggle", (e) => {
  for (const s of reading.querySelectorAll("span.edition-correction.is-open")) s.classList.remove("is-open");
  if (e.newState === "open" && notePop.anchor?.matches(".edition-mark")) notePop.anchor.previousElementSibling.classList.add("is-open");
});

// "As printed" mode: every corrected run shows its printed form, the † marks hide, and a small banner offers
// the way back. The choice persists in localStorage when the browser allows it.
const corrections = [...reading.querySelectorAll("span.edition-correction")];
let printedBanner = null;
function setTextMode(printed, save = true) {
  document.documentElement.toggleAttribute("data-printed-text", printed);
  for (const span of corrections) {
    span.dataset.corrected ??= span.textContent;
    span.textContent = printed ? span.dataset.printed : span.dataset.corrected;
  }
  if (save) {
    try { printed ? localStorage.setItem(TEXT_MODE_KEY, "printed") : localStorage.removeItem(TEXT_MODE_KEY); }
    catch { /* Private mode or blocked storage: the mode then lasts for this visit only. */ }
  }
  if (printed && !printedBanner) {
    printedBanner = document.createElement("div");
    printedBanner.className = "printed-banner";
    printedBanner.setAttribute("role", "status");
    const text = document.createElement("span");
    text.textContent = "מוצג הנוסח המודפס, עם הטעויות";
    const back = document.createElement("button");
    back.type = "button";
    back.textContent = "הצגת הנוסח המתוקן";
    back.addEventListener("click", () => setTextMode(false));
    const list = document.createElement("a");
    list.href = "errata/";
    list.textContent = "הרשימה";
    list.setAttribute("aria-label", "רשימת תיקוני המהדורה");
    printedBanner.append(text, back, list);
    document.body.append(printedBanner);
  } else if (!printed && printedBanner) {
    printedBanner.remove();
    printedBanner = null;
  }
}
function readTextModeSaved() {
  try { return localStorage.getItem(TEXT_MODE_KEY) === "printed"; } catch { return false; }
}
if (corrections.length && readTextModeSaved()) setTextMode(true, false);
// The errata page may change the mode while this page waits in the back-forward cache.
addEventListener("pageshow", (e) => {
  if (e.persisted && corrections.length && readTextModeSaved() !== document.documentElement.hasAttribute("data-printed-text")) {
    setTextMode(readTextModeSaved(), false);
  }
});

// Arrival from the errata page: ?hl=<text>#<element> highlights that text (the first form that is on the page).
{
  const params = new URLSearchParams(location.search);
  const marks = params.getAll("hl");
  const target = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (marks.length && target) {
    target.classList.remove("flash"); // Core already flashed the whole block on arrival.
    highlight(target, marks);
  }
  if (params.has("hl")) history.replaceState(history.state, "", location.pathname + location.hash);
}
