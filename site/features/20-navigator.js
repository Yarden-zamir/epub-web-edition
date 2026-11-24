// Navigator: chapters (with a filter) and, when the book has one, a timeline tab.
const tocDialog = byId("toc-dialog");
const tabs = [...tocDialog.querySelectorAll("[role='tab']")];
function selectTab(tab) {
  for (const t of tabs) {
    const on = t === tab;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    byId(t.getAttribute("aria-controls")).hidden = !on;
  }
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
  tocDialog.querySelector(".toc-item:not([hidden]) a")?.click();
});
tocFilter.addEventListener("input", () => {
  const words = tokenize(tocFilter.value).map((t) => t.word);
  const matches = (el) => {
    const text = tokenize(el.textContent).map((t) => t.word).join(" ");
    return words.every((w) => text.includes(w));
  };
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
});
onDialogOpen["toc-dialog"] = () => {
  // The current chapter: the last top-level section that starts above a third of the screen.
  let current = null;
  for (const section of reading.querySelectorAll(".doc > section[id]")) {
    if (section.getBoundingClientRect().top < innerHeight / 3) current = section.id;
    else break;
  }
  for (const link of tocDialog.querySelectorAll("[aria-current]")) link.removeAttribute("aria-current");
  const link = current && tocDialog.querySelector(`[data-chapter="${CSS.escape(current)}"] > a`);
  if (link) {
    link.setAttribute("aria-current", "location");
    if (tabs[0].getAttribute("aria-selected") === "true") link.scrollIntoView({ block: "center" });
  }
};

