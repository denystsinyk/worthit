async function initPlaidLink(mode) {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const tokenResp = await fetch("/api/link-token", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ mode }),
  });
  const { link_token } = await tokenResp.json();

  const handler = Plaid.create({
    token: link_token,
    onSuccess: async (public_token) => {
      if (mode === "update") {
        // Update mode refreshes credentials on the existing Item in place -
        // there's no new public_token to exchange.
        await fetch("/api/reauth-complete", {
          method: "POST",
          headers: { "X-CSRF-Token": csrfToken },
        });
      } else {
        await fetch("/api/exchange-token", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
          body: JSON.stringify({ public_token }),
        });
      }
      window.location.href = "/";
    },
    onExit: (err) => {
      if (err) console.error("Plaid Link exited with error:", err);
    },
  });
  handler.open();
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("link-button");
  if (btn) {
    btn.addEventListener("click", () => initPlaidLink(btn.dataset.mode || "link"));
  }
});
