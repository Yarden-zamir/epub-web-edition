// Offline reading: the service worker (sw.js, written by tools/web/99_offline.py) keeps the book readable without a
// network. In the installed app (home screen) the whole book is saved in the background; no button.
const SAVED_KEY = `reader-saved:${document.documentElement.dataset.bookId}`;
const installedApp = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

function toast(text) {
  const box = document.createElement("div");
  box.className = "toast";
  box.setAttribute("role", "status");
  box.textContent = text;
  document.body.append(box);
  requestAnimationFrame(() => box.classList.add("shown"));
  setTimeout(() => {
    box.classList.remove("shown");
    box.addEventListener("transitionend", () => box.remove(), { once: true });
    setTimeout(() => box.remove(), 1000); // No transition with reduced motion.
  }, 4000);
}

async function saveWholeBook() {
  const registration = await navigator.serviceWorker.ready;
  // Ask the browser not to evict the saved book when space runs low. It may say no; the book then stays cached
  // as long as the browser keeps it.
  await navigator.storage?.persist?.();
  // The map library is the one file from another host that every map needs (LEAFLET in 50-maps.js).
  registration.active.postMessage({ type: "save-all", extra: [`${LEAFLET}leaflet.js`, `${LEAFLET}leaflet.css`] });
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.addEventListener("message", (e) => {
    if (e.data?.type !== "saved" || e.data.total === 0) return;
    let told = false;
    try { told = localStorage.getItem(SAVED_KEY) === "1"; localStorage.setItem(SAVED_KEY, "1"); } catch { /* Storage blocked: tell every time. */ }
    if (!told) toast("הספר נשמר במכשיר, ואפשר לקרוא בו גם בלי חיבור לרשת");
  });
  // After the page loads, so the worker and its downloads never compete with the first screen.
  addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js", { updateViaCache: "none" }).catch((error) => console.error("sw:", error));
    if (installedApp()) saveWholeBook();
  });
  addEventListener("appinstalled", saveWholeBook);
  // On the first visit the worker takes over after some images loaded. Hand it those, so they read offline too.
  if (!navigator.serviceWorker.controller) {
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      const base = new URL(".", location.href).href;
      const paths = performance.getEntriesByType("resource")
        .filter((e) => e.initiatorType === "img" && e.name.startsWith(base))
        .map((e) => decodeURIComponent(e.name.slice(base.length)));
      navigator.serviceWorker.controller?.postMessage({ type: "save-read", paths });
    }, { once: true });
  }
}
