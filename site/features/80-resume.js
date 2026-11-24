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
  // It leaves on its own after 5 seconds, but not while the pointer is over it or it has focus.
  let timer = 0;
  const fade = () => {
    if (bar.matches(":hover, :focus-within")) return;
    if (reduceMotion.matches) { remove(); return; }
    bar.classList.add("leaving");
    bar.addEventListener("transitionend", remove, { once: true });
  };
  const restart = () => { clearTimeout(timer); bar.classList.remove("leaving"); timer = setTimeout(fade, 5000); };
  bar.addEventListener("pointerenter", () => { clearTimeout(timer); bar.classList.remove("leaving"); });
  bar.addEventListener("focusin", () => { clearTimeout(timer); bar.classList.remove("leaving"); });
  bar.addEventListener("pointerleave", restart);
  bar.addEventListener("focusout", (e) => { if (!bar.contains(e.relatedTarget)) restart(); });
  restart();
  // Gone at once when the reader starts somewhere else.
  const hero = byId("top");
  addEventListener("scroll", () => { if (scrollY > hero.offsetHeight) remove(); }, { passive: true });
}
offerResume();
