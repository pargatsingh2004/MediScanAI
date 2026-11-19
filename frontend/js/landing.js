(function () {
  "use strict";

  const themeKey = "ms-theme";
  const body = document.body;
  const themeButton = document.querySelector("[data-theme-toggle]");
  const zone = document.getElementById("guest-dropzone");
  const input = document.getElementById("guest-file");
  const analyzeButton = document.getElementById("guest-analyze");
  const result = document.getElementById("guest-result");
  const errorBox = document.getElementById("guest-error");
  const fileName = document.getElementById("guest-file-name");
  const fileNote = document.getElementById("guest-file-note");
  let selectedFile = null;
  let language = "en";

  function setTheme(theme) {
    const next = theme === "dark" ? "dark" : "light";
    body.classList.remove("dark", "light");
    body.classList.add(next);
    document.documentElement.style.colorScheme = next;
    try { window.localStorage.setItem(themeKey, next); } catch (_) { /* Storage can be disabled. */ }
    if (themeButton) themeButton.setAttribute("aria-label", next === "dark" ? "Switch to light theme" : "Switch to dark theme");
  }

  try {
    const saved = window.localStorage.getItem(themeKey);
    setTheme(saved === "dark" ? "dark" : "light");
  } catch (_) {
    setTheme("light");
  }

  themeButton?.addEventListener("click", function () {
    setTheme(body.classList.contains("dark") ? "light" : "dark");
  });

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.textContent = "";
    errorBox.hidden = true;
  }

  function acceptFile(file) {
    clearError();
    result.hidden = true;
    if (!file) return;
    const allowed = /\.(pdf|png|jpe?g)$/i.test(file.name);
    if (!allowed) {
      selectedFile = null;
      showError("Choose a PDF, PNG, or JPG medical report.");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      selectedFile = null;
      showError("The report must be 20 MB or smaller.");
      return;
    }
    selectedFile = file;
    fileName.textContent = file.name;
    fileNote.textContent = `${Math.max(1, Math.round(file.size / 1024))} KB · ${body.dataset.signedIn === "true" ? "Open your workspace to save this report." : "Analyze this first report for free."}`;
    analyzeButton.textContent = body.dataset.signedIn === "true" ? "Open Workspace" : "Analyze First Report Free";
  }

  zone?.addEventListener("click", function (event) {
    if (event.target !== input) input.click();
  });
  zone?.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input?.addEventListener("change", function () { acceptFile(input.files && input.files[0]); });
  ["dragenter", "dragover"].forEach(function (type) {
    zone?.addEventListener(type, function (event) {
      event.preventDefault();
      zone.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach(function (type) {
    zone?.addEventListener(type, function (event) {
      event.preventDefault();
      zone.classList.remove("dragging");
    });
  });
  zone?.addEventListener("drop", function (event) {
    const file = event.dataTransfer && event.dataTransfer.files[0];
    acceptFile(file);
  });

  document.querySelectorAll("[data-language]").forEach(function (button) {
    button.addEventListener("click", function () {
      language = button.dataset.language || "en";
      document.querySelectorAll("[data-language]").forEach(function (item) { item.classList.toggle("active", item === button); });
    });
  });

  function addText(parent, tag, value, className) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = value == null ? "" : String(value);
    parent.appendChild(node);
    return node;
  }

  function addList(panel, title, values, fallback) {
    addText(panel, "h3", title, "preview-panel-title");
    if (!Array.isArray(values) || values.length === 0) {
      addText(panel, "p", fallback, "preview-empty");
      return;
    }
    const list = document.createElement("ul");
    list.className = "preview-list";
    values.slice(0, 4).forEach(function (value) {
      const item = document.createElement("li");
      item.className = "preview-item";
      if (typeof value === "string") {
        addText(item, "span", value);
      } else if (value && typeof value === "object") {
        const label = value.name || value.testName || value.medicineName || value.title || "Report item";
        const details = value.value || value.dosage || value.schedule || value.explanation || value.details || "";
        addText(item, "strong", label);
        if (details) addText(item, "span", details);
        if (value.referenceRange) addText(item, "small", `Reference: ${value.referenceRange} · ${value.severity || value.status || "review"}`);
      }
      list.appendChild(item);
    });
    panel.appendChild(list);
  }

  function renderPreview(preview) {
    result.replaceChildren();
    const analysis = preview.analysis || {};
    const insights = preview.insights || {};
    const head = document.createElement("div");
    head.className = "preview-head";
    const title = document.createElement("div");
    addText(title, "div", "First Report Preview", "preview-eyebrow");
    addText(title, "div", preview.filename || "Medical report", "preview-title");
    head.appendChild(title);
    addText(head, "div", "Based on text extracted from this document", "preview-meta");
    result.appendChild(head);
    addText(result, "p", analysis.plainLanguageSummary || insights.summary || "The report was processed. Review the extracted values with your clinician.", "preview-summary");
    const badges = document.createElement("div");
    badges.className = "preview-badges";
    addText(badges, "span", `Risk: ${String(insights.overallRisk || "unknown").toUpperCase()}`, "preview-badge");
    addText(badges, "span", `Findings: ${(insights.abnormalFindings || []).length}`, "preview-badge");
    addText(badges, "span", `Medicines: ${(analysis.medicines || []).length}`, "preview-badge");
    result.appendChild(badges);
    const grid = document.createElement("div");
    grid.className = "preview-grid";
    const findings = document.createElement("section");
    findings.className = "preview-panel";
    addList(findings, "Key Findings", insights.abnormalFindings, "No abnormal values were identified by this screening.");
    const medicines = document.createElement("section");
    medicines.className = "preview-panel";
    addList(medicines, "Medicines in Report", analysis.medicines, "No medicine names were recognized in the report.");
    const precautions = document.createElement("section");
    precautions.className = "preview-panel";
    addList(precautions, "Precautions", analysis.precautions, "No specific precautions were generated.");
    const questions = document.createElement("section");
    questions.className = "preview-panel";
    addList(questions, "Follow-up Questions", analysis.followUpQuestions, "Discuss the report with your clinician.");
    [findings, medicines, precautions, questions].forEach(function (panel) { grid.appendChild(panel); });
    result.appendChild(grid);
    const gate = document.createElement("div");
    gate.className = "preview-gate";
    addText(gate, "p", "This preview is not saved to report history. Create an account to keep reports, compare results, set reminders, and continue with assistant chat.", "preview-gate-copy");
    const actions = document.createElement("div");
    actions.className = "preview-gate-actions";
    const create = document.createElement("a");
    create.className = "btn btn-solid";
    create.href = "/signup/";
    create.textContent = "Create Free Account";
    const signIn = document.createElement("a");
    signIn.className = "btn btn-outline";
    signIn.href = "/login/";
    signIn.textContent = "Sign In";
    actions.append(create, signIn);
    gate.appendChild(actions);
    result.appendChild(gate);
    result.hidden = false;
  }

  analyzeButton?.addEventListener("click", async function () {
    if (body.dataset.signedIn === "true") {
      window.location.assign("/workspace/");
      return;
    }
    if (!selectedFile) {
      input.click();
      return;
    }
    clearError();
    analyzeButton.disabled = true;
    analyzeButton.textContent = "Analyzing report…";
    const form = new FormData();
    form.append("file", selectedFile);
    form.append("language", language);
    try {
      const response = await fetch("/api/guest-report-preview", { method: "POST", body: form, credentials: "same-origin" });
      const data = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        if (data.requiresAuth || data.limitReached) {
          showError("Your free report preview has been used. Sign in or create an account to continue.");
        } else {
          showError(data.error || "Unable to analyze this report. Please try a clearer PDF or image.");
        }
        return;
      }
      renderPreview(data.preview || {});
    } catch (_) {
      showError("Unable to reach the report service. Check your connection and try again.");
    } finally {
      analyzeButton.disabled = false;
      analyzeButton.textContent = "Analyze First Report Free";
    }
  });
}());
