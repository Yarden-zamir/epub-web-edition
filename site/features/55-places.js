// Places map, right after the printed contents (build: tools/web/70_places.py). The list under it works without JavaScript.
// API for other features: openPlace(id) scrolls to the map, flies to the place and opens its card. It returns a
// promise that settles when the card is open, and rejects for an unknown place ID. Any open overlay closes first (goTo).
const placesMap = document.getElementById("places-map");
const places = placesMap ? JSON.parse(byId("places-data").textContent) : [];
const placeById = new Map(places.map((p) => [p.id, p]));
let placesReady = null;
// A place card: the name, a sentence about the place, its chapters as pills and its photos.
// Desktop shows it in a map popup; a phone shows it as a sheet at the bottom of the map.
function placeCard(p, close) {
  const card = document.createElement("div");
  card.className = "place-card";
  card.dir = "rtl";
  const title = document.createElement("h3");
  title.className = "pc-title";
  title.textContent = p.name;
  const text = document.createElement("p");
  text.className = "pc-desc";
  text.textContent = p.description;
  // A "book" description quotes the book at p.source; an "edition" description is the edition's own, with an outside source.
  const source = document.createElement("a");
  source.className = "pc-source";
  if (p.description_kind === "edition") {
    Object.assign(source, { href: p.description_url, target: "_blank", rel: "noopener", textContent: "מקור התיאור ↗" });
  } else {
    Object.assign(source, { href: p.source, textContent: "מתוך הספר" });
  }
  const chapters = document.createElement("div");
  chapters.className = "pc-chapters";
  for (const c of p.chapters) {
    const a = document.createElement("a");
    a.href = c.href;
    a.textContent = c.title;
    chapters.append(a);
  }
  card.append(title, text, source, chapters);
  if (p.figures.length) {
    const thumbs = document.createElement("div");
    thumbs.className = "pc-thumbs";
    for (const f of p.figures) {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("aria-label", `הצגת התמונה: ${f.alt}`);
      const img = document.createElement("img");
      Object.assign(img, { src: f.thumb, alt: "", width: 64, height: 64, loading: "lazy" });
      button.append(img);
      button.addEventListener("click", () => openFigure(byId(f.href.slice(1))));
      thumbs.append(button);
    }
    card.append(thumbs);
  }
  card.addEventListener("click", (e) => {
    const link = e.target.closest("a[href^='#']");
    if (!link) return;
    e.preventDefault();
    close();
    // Only a "book" description is the book's own text, so only it is highlighted at its source.
    // A quote cut short ends in "…", which is not in the book text.
    const quote = p.description.endsWith("…") ? p.description.slice(0, -1).trim() : p.description;
    goTo(link.getAttribute("href").slice(1), { marks: link === source ? [quote] : [] });
  });
  return card;
}
if (placesMap) {
  // The box shows at once at its full size, in the mat colour, so the page does not move when the map draws.
  // Without the script it stays hidden.
  placesMap.hidden = false;
  placesReady = whenNear(placesMap, () => {
    const map = makeMap(placesMap, { label: "מפת המקומות בספר" });
    // The first view holds the Dead Sea region: the places within 75 km of the median place.
    // Places outside it stay on the map; a place marked "far" (abroad) also gets a chip that flies there.
    const near = places.filter((p) => !p.far);
    const median = (values) => values.toSorted((a, b) => a - b)[Math.floor(values.length / 2)];
    const middle = L.latLng(median(near.map((p) => p.lat)), median(near.map((p) => p.lon)));
    const core = near.filter((p) => middle.distanceTo([p.lat, p.lon]) < 75_000);
    const home = L.latLngBounds(core.map((p) => [p.lat, p.lon])).pad(0.08);
    map.fitBounds(home);
    const sheet = document.createElement("div");
    sheet.className = "map-sheet";
    sheet.hidden = true;
    L.DomEvent.disableClickPropagation(sheet);
    L.DomEvent.disableScrollPropagation(sheet);
    placesMap.append(sheet);
    let selected = null;
    const deselect = () => {
      selected?.getElement()?.classList.remove("selected");
      selected = null;
      sheet.hidden = true;
    };
    const phone = () => placesMap.clientWidth < 560;
    const select = (p) => {
      const marker = pins.markers.get(p.id);
      deselect();
      map.closePopup();
      selected = marker;
      marker.getElement().classList.add("selected");
      const card = placeCard(p, () => { map.closePopup(); deselect(); });
      if (phone()) {
        const close = document.createElement("button");
        close.type = "button";
        close.className = "sheet-close";
        close.textContent = "×";
        close.setAttribute("aria-label", "סגירה");
        close.addEventListener("click", () => { const m = selected; deselect(); m?.getElement()?.focus(); });
        sheet.replaceChildren(close, card);
        sheet.hidden = false;
        sheet.scrollTop = 0;
        // Keep the pin in the part of the map above the sheet.
        const room = placesMap.clientHeight - sheet.offsetHeight;
        const at = map.latLngToContainerPoint(marker.getLatLng());
        if (at.y > room - 24 || at.y < 24 || at.x < 24 || at.x > placesMap.clientWidth - 24) {
          map.panBy([at.x - placesMap.clientWidth / 2, at.y - room / 2], { duration: mapMotion() || undefined, animate: mapMotion() > 0 });
        }
        return;
      }
      const [dx, dy] = pins.offset(marker);
      L.popup({ maxWidth: 320, minWidth: 260, className: "place-popup", autoPanPadding: [24, 24], offset: [dx, dy - 8] })
        .setLatLng(marker.getLatLng()).setContent(card).openOn(map);
    };
    map.on("popupclose", () => { if (!phone()) deselect(); });
    map.on("click", deselect);
    const pins = addPins(map, places.map((p) => ({ ...p, weight: p.chapters.length })), { className: "place-pin", onSelect: select });
    // Each place keeps its own colour on the map: its pin dot and selection ring take --place-N (70_places.py).
    // Figure maps without places keep the one --pin colour of 50-maps.css.
    for (const p of places) pins.markers.get(p.id).getElement().style.setProperty("--pin", `var(--place-${p.n})`);
    // Places outside the first view stay in reach: one button shows every place except those marked "far",
    // and each "far" place (abroad) gets a chip that flies there.
    const all = L.latLngBounds(near.map((p) => [p.lat, p.lon])).pad(0.05);
    const far = places.filter((p) => p.far);
    const outside = near.some((p) => !home.contains([p.lat, p.lon]));
    const fly = (target, zoom) => (mapMotion()
      ? (Array.isArray(zoom) ? map.flyToBounds(target, { duration: 0.8 }) : map.flyTo(target, zoom, { duration: 1.2 }))
      : (Array.isArray(zoom) ? map.fitBounds(target) : map.setView(target, zoom)));
    if (far.length || outside) {
      const Chips = L.Control.extend({ options: { position: "topleft" }, onAdd() {
        const box = L.DomUtil.create("div", "map-chips");
        box.dir = "rtl";
        L.DomEvent.disableClickPropagation(box);
        const chip = (text, onClick, dot) => {
          const b = document.createElement("button");
          b.type = "button";
          if (dot) b.append(document.createElement("i"));
          b.append(text);
          b.addEventListener("click", onClick);
          box.append(b);
          return b;
        };
        const back = chip("חזרה לים המלח", () => { fly(home, []); back.hidden = true; });
        back.hidden = true;
        if (outside) chip("כל המקומות", () => { fly(all, []); back.hidden = false; });
        for (const p of far) {
          chip(`מחוץ למפה: ${p.name}`, () => {
            back.hidden = false;
            if (mapMotion()) map.once("moveend", () => select(p));
            fly([p.lat, p.lon], 9);
            if (!mapMotion()) select(p);
          }, true).style.setProperty("--pin", `var(--place-${p.n})`);
        }
        box.append(back);
        return box;
      } });
      new Chips().addTo(map);
    }
    return { map, markers: pins.markers, select };
  });
  placesReady.catch((err) => { placesMap.hidden = true; console.error(err); });
  byId("places").querySelector(".places-list").setAttribute("data-live", "");
}
// Show one place: scroll the map into view, fly to the place and open its card.
async function openPlace(id) {
  const p = placeById.get(id);
  if (!p) throw new Error(`reader.js: unknown place ${id}`);
  goTo("places");
  // The map draws when it comes near the viewport; scrolling there triggers it.
  const { map, markers, select } = await placesReady;
  const zoom = Math.max(map.getZoom(), 11);
  if (mapMotion() && map.getBounds().contains([p.lat, p.lon])) {
    await new Promise((resolve) => { map.once("moveend", resolve); map.flyTo([p.lat, p.lon], zoom, { duration: 0.6 }); });
  } else {
    map.setView([p.lat, p.lon], zoom, { animate: false });
  }
  select(p);
  markers.get(id).getElement().focus({ preventScroll: true });
}
// The list: each name opens its place on the map.
for (const li of document.querySelectorAll(".places-list[data-live] li")) {
  const name = li.querySelector(".place-name");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "place-name";
  button.textContent = name.textContent;
  button.addEventListener("click", () => openPlace(li.id.slice("place-".length)));
  name.replaceWith(button);
}
// Printed contents: a dot per place after each chapter that has places; the dots open pills that open the map.
const placesByChapter = new Map();
for (const p of places) for (const c of p.chapters) {
  if (!placesByChapter.has(c.chapter)) placesByChapter.set(c.chapter, []);
  if (!placesByChapter.get(c.chapter).includes(p)) placesByChapter.get(c.chapter).push(p);
}
for (const [chapter, list] of placesByChapter) {
  const item = tocDialog.querySelector(`.toc-item[data-chapter="${CSS.escape(chapter)}"] > a`);
  if (item) {
    const dots = document.createElement("span");
    dots.className = "toc-places";
    dots.title = list.map((p) => p.name).join(", ");
    dots.setAttribute("aria-hidden", "true");
    // At most five marks, so a row never outgrows the panel: four dots and "+N" when there are more. The title names all.
    const shown = list.length > 5 ? list.slice(0, 4) : list;
    for (const p of shown) {
      const dot = document.createElement("i");
      dot.style.setProperty("--place", `var(--place-${p.n})`);
      dots.append(dot);
    }
    if (shown.length < list.length) dots.append(`\u2066+${list.length - shown.length}\u2069`); // Isolated: reads "+4" in a right-to-left row.
    item.append(dots);
  }
  for (const link of reading.querySelectorAll(`ol.contents a[href="#${CSS.escape(chapter)}"]`)) {
    const li = link.closest("li");
    const dots = document.createElement("button");
    dots.type = "button";
    dots.className = "place-dots";
    dots.setAttribute("aria-expanded", "false");
    dots.setAttribute("aria-label", `מקומות בפרק: ${list.map((p) => p.name).join(", ")}`);
    const pills = document.createElement("div");
    pills.className = "place-pills";
    pills.hidden = true;
    for (const p of list) {
      const dot = document.createElement("i");
      dot.style.setProperty("--place", `var(--place-${p.n})`);
      dots.append(dot);
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "place-pill";
      pill.style.setProperty("--place", `var(--place-${p.n})`);
      pill.append(document.createElement("i"), p.name);
      pill.addEventListener("click", () => openPlace(p.id));
      pills.append(pill);
    }
    dots.addEventListener("click", () => {
      pills.hidden = !pills.hidden;
      dots.setAttribute("aria-expanded", String(!pills.hidden));
    });
    li.append(dots, pills);
  }
}
