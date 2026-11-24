// Back chip: after a jump from a link in the text (a note, a cross-link, a glossary source, a map place), a small chip
// names where Back goes, for five seconds (longer while the pointer is on it or it has focus). Pressing it is Back.
const backChip = document.createElement("button");
backChip.type = "button";
backChip.className = "back-chip";
backChip.hidden = true;
document.body.append(backChip);
let backTimer = 0;
const hideBackChip = () => { clearTimeout(backTimer); backChip.hidden = true; };
const waitBackChip = () => { clearTimeout(backTimer); backTimer = setTimeout(hideBackChip, 5000); };
addEventListener("reader:jump", (e) => {
  const from = document.getElementById(e.detail.back.id);
  const chapter = from?.closest(".doc > section[id]")?.id;
  const name = chapter && tocDialog.querySelector(`[data-chapter="${CSS.escape(chapter)}"] :is(.toc-name, .toc-part-title)`)?.textContent;
  const text = Object.assign(document.createElement("span"), { className: "back-text", textContent: name ? `חזרה אל: ${name}` : "חזרה למקום הקודם" });
  backChip.replaceChildren(Object.assign(document.createElement("span"), { className: "back-arrow", ariaHidden: "true" }), text);
  backChip.hidden = false;
  waitBackChip();
});
backChip.addEventListener("click", () => { hideBackChip(); history.back(); });
backChip.addEventListener("pointerenter", () => clearTimeout(backTimer));
backChip.addEventListener("focus", () => clearTimeout(backTimer));
backChip.addEventListener("pointerleave", waitBackChip);
backChip.addEventListener("blur", waitBackChip);
addEventListener("popstate", hideBackChip);
