document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-refresh-form]");
  const button = document.querySelector("[data-refresh-button]");
  if (!form || !button) return;

  form.addEventListener("submit", () => {
    button.disabled = true;
    button.classList.add("is-refreshing");
    button.setAttribute("aria-label", "Refreshing data");
    button.title = "Refreshing data";
  });

  if (button.classList.contains("is-complete")) {
    button.setAttribute("aria-label", "Refresh complete");
    button.title = "Refresh complete";
    window.setTimeout(() => {
      button.classList.remove("is-complete");
      button.setAttribute("aria-label", "Refresh data");
      button.title = "Refresh data";
      window.history.replaceState({}, "", window.location.pathname);
    }, 1800);
  }
});
