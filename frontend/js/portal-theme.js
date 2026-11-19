(function () {
  "use strict";
  try {
    const theme = localStorage.getItem("ms-theme");
    if (theme === "dark" || theme === "light") {
      document.body.classList.remove("dark", "light");
      document.body.classList.add(theme);
      document.documentElement.style.colorScheme = theme;
    }
  } catch (_) { /* Use the light theme if storage is unavailable. */ }
  document.querySelector("[data-theme-toggle]")?.addEventListener("click", function () {
    const theme = document.body.classList.contains("dark") ? "light" : "dark";
    document.body.classList.remove("dark", "light");
    document.body.classList.add(theme);
    document.documentElement.style.colorScheme = theme;
    try { localStorage.setItem("ms-theme", theme); } catch (_) { /* optional */ }
  });
}());
