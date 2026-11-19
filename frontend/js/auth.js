(function () {
  "use strict";
  const form = document.getElementById("auth-form");
  if (!form) return;
  const message = document.getElementById("auth-message");
  const submit = document.getElementById("auth-submit");
  const emailInput = document.getElementById("auth-email");
  const passwordInput = document.getElementById("auth-password");
  const resendBox = document.getElementById("resend-verification");

  function cookie(name) {
    const entry = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(`${name}=`));
    return entry ? decodeURIComponent(entry.slice(name.length + 1)) : "";
  }
  function show(text, kind) {
    message.textContent = text;
    message.className = `portal-status ${kind || ""}`;
    message.hidden = false;
  }
  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Request failed. Please try again.");
    return data;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    message.hidden = true;
    const mode = form.dataset.mode;
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !password) return show("Enter your email address and password.", "error");
    if (mode === "signup") {
      const name = document.getElementById("auth-name").value.trim();
      const confirmation = document.getElementById("auth-confirm-password").value;
      const otpRow = document.getElementById("auth-otp-row");
      const otpInput = document.getElementById("auth-otp");
      if (otpRow && !otpRow.hidden) {
        if (!/^\d{6}$/.test(otpInput.value.trim())) return show("Enter the six-digit code from your email.", "error");
        submit.disabled = true;
        submit.textContent = "Verifying…";
        try {
          await post("/api/auth/verify-otp", { email, otp: otpInput.value.trim() });
          show("Email confirmed. Redirecting to sign in…", "success");
          window.setTimeout(() => { window.location.assign("/login/?confirmed=1"); }, 700);
        } catch (error) {
          show(error.message, "error");
        } finally {
          submit.disabled = false;
          submit.textContent = "Verify email";
        }
        return;
      }
      if (password.length < 8) return show("Password must be at least 8 characters long.", "error");
      if (password !== confirmation) return show("The passwords do not match.", "error");
      if (!document.getElementById("auth-terms").checked) return show("Please accept the Terms and review the Privacy information.", "error");
      submit.disabled = true;
      submit.textContent = "Creating account…";
      try {
        const data = await post("/api/auth/signup", { email, password, fullName: name });
        show(data.message || "Check your email to confirm your account.", "success");
        if (otpRow) {
          otpRow.hidden = false;
          otpInput.required = true;
          submit.textContent = "Verify email";
          passwordInput.disabled = true;
          document.getElementById("auth-confirm-password").disabled = true;
          document.getElementById("auth-name").disabled = true;
          document.getElementById("auth-terms").disabled = true;
        }
      } catch (error) {
        show(error.message, "error");
      } finally {
        submit.disabled = false;
        submit.textContent = otpRow && !otpRow.hidden ? "Verify email" : "Create account";
      }
      return;
    }
    submit.disabled = true;
    submit.textContent = "Signing in…";
    try {
      await post("/api/auth/login", { email, password });
      const next = form.dataset.next || "/workspace/";
      window.location.assign(next.startsWith("/") && !next.startsWith("//") ? next : "/workspace/");
    } catch (error) {
      show(error.message, "error");
      if (/confirm/i.test(error.message) && resendBox) resendBox.hidden = false;
    } finally {
      submit.disabled = false;
      submit.textContent = "Sign In";
    }
  });

  document.getElementById("forgot-password")?.addEventListener("click", async function () {
    const email = emailInput.value.trim();
    if (!email) return show("Enter your email address first.", "error");
    try {
      const data = await post("/api/auth/password-reset", { email });
      show(data.message, "success");
    } catch (error) { show(error.message, "error"); }
  });
  document.getElementById("resend-button")?.addEventListener("click", async function () {
    const email = emailInput.value.trim();
    if (!email) return show("Enter your email address first.", "error");
    try {
      const data = await post("/api/auth/resend", { email });
      show(data.message, "success");
    } catch (error) { show(error.message, "error"); }
  });

  const themeButton = document.querySelector("[data-theme-toggle]");
  themeButton?.addEventListener("click", function () {
    const next = document.body.classList.contains("dark") ? "light" : "dark";
    document.body.classList.remove("dark", "light");
    document.body.classList.add(next);
    document.documentElement.style.colorScheme = next;
    try { localStorage.setItem("ms-theme", next); } catch (_) { /* Storage can be disabled. */ }
  });
  try {
    const theme = localStorage.getItem("ms-theme");
    if (theme === "dark" || theme === "light") {
      document.body.classList.remove("dark", "light");
      document.body.classList.add(theme);
      document.documentElement.style.colorScheme = theme;
    }
  } catch (_) { /* Use the light default. */ }
}());
