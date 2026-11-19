(() => {
  const search = document.getElementById("report-filter");
  const rows = Array.from(document.querySelectorAll("[data-report-row]"));
  const emptyState = document.getElementById("no-matching-reports");

  if (search) {
    search.addEventListener("input", () => {
      const query = search.value.trim().toLocaleLowerCase();
      let visible = 0;
      rows.forEach((row) => {
        const matches = row.textContent.toLocaleLowerCase().includes(query);
        row.hidden = !matches;
        if (matches) visible += 1;
      });
      if (emptyState) emptyState.hidden = visible !== 0;
    });
  }
})();
