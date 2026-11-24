// Figure viewer: shows the site-only original when enhancements.json lists one.
const viewer = byId("figure-dialog");
reading.addEventListener("click", (e) => {
  const img = e.target.closest("figure[id] img");
  if (!img || img.closest(".video")) return; // A video thumbnail starts the player instead.
  openFigure(img.closest("figure"));
});
function openFigure(figure) {
  const img = figure.querySelector("img");
  const original = figure.dataset.original;
  const viewerImg = byId("viewer-img");
  viewerImg.src = original ?? img.currentSrc ?? img.src;
  viewerImg.alt = img.alt;
  byId("viewer-caption").replaceChildren(...[...figure.querySelectorAll("figcaption > *")].map((n) => n.cloneNode(true)));
  const link = byId("viewer-original");
  link.hidden = !original;
  if (original) link.href = original;
  openOverlay(viewer, () => viewer.showModal());
}

