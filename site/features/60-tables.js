// Data tables: a header button sorts by its column; a second press reverses the order.
for (const table of reading.querySelectorAll("table.data-table")) {
  const body = table.tBodies[0];
  for (const button of table.querySelectorAll("button[data-sort]")) {
    button.addEventListener("click", () => {
      const col = Number(button.dataset.sort);
      const th = button.parentElement;
      const descending = th.getAttribute("aria-sort") !== "descending";
      for (const other of table.querySelectorAll("th[aria-sort]")) other.removeAttribute("aria-sort");
      th.setAttribute("aria-sort", descending ? "descending" : "ascending");
      const key = (row) => {
        const cell = row.children[col];
        return cell.dataset.value !== undefined ? Number(cell.dataset.value) : cell.textContent.trim();
      };
      const rows = [...body.rows].sort((a, b) => {
        const x = key(a), y = key(b);
        const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "he");
        return descending ? -order : order;
      });
      body.append(...rows);
    });
  }
}

