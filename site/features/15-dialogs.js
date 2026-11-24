// Dialogs
const onDialogOpen = {}; // Dialog ID -> function run right after it opens.
for (const button of document.querySelectorAll("[data-open]:not([data-open='search-dialog'])")) {
  const dialog = byId(button.dataset.open);
  overlayOpeners[dialog.id] ??= () => { dialog.showModal(); onDialogOpen[dialog.id]?.(); };
  button.addEventListener("click", () => openOverlay(dialog, overlayOpeners[dialog.id]));
}
for (const dialog of document.querySelectorAll("dialog")) {
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog || e.target.closest("[data-close]")) dialog.close();
  });
  dialog.addEventListener("close", () => overlayClosed(dialog));
}
byId("toc-dialog").addEventListener("click", (e) => {
  const link = e.target.closest("a[href^='#']");
  if (!link) return;
  e.preventDefault();
  goTo(link.getAttribute("href").slice(1), { marks: link.dataset.quote ? [link.dataset.quote] : [] });
});

