document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-refresh-form]");
  const button = document.querySelector("[data-refresh-button]");
  if (!form || !button) return;

  form.addEventListener("submit", () => {
    button.disabled = true;
    button.textContent = "Refreshing…";
  });
});
