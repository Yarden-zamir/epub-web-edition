// Chapter rail: one mark per chapter and part on the inline-start edge, the current one lit. Dragging along it scrubs
// the page and shows the chapter under the finger; letting go keeps the page where it is, as one history entry,
// so Back returns to where the scrub began. Touch only (84-rail.css): with a mouse the rail would cover the
// scrollbar. Keyboard and screen-reader users have the navigator.
const rail = document.createElement("div");
rail.className = "rail";
rail.setAttribute("aria-hidden", "true");
rail.hidden = true;
const railTrack = document.createElement("div");
railTrack.className = "rail-track";
const railLabel = document.createElement("div");
railLabel.className = "rail-label";
railLabel.hidden = true;
rail.append(railTrack, railLabel);
document.body.append(rail);
const railSections = [...reading.querySelectorAll(".doc > section[id]")]
  .filter((s) => tocDialog.querySelector(`[data-chapter="${CSS.escape(s.id)}"]`));
const railName = (s) => tocDialog.querySelector(`[data-chapter="${CSS.escape(s.id)}"] :is(.toc-name, .toc-part-title)`)?.textContent ?? "";
let railMarks = [];
function layoutRail() {
  const height = document.documentElement.scrollHeight;
  // The top of the document box, not of the section: a section of a skipped document (content-visibility) has no
  // layout, and reading its position would force one. The section starts at the top of its document.
  railMarks = railSections.map((s) => ({ s, at: (s.closest(".book > *").getBoundingClientRect().top + scrollY) / height }));
  railTrack.replaceChildren(...railMarks.map(({ s, at }) => {
    const mark = document.createElement("i");
    mark.className = s.matches(".part") ? "part" : "";
    mark.style.top = `${(at * 100).toFixed(2)}%`;
    return mark;
  }));
}
const sectionAt = (fraction) => railMarks.findLast((m) => m.at <= fraction + 1e-6)?.s ?? railSections[0];
function markCurrent() {
  const now = (scrollY + innerHeight / 3) / document.documentElement.scrollHeight;
  const current = sectionAt(now);
  railMarks.forEach((m, i) => railTrack.children[i]?.classList.toggle("current", m.s === current));
}
// Shown while the reader scrolls past the hero, hidden again after a pause (not while scrubbing or hovered).
let railTimer = 0, scrubbing = false;
const hero = byId("top");
const showRail = () => {
  if (scrollY < hero.offsetHeight * 0.8) { rail.hidden = true; return; }
  if (rail.hidden) { layoutRail(); rail.hidden = false; }
  markCurrent();
  clearTimeout(railTimer);
  railTimer = setTimeout(() => { if (!scrubbing && !rail.matches(":hover")) rail.hidden = true; }, 1600);
};
addEventListener("scroll", showRail, { passive: true });
addEventListener("resize", () => { if (!rail.hidden) layoutRail(); });
rail.addEventListener("pointerleave", () => { if (!scrubbing) showRail(); });
// Scrub.
function scrubTo(clientY) {
  const box = railTrack.getBoundingClientRect();
  const fraction = Math.min(1, Math.max(0, (clientY - box.top) / box.height));
  const section = sectionAt(fraction);
  scrollTo({ top: fraction * (document.documentElement.scrollHeight - innerHeight), behavior: "instant" });
  railLabel.textContent = railName(section);
  railLabel.style.top = `${clientY - rail.getBoundingClientRect().top}px`;
  railLabel.hidden = false;
  markCurrent();
  return section;
}
let scrubSection = null;
rail.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  scrubbing = true;
  document.documentElement.setAttribute("data-scrubbing", "");
  rail.setPointerCapture(e.pointerId);
  // Right after a load some chapters may still have estimated sizes (00-core.js); a scrub needs exact ones.
  if (finishSizing()) layoutRail();
  history.replaceState({ ...history.state, ...position(), back: null }, ""); // Back returns here.
  scrubSection = scrubTo(e.clientY);
});
rail.addEventListener("pointermove", (e) => { if (scrubbing) scrubSection = scrubTo(e.clientY); });
const endScrub = () => {
  if (!scrubbing) return;
  scrubbing = false;
  document.documentElement.removeAttribute("data-scrubbing");
  railLabel.hidden = true;
  // Stay where the reader let go; a jump to the chapter start would move the page after the release.
  if (scrubSection) history.pushState({ overlays: [], target: null, marks: [], back: null, ...position() }, "");
  showRail();
};
rail.addEventListener("pointerup", endScrub);
rail.addEventListener("pointercancel", endScrub);
