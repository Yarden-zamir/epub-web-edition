// Poems: a line that wraps gets .wraps (02-book.css), so its last part sits at the far edge and never looks like a
// line that steps in (indent-N). Measured when the poem comes near, and again for those poems when the width changes.
// Reads first, then writes, so one poem costs one layout.
const measuredPoems = new Set();
function markWraps(poem) {
  const lines = [...poem.querySelectorAll(".line")];
  for (const line of lines) line.classList.remove("wraps");
  const wraps = lines.map((line) => line.getBoundingClientRect().height > parseFloat(getComputedStyle(line).lineHeight) * 1.5);
  lines.forEach((line, i) => line.classList.toggle("wraps", wraps[i]));
}
for (const poem of reading.querySelectorAll("section.poem")) {
  onNear(poem, () => { measuredPoems.add(poem); markWraps(poem); });
}
{
  let width = innerWidth, timer = 0;
  addEventListener("resize", () => {
    if (innerWidth === width) return;
    width = innerWidth;
    clearTimeout(timer);
    timer = setTimeout(() => { for (const poem of measuredPoems) markWraps(poem); }, 200);
  });
}
