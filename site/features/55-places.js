// Places map, right after the printed contents. The numbered list under it works without JavaScript.
const placesMap = document.getElementById("places-map");
const places = placesMap ? JSON.parse(byId("places-data").textContent) : [];
const placeById = new Map(places.map((p) => [p.id, p]));
let placesReady = null;
// A place card: name with its colour, the book's sentence about it, its chapters as pills and its photos.
// Desktop shows it in a map popup; a phone shows it as a sheet at the bottom of the map.
function placeCard(p, close) {
  const card = document.createElement("div");
  card.className = "place-card";
  card.style.setProperty("--place", `var(--place-${p.n})`);
  const title = document.createElement("h3");
  title.className = "pc-title";
  const dot = document.createElement("i");
  dot.setAttribute("aria-hidden", "true");
  title.append(dot, p.name);
  const text = document.createElement("p");
  text.className = "pc-desc";
  text.textContent = p.description;
  // A "book" description quotes the book at p.source; an "edition" description is the edition's own, with an outside source.
  const source = document.createElement("a");
  source.className = "pc-source";
  if (p.description_kind === "edition") {
    Object.assign(source, { href: p.description_url, target: "_blank", rel: "noopener", textContent: "מקור התיאור" });
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
    // The description is a sentence from the book: highlight it at its source.
    // A quote cut short ends in "…", which is not in the book text.
    const quote = p.description.endsWith("…") ? p.description.slice(0, -1).trim() : p.description;
    goTo(link.getAttribute("href").slice(1), { marks: link === source ? [quote] : [] });
  });
  return card;
}
if (placesMap) {
  placesReady = whenNear(byId("places"), () => { // The map box is hidden until drawn, so watch its section.
    placesMap.hidden = false;
    const map = makeMap(placesMap);
    // The first view holds the Dead Sea region: the places within 75 km of the median place.
    // Places outside it stay on the map; a place marked "far" (abroad) also gets a chip that flies there.
    const near = places.filter((p) => !p.far);
    const median = (values) => values.toSorted((a, b) => a - b)[Math.floor(values.length / 2)];
    const middle = L.latLng(median(near.map((p) => p.lat)), median(near.map((p) => p.lon)));
    const core = near.filter((p) => middle.distanceTo([p.lat, p.lon]) < 75_000);
    const home = L.latLngBounds(core.map((p) => [p.lat, p.lon])).pad(0.05);
    map.fitBounds(home);
    const markers = new Map();
    const shift = new Map(); // Marker -> [dx, dy] from declutter, so the popup points at the drawn dot.
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
      const marker = markers.get(p.id);
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
        close.addEventListener("click", deselect);
        sheet.replaceChildren(close, card);
        sheet.hidden = false;
        if (!map.getBounds().pad(-0.15).contains(marker.getLatLng())) map.panTo(marker.getLatLng());
        return;
      }
      const [dx, dy] = shift.get(marker) ?? [0, 0];
      L.popup({ maxWidth: 320, minWidth: 240, className: "place-popup", autoPanPadding: [24, 24], offset: [dx, dy - 6] })
        .setLatLng(marker.getLatLng()).setContent(card).openOn(map);
    };
    map.on("popupclose", () => { if (!phone()) deselect(); });
    map.on("click", deselect);
    for (const p of places) {
      const icon = L.divIcon({ className: "place-pin", iconSize: [14, 14], iconAnchor: [7, 7],
        html: `<span class="pin-dot" style="--place: var(--place-${p.n})"></span><span class="pin-label" dir="rtl"></span>` });
      const marker = L.marker([p.lat, p.lon], { icon, keyboard: true, riseOnHover: true }).addTo(map);
      const el = marker.getElement();
      el.querySelector(".pin-label").textContent = p.name;
      el.setAttribute("role", "button");
      el.setAttribute("aria-label", p.name);
      marker.on("click", () => select(p));
      el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(p); } });
      markers.set(p.id, marker);
    }
    const far = places.filter((p) => p.far);
    if (far.length) {
      const Far = L.Control.extend({ options: { position: "bottomleft" }, onAdd() {
        const box = L.DomUtil.create("div", "map-chips");
        L.DomEvent.disableClickPropagation(box);
        const back = document.createElement("button");
        back.type = "button";
        back.textContent = "חזרה לתצוגה הראשונה";
        back.hidden = true;
        back.addEventListener("click", () => { map.fitBounds(home); back.hidden = true; });
        for (const p of far) {
          const chip = document.createElement("button");
          chip.type = "button";
          chip.style.setProperty("--place", `var(--place-${p.n})`);
          chip.append(document.createElement("i"), `רחוק מכאן: ${p.name}`);
          chip.addEventListener("click", () => { map.setView([p.lat, p.lon], 9); select(p); back.hidden = false; });
          box.append(chip);
        }
        box.append(back);
        return box;
      } });
      new Far().addTo(map);
    }
    // Markers closer than a marker's width push each other apart a little, so each stays visible and tappable.
    // The popup and tooltip keep the true position. Limit: a dense group at a far zoom spreads into a small cloud;
    // zooming in brings every marker back to its true spot.
    const declutter = () => {
      const items = [...markers.values()].map((m) => {
        const at = map.latLngToContainerPoint(m.getLatLng());
        return { m, x: at.x, y: at.y, x0: at.x, y0: at.y };
      });
      const gap = 16;
      for (let round = 0; round < 60; round++) {
        let moved = false;
        for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
          const a = items[i], b = items[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          const d = Math.hypot(dx, dy);
          if (d >= gap) continue;
          if (d < 0.01) { dx = Math.cos(i + j); dy = Math.sin(i + j); } // Same spot: pick a direction.
          const push = (gap - d) / 2 / Math.max(d, 0.01);
          a.x -= dx * push; a.y -= dy * push; b.x += dx * push; b.y += dy * push;
          moved = true;
        }
        if (!moved) break;
      }
      for (const it of items) {
        shift.set(it.m, [it.x - it.x0, it.y - it.y0]);
        it.m.getElement().style.translate = `${(it.x - it.x0).toFixed(1)}px ${(it.y - it.y0).toFixed(1)}px`;
      }
      layoutLabels();
    };
    // Name labels: places in more chapters first; a label that would overlap a shown label or another dot stays
    // hidden, and shows on hover, focus or selection.
    const byWeight = places.toSorted((a, b) => b.chapters.length - a.chapters.length || a.n - b.n);
    const layoutLabels = () => {
      const dots = [...markers.values()].map((m) => m.getElement().querySelector(".pin-dot").getBoundingClientRect());
      const shown = [];
      const hit = (a, b) => a.left < b.right + 2 && b.left < a.right + 2 && a.top < b.bottom + 1 && b.top < a.bottom + 1;
      const box = placesMap.getBoundingClientRect();
      for (const p of byWeight) {
        const el = markers.get(p.id).getElement();
        const label = el.querySelector(".pin-label");
        el.classList.remove("label-hidden");
        const r = label.getBoundingClientRect();
        const own = el.querySelector(".pin-dot").getBoundingClientRect();
        const inside = r.left >= box.left && r.right <= box.right && r.top >= box.top && r.bottom <= box.bottom;
        const clash = !inside || shown.some((s) => hit(r, s)) || dots.some((d) => d.left !== own.left && hit(r, d));
        el.classList.toggle("label-hidden", clash);
        if (!clash) shown.push(r);
      }
    };
    map.on("zoomend", declutter);
    map.on("moveend", layoutLabels);
    declutter();
    return { map, markers, select };
  });
  placesReady.catch((err) => { placesMap.hidden = true; console.error(err); });
  byId("places").querySelector(".places-list").setAttribute("data-live", "");
}
// Show one place: scroll the map into view, centre it and open its popup.
async function openPlace(id) {
  const p = placeById.get(id);
  if (!p) throw new Error(`reader.js: unknown place ${id}`);
  goTo("places");
  // The map draws when it comes near the viewport; scrolling there triggers it.
  const { map, select } = await placesReady;
  map.setView([p.lat, p.lon], Math.max(map.getZoom(), 11), { animate: false });
  select(p);
}
// The numbered list: each name opens its place on the map.
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
    for (const p of list) {
      const dot = document.createElement("i");
      dot.style.setProperty("--place", `var(--place-${p.n})`);
      dots.append(dot);
    }
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

