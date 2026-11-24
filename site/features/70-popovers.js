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
  pop.anchor = anchor; // The link that opened it: Back from the note highlights it again.
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
  go.addEventListener("click", (e) => { e.preventDefault(); pop.hidePopover(); goTo(href.slice(1), { from: pop.anchor ?? termAnchor }); });
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

