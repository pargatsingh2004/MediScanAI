/**
 * MediScanAI Healthcare Intelligence — Global Core Utilities
 * Vanilla JavaScript (No React / No Next.js / No Frameworks)
 */

const HealthcareApp = {
  /**
   * Helper to get CSRF token from cookies
   */
  getCsrfToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, 10) === "csrftoken=") {
          cookieValue = decodeURIComponent(cookie.substring(10));
          break;
        }
      }
    }
    return cookieValue || "";
  },

  /**
   * Universal JSON fetch helper with CSRF protection
   */
  async fetchJson(url, options = {}) {
    const defaultHeaders = {
      "Accept": "application/json",
      "X-CSRFToken": this.getCsrfToken(),
    };

    if (!(options.body instanceof FormData)) {
      defaultHeaders["Content-Type"] = "application/json";
    }

    const mergedOptions = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {}),
      },
    };

    const res = await fetch(url, mergedOptions);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || data.detail || `Request failed with status ${res.status}`);
    }
    return data;
  },

  /**
   * Show a temporary toast message
   */
  showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 8px;
        pointer-events: none;
      `;
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    const bg = type === "error" ? "#f43f5e" : type === "success" ? "#10b981" : "#0d9488";
    toast.style.cssText = `
      background: ${bg};
      color: #fff;
      padding: 10px 18px;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 500;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      pointer-events: auto;
      transition: all 0.3s ease;
      opacity: 0;
      transform: translateY(10px);
    `;
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateY(0)";
    });

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  /**
   * Modal helper
   */
  openModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.add("active");
  },

  closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.remove("active");
  },
};

// Auto-bind close buttons for all modals
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".modal-close, [data-modal-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const modal = btn.closest(".modal-overlay");
      if (modal) modal.classList.remove("active");
    });
  });
});
