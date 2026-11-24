// Navigation bar: transparent only at the very top; solid as soon as the page scrolls more than the bar's height,
// so the hero never slides under a see-through bar.
const nav = byId("nav");
const setSolid = () => nav.toggleAttribute("data-solid", scrollY > nav.offsetHeight);
addEventListener("scroll", setSolid, { passive: true });
setSolid();
// The bar's download button shows once the hero's download button is out of view (above the bar).
new IntersectionObserver(([entry]) => {
  nav.toggleAttribute("data-download", !entry.isIntersecting && entry.boundingClientRect.top < innerHeight);
}, { rootMargin: "-64px 0px 0px 0px" }).observe(byId("hero-download"));
// The bar shows the full title when it fits and the author's name when it does not.
const navTitle = nav.querySelector(".nav-title");
const navTitleFull = navTitle.querySelector(".nav-title-full");
new ResizeObserver(() => {
  navTitle.removeAttribute("data-short");
  navTitle.toggleAttribute("data-short", navTitleFull.offsetWidth > navTitle.clientWidth);
}).observe(navTitle);

// E-reader menu: one popover, placed under whichever chevron opened it.
const sendMenu = byId("send-menu");
let menuAnchor = null;
for (const button of document.querySelectorAll("[popovertarget='send-menu']")) {
  button.addEventListener("click", () => { menuAnchor = button; });
}
overlayOpeners["send-menu"] = () => sendMenu.showPopover();
sendMenu.addEventListener("toggle", (e) => {
  if (e.newState === "closed") { overlayClosed(sendMenu); return; }
  if (!overlayStack.includes("send-menu")) openOverlay(sendMenu, () => {});
  if (!menuAnchor) return;
  const box = menuAnchor.getBoundingClientRect();
  const width = sendMenu.offsetWidth, height = sendMenu.offsetHeight;
  const rtl = document.dir === "rtl";
  const left = Math.min(innerWidth - width - 8, Math.max(8, rtl ? box.left : box.right - width));
  const below = box.bottom + 6 + height <= innerHeight;
  sendMenu.style.left = `${left}px`;
  sendMenu.style.top = `${below ? box.bottom + 6 : Math.max(8, box.top - 6 - height)}px`;
});

