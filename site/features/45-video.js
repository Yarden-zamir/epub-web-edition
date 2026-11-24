// Videos: a printed QR code that links to YouTube gets a player on the web.
// Nothing loads from YouTube until the reader presses play (privacy and page weight).
function youtubeTarget(href) {
  let url;
  try { url = new URL(href); } catch { return null; }
  if (url.hostname !== "www.youtube.com" && url.hostname !== "youtube.com") return null;
  const id = url.searchParams.get("v");
  if (!id || !/^[\w-]{11}$/.test(id)) return null;
  const start = Number.parseInt(url.searchParams.get("t") ?? "0", 10);
  return { id, start: Number.isFinite(start) ? start : 0 };
}
for (const link of reading.querySelectorAll("figure a.qr-link")) {
  const target = youtubeTarget(link.href);
  if (!target) continue;
  const figure = link.closest("figure");
  const label = figure.querySelector("figcaption .caption")?.textContent.trim() || "סרטון";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "video-play";
  button.setAttribute("aria-label", `הפעלת הסרטון: ${label}`);
  const thumb = document.createElement("img");
  thumb.src = `https://i.ytimg.com/vi/${target.id}/hqdefault.jpg`;
  thumb.alt = "";
  thumb.loading = "lazy";
  const icon = document.createElement("span");
  icon.className = "video-icon";
  icon.setAttribute("aria-hidden", "true");
  button.append(thumb, icon);
  const box = document.createElement("div");
  box.className = "video";
  box.append(button);
  button.addEventListener("click", () => {
    const frame = document.createElement("iframe");
    frame.src = `https://www.youtube-nocookie.com/embed/${target.id}?autoplay=1&start=${target.start}`;
    frame.title = label;
    frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    frame.allowFullscreen = true;
    box.replaceChildren(frame);
    frame.focus();
  });
  figure.classList.add("has-video");
  const watch = document.createElement("a");
  Object.assign(watch, { href: link.href, className: "video-link", target: "_blank", rel: "noopener", textContent: "צפייה ב־YouTube" });
  figure.querySelector("figcaption")?.append(watch);
  figure.insertBefore(box, figure.querySelector("figcaption"));
}

