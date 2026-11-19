(function () {
  "use strict";

  const state = { reports: [], selectedReportId: null, selectedReport: null, reminders: [], chart: null, alerted: new Set(), notificationReady: false, alarmAudio: null, savedHospitalIds: new Set(), savedDoctorIds: new Set() };
  const byId = (id) => document.getElementById(id);
  const sections = Array.from(document.querySelectorAll("[data-workspace-section]"));
  const tabs = Array.from(document.querySelectorAll("[data-tab]"));

  function getCookie(name) {
    const part = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith(`${name}=`));
    return part ? decodeURIComponent(part.slice(name.length + 1)) : "";
  }
  async function api(url, options) {
    const init = Object.assign({ credentials: "same-origin" }, options || {});
    const headers = new Headers(init.headers || {});
    if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (init.method && !["GET", "HEAD"].includes(init.method.toUpperCase())) headers.set("X-CSRFToken", getCookie("csrftoken"));
    init.headers = headers;
    const response = await fetch(url, init);
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      window.location.assign(`/login/?next=${encodeURIComponent(window.location.pathname)}`);
      const error = new Error(data.error || "Your session has expired.");
      error.status = 401;
      throw error;
    }
    if (!response.ok) {
      const error = new Error(data.error || data.detail || "The request could not be completed.");
      error.status = response.status;
      throw error;
    }
    return data;
  }
  function el(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined && value !== null) node.textContent = String(value);
    return node;
  }
  function showStatus(target, value, type) {
    if (!target) return;
    target.textContent = value || "";
    target.className = `portal-status ${type || ""}`;
    target.hidden = !value;
  }
  function dateLabel(value) {
    if (!value) return "Date unavailable";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }
  function selectedReport() { return state.reports.find((report) => report.id === state.selectedReportId) || null; }
  function showTab(name) {
    tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
    sections.forEach((section) => section.classList.toggle("active", section.dataset.workspaceSection === name));
    if (name === "trends") loadTrends();
    if (name === "reminders") loadReminders();
    if (name === "account") loadAccountSettings();
    if (name === "healthcare") { /* Keep the entered search coordinates. */ }
  }
  tabs.forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));
  document.querySelectorAll("[data-open-tab]").forEach((button) => button.addEventListener("click", () => showTab(button.dataset.openTab)));

  function renderHistory() {
    const host = byId("workspace-report-list");
    host.replaceChildren();
    if (!state.reports.length) {
      host.appendChild(el("div", "portal-empty", "No saved reports yet. Upload a report to start your history."));
      return;
    }
    state.reports.forEach((report) => {
      const button = el("button", `report-row${report.id === state.selectedReportId ? " active" : ""}`);
      button.type = "button";
      const main = el("span", "report-row-main");
      main.append(el("span", "report-row-title", report.title || report.original_filename || "Medical report"));
      main.append(el("span", "report-row-meta", `${dateLabel(report.created_at)} · ${report.report_status || "uploaded"}`));
      button.appendChild(main);
      const risk = report.insights_json?.overallRisk;
      if (risk) button.appendChild(el("span", `risk-pill risk-${String(risk).toLowerCase()}`, risk));
      button.addEventListener("click", () => selectReport(report.id));
      host.appendChild(button);
    });
  }

  function renderCompareOptions() {
    const host = byId("compare-report-options");
    host.replaceChildren();
    if (state.reports.length < 2) {
      host.appendChild(el("div", "portal-empty", "Upload two or more reports to compare results."));
    } else {
      state.reports.forEach((report) => {
        const label = el("label", "portal-check-row");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.name = "reportIds";
        input.value = report.id;
        const copy = el("span");
        copy.append(el("strong", "", report.title || report.original_filename));
        copy.append(el("small", "", dateLabel(report.created_at)));
        label.append(input, copy);
        host.appendChild(label);
      });
    }
    const select = byId("chat-report");
    const current = select.value;
    select.replaceChildren(new Option("Select a report", ""));
    state.reports.forEach((report) => select.add(new Option(`${report.title || report.original_filename} · ${dateLabel(report.created_at)}`, report.id)));
    if (state.reports.some((item) => item.id === current)) select.value = current;
    else if (state.selectedReportId) select.value = state.selectedReportId;
  }

  function updateStats() {
    byId("stat-reports").textContent = String(state.reports.length);
    const flagged = state.reports.reduce((sum, report) => sum + ((report.insights_json?.abnormalFindings || []).length), 0);
    byId("stat-findings").textContent = String(flagged);
    byId("stat-risk").textContent = state.reports[0]?.insights_json?.overallRisk || "—";
    byId("dashboard-empty-hint").hidden = state.reports.length > 0;
  }

  async function loadHistory(preferredId) {
    const payload = await api("/api/reports/history");
    state.reports = payload.reports || [];
    if (preferredId && state.reports.some((report) => report.id === preferredId)) state.selectedReportId = preferredId;
    else if (!state.reports.some((report) => report.id === state.selectedReportId)) state.selectedReportId = state.reports[0]?.id || null;
    renderHistory();
    renderCompareOptions();
    updateStats();
    if (state.selectedReportId) await selectReport(state.selectedReportId, true);
    else {
      state.selectedReport = null;
      renderReminderSuggestions();
      byId("report-details").replaceChildren(el("div", "portal-empty", "Choose a report from history to review its results."));
    }
    loadReminders().catch(() => undefined);
  }

  function addDataList(host, title, rows, fallback) {
    const section = el("section", "portal-card span-6");
    section.appendChild(el("h3", "", title));
    if (!Array.isArray(rows) || !rows.length) {
      section.appendChild(el("p", "portal-empty", fallback));
    } else {
      const list = el("ul", "portal-data-list");
      rows.slice(0, 16).forEach((row) => {
        const item = el("li", "portal-data-item");
        if (typeof row === "string") item.appendChild(el("span", "", row));
        else {
          const titleText = row.name || row.testName || row.medicineName || row.title || row.condition || "Report detail";
          item.appendChild(el("strong", "", titleText));
          const value = row.value || row.dosage || row.frequency || row.schedule || row.explanation || row.reason || row.details || row.description || row.category || row.purpose || row.timingAdvice;
          if (value) item.appendChild(el("span", "", value));
          const note = row.referenceRange || row.severity || row.status || row.priority;
          if (note) item.appendChild(el("small", "", row.referenceRange ? `Reference: ${row.referenceRange} · ${row.severity || row.status || ""}` : note));
          ["uses", "medicines", "precautions", "interactionWarnings", "sideEffects", "rationale", "preventiveSteps"].forEach((key) => {
            const details = row[key];
            if (!Array.isArray(details) || !details.length) return;
            const detail = el("small", "", `${key === "medicines" ? "Medicines" : key.replace(/([A-Z])/g, " $1")}: ${details.map((entry) => typeof entry === "string" ? entry : entry?.name || entry?.details || "").filter(Boolean).join(" · ")}`);
            item.appendChild(detail);
          });
        }
        list.appendChild(item);
      });
      section.appendChild(list);
    }
    host.appendChild(section);
  }

  function renderReport(report) {
    const host = byId("report-details");
    host.replaceChildren();
    const analysis = report.analysis_json || {};
    const insights = report.insights_json || {};
    const wrap = el("div", "portal-report-detail");
    const head = el("section", "portal-card");
    const row = el("div", "portal-card-heading-row");
    const heading = el("div");
    heading.append(el("h2", "", report.title || report.original_filename));
    heading.append(el("p", "", `${dateLabel(report.created_at)} · ${report.original_filename}`));
    row.appendChild(heading);
    const risk = String(insights.overallRisk || "unknown").toLowerCase();
    row.appendChild(el("span", `risk-pill risk-${risk}`, `Risk: ${risk}`));
    head.appendChild(row);
    head.appendChild(el("p", "", analysis.plainLanguageSummary || insights.summary || "The report is saved. Reprocess it to update extracted values."));
    const actions = el("div", "portal-actions-row");
    const ask = el("button", "portal-button small", "Ask about this report");
    ask.type = "button";
    ask.addEventListener("click", () => { byId("chat-report").value = report.id; showTab("chat"); renderChat(report.chat_messages || []); });
    actions.append(ask);
    const refresh = el("button", "portal-button secondary small", "Re-run OCR");
    refresh.type = "button";
    refresh.addEventListener("click", async () => {
      refresh.disabled = true;
      try { await api(`/api/reports/${report.id}/ocr?language=${encodeURIComponent(insights.preferredLanguage || "en")}`, { method: "POST" }); await loadHistory(report.id); } catch (error) { notify(error.message, "error"); } finally { refresh.disabled = false; }
    });
    actions.append(refresh);
    const remove = el("button", "portal-button danger small", "Delete report");
    remove.type = "button";
    remove.addEventListener("click", async () => {
      if (!window.confirm("Delete this report and its saved analysis?")) return;
      try { await api(`/api/reports/${report.id}`, { method: "DELETE" }); state.selectedReportId = null; await loadHistory(); notify("Report deleted.", "success"); } catch (error) { notify(error.message, "error"); }
    });
    actions.append(remove);
    head.appendChild(actions);
    wrap.appendChild(head);

    const scoreCard = el("section", "portal-card");
    scoreCard.append(el("h3", "", "AI confidence"));
    scoreCard.append(el("p", "", "Confidence reflects OCR and value extraction quality, not whether a medical conclusion is correct."));
    const scoreHost = el("div", "portal-confidence");
    scoreHost.id = "report-confidence";
    scoreHost.textContent = "Calculating…";
    scoreCard.appendChild(scoreHost);
    wrap.appendChild(scoreCard);

    const middle = el("div", "portal-grid");
    addDataList(middle, "Possible patterns", analysis.possibleConditions, "No condition patterns were generated.");
    addDataList(middle, "Medicines in report", analysis.medicines, "No medicine names were recognized.");
    addDataList(middle, "Medicine information", insights.medicineDetails, "No additional medicine information is available.");
    addDataList(middle, "Interaction and safety checks", insights.interactionChecks, "No interaction checks were generated.");
    addDataList(middle, "Risk signals and prevention", insights.riskPredictions, "No report-specific risk signals were generated.");
    addDataList(middle, "Precautions", analysis.precautions, "No specific precautions were generated.");
    addDataList(middle, "Questions for your clinician", analysis.followUpQuestions, "No follow-up questions were generated.");
    addDataList(middle, "Doctor recommendations", insights.doctorRecommendations, "No specialty suggestions were generated.");
    addDataList(middle, "Lifestyle follow-up", insights.lifestyleRecommendations, "No additional suggestions are available.");
    addDataList(middle, "Report alerts", insights.alerts, "No report alerts were generated.");
    if (insights.emergencyAssessment) {
      const emergency = insights.emergencyAssessment;
      const emergencyCard = el("section", "portal-card");
      emergencyCard.append(el("h3", "", emergency.headline || "Safety assessment"));
      emergencyCard.append(el("p", "", emergency.action || "Review this assessment with a qualified clinician."));
      if (emergency.criticalTests?.length) emergencyCard.append(el("small", "", `Critical values detected: ${emergency.criticalTests.join(", ")}`));
      middle.appendChild(emergencyCard);
    }
    if (insights.authenticity) {
      const proof = insights.authenticity;
      const proofCard = el("section", "portal-card");
      proofCard.append(el("h3", "", "File integrity hashes"));
      proofCard.append(el("p", "", proof.verificationMessage || "These hashes help check file integrity and do not verify medical correctness."));
      ["documentHash", "ocrHash", "analysisHash", "blockHash"].forEach((key) => {
        if (proof[key]) proofCard.append(el("small", "portal-hash", `${key}: ${proof[key]}`));
      });
      middle.appendChild(proofCard);
    }
    wrap.appendChild(middle);

    const tests = el("section", "portal-card");
    tests.appendChild(el("h3", "", "Recognized test values"));
    const values = analysis.testValues || [];
    if (!values.length) tests.appendChild(el("p", "portal-empty", "No standard numeric lab values were recognized. Check the extracted report text below."));
    else {
      const tableWrap = el("div", "portal-table-wrap");
      const table = el("table", "portal-findings");
      const headRow = document.createElement("tr");
      ["Test", "Value", "Reference range", "Status"].forEach((label) => headRow.appendChild(el("th", "", label)));
      const thead = document.createElement("thead"); thead.appendChild(headRow); table.appendChild(thead);
      const tbody = document.createElement("tbody");
      values.forEach((item) => {
        const row = document.createElement("tr");
        [item.name, item.value, item.referenceRange, item.status].forEach((value) => row.appendChild(el("td", "", value || "—")));
        tbody.appendChild(row);
      });
      table.appendChild(tbody); tableWrap.appendChild(table); tests.appendChild(tableWrap);
    }
    wrap.appendChild(tests);
    const ocr = el("section", "portal-card");
    const ocrHeading = el("div", "portal-card-heading-row");
    ocrHeading.append(el("h3", "", "Extracted text"));
    const download = el("a", "portal-button secondary small", "Open original file");
    download.href = report.file_url || `/api/reports/${encodeURIComponent(report.id)}/file`;
    download.target = "_blank"; download.rel = "noopener noreferrer";
    ocrHeading.append(download); ocr.appendChild(ocrHeading);
    ocr.appendChild(el("pre", "portal-pre", report.ocr_text || "No text was extracted."));
    wrap.appendChild(ocr);
    host.appendChild(wrap);

    api(`/api/analytics/confidence?reportId=${encodeURIComponent(report.id)}`).then((data) => {
      const target = byId("report-confidence");
      target.replaceChildren();
      ["ocr", "analysis", "overall"].forEach((key) => {
        const score = data.confidence?.[key];
        if (!score) return;
        const chip = el("span", "portal-confidence-chip", `${key}: ${score.score}% · ${score.level}`);
        target.appendChild(chip);
      });
    }).catch(() => { byId("report-confidence").textContent = "Confidence details are unavailable."; });
    api(`/api/recommendations/doctors?reportId=${encodeURIComponent(report.id)}`).then((data) => {
      const values = data.recommendations || [];
      const section = Array.from(host.querySelectorAll(".portal-card")).find((item) => item.querySelector("h3")?.textContent === "Doctor recommendations");
      if (!section || !values.length) return;
      const list = el("ul", "portal-data-list");
      values.slice(0, 5).forEach((doctor) => {
        const item = el("li", "portal-data-item");
        item.append(el("strong", "", `${doctor.name || "Doctor"} · ${doctor.specialty || "Specialist"}`));
        item.append(el("small", "", `${doctor.experience_years || 0} years · ${doctor.rating || "—"}★ · ${doctor.hospital?.name || "Nearby"}`));
        if (doctor.doctor_id) {
          const link = el("a", "portal-inline-link", "View profile");
          link.href = `/doctors/${encodeURIComponent(doctor.doctor_id)}/`;
          item.appendChild(link);
        }
        list.appendChild(item);
      });
      section.querySelector("ul")?.remove();
      section.querySelector("p")?.remove();
      section.appendChild(list);
    }).catch(() => undefined);
  }

  async function selectReport(reportId, quiet) {
    state.selectedReportId = reportId;
    renderHistory();
    try {
      const data = await api(`/api/reports/${encodeURIComponent(reportId)}`);
      if (state.selectedReportId !== reportId) return;
      state.selectedReport = data.report;
      renderReport(data.report);
      renderReminderSuggestions();
      renderChat(data.report.chat_messages || []);
      renderCompareOptions();
    } catch (error) {
      if (!quiet) notify(error.message, "error");
    }
  }

  function notify(message, type) {
    const box = byId("workspace-notice");
    showStatus(box, message, type);
    box.dataset.message = message;
    if (state.alarmAudio) {
      const stop = el("button", "portal-button secondary small", "Stop alarm");
      stop.type = "button";
      stop.addEventListener("click", stopAlarm);
      box.appendChild(stop);
    }
    if (type === "success") window.setTimeout(() => { if (box.dataset.message === message && !state.alarmAudio) box.hidden = true; }, 4500);
  }
  function stopAlarm() {
    if (!state.alarmAudio) return;
    state.alarmAudio.pause();
    state.alarmAudio.currentTime = 0;
    state.alarmAudio = null;
    byId("workspace-notice").querySelector("button")?.remove();
  }

  byId("workspace-upload-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    const file = byId("workspace-file").files[0];
    if (!file) return showStatus(byId("upload-status"), "Choose a PDF, PNG, or JPG report first.", "error");
    if (file.size > 20 * 1024 * 1024) return showStatus(byId("upload-status"), "The report is larger than 20 MB.", "error");
    const form = new FormData();
    form.append("file", file);
    form.append("language", byId("report-language").value);
    const button = byId("upload-submit"); button.disabled = true; button.textContent = "Extracting and analyzing…";
    showStatus(byId("upload-status"), "Your report is being processed. This can take a short while.");
    try {
      const data = await api("/api/reports/upload", { method: "POST", body: form });
      showStatus(byId("upload-status"), "Report saved to your workspace.", "success");
      byId("workspace-file").value = "";
      await loadHistory(data.reportId);
      notify("Report processed and saved.", "success");
    } catch (error) { showStatus(byId("upload-status"), error.message, "error"); }
    finally { button.disabled = false; button.textContent = "Analyze and save report"; }
  });

  const uploadZone = byId("upload-drop-zone");
  ["dragenter", "dragover"].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => { event.preventDefault(); uploadZone.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => { event.preventDefault(); uploadZone.classList.remove("dragging"); }));
  uploadZone.addEventListener("drop", (event) => { const file = event.dataTransfer?.files?.[0]; if (file) { const transfer = new DataTransfer(); transfer.items.add(file); byId("workspace-file").files = transfer.files; } });

  async function loadTrends() {
    byId("trend-count").textContent = "Loading report measurements…";
    try {
      const data = await api("/api/analytics/trends");
      byId("trend-count").textContent = `${data.reportsCount || 0} reports · ${data.storedMetricsCount || 0} measurements`;
      renderTrendChart(data.metricSeries || []);
      const host = byId("trend-list"); host.replaceChildren();
      (data.trendInsights || []).forEach((item) => {
        const card = el("section", "portal-card span-6");
        card.append(el("h3", "", item.testName));
        card.append(el("p", "", `${item.latestValue} ${item.unit} · ${item.status}`));
        card.append(el("small", "", item.summary));
        host.appendChild(card);
      });
      if (!data.metricSeries?.length) byId("trend-chart-empty").hidden = false;
    } catch (error) { byId("trend-count").textContent = error.message; }
  }
  function renderTrendChart(seriesList) {
    state.chart = seriesList;
    const canvas = byId("trend-chart");
    const empty = byId("trend-chart-empty");
    const select = byId("trend-metric");
    const usable = seriesList.filter((series) => series.points?.length);
    const selectedKey = select.value;
    select.replaceChildren();
    usable.forEach((series) => select.add(new Option(`${series.testName}${series.unit ? ` (${series.unit})` : ""}`, series.metricKey)));
    if (usable.some((series) => series.metricKey === selectedKey)) select.value = selectedKey;
    else if (usable.length) select.value = usable[0].metricKey;
    const series = usable.find((item) => item.metricKey === select.value);
    if (!series?.points?.length) { canvas.hidden = true; empty.hidden = false; return; }
    canvas.hidden = false; empty.hidden = true;
    const rect = canvas.getBoundingClientRect(); const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(300, rect.width * ratio); canvas.height = 220 * ratio;
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio);
    const width = canvas.width / ratio; const height = 220; const pad = { left: 54, right: 18, top: 18, bottom: 35 };
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue("--border-med").trim() || "#c8dbd2";
    ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim() || "#6d8478";
    ctx.font = "10px sans-serif";
    for (let i = 0; i < 4; i += 1) {
      const y = pad.top + (height - pad.top - pad.bottom) * i / 3;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
    }
    const points = series.points.map((item) => ({ ...item, numericValue: Number(item.value) })).filter((item) => Number.isFinite(item.numericValue));
    if (!points.length) { canvas.hidden = true; empty.hidden = false; return; }
    const min = Math.min(...points.map((item) => item.numericValue));
    const max = Math.max(...points.map((item) => item.numericValue));
    const span = max === min ? Math.max(1, Math.abs(max) * .1) : max - min;
    const low = min === max ? min - span / 2 : min;
    const high = min === max ? max + span / 2 : max;
    ctx.strokeStyle = "#2a7a5c"; ctx.fillStyle = "#2a7a5c"; ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach((item, pointIndex) => {
      const x = pad.left + (width - pad.left - pad.right) * (points.length < 2 ? .5 : pointIndex / (points.length - 1));
      const y = height - pad.bottom - (item.numericValue - low) / (high - low) * (height - pad.top - pad.bottom);
      if (pointIndex === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      ctx.fillRect(x - 2.5, y - 2.5, 5, 5);
    });
    ctx.stroke();
    ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim() || "#6d8478";
    ctx.textAlign = "right"; ctx.fillText(`${high.toPrecision(4)} ${series.unit || ""}`, pad.left - 5, pad.top + 4);
    ctx.fillText(`${low.toPrecision(4)} ${series.unit || ""}`, pad.left - 5, height - pad.bottom + 4);
    const firstDate = dateLabel(points[0].createdAt).split(",")[0];
    const lastDate = dateLabel(points[points.length - 1].createdAt).split(",")[0];
    ctx.textAlign = "left"; ctx.fillText(firstDate, pad.left, height - 8);
    ctx.textAlign = "right"; ctx.fillText(lastDate, width - pad.right, height - 8);
  }
  byId("refresh-trends").addEventListener("click", loadTrends);
  byId("trend-metric").addEventListener("change", () => renderTrendChart(state.chart || []));
  window.addEventListener("resize", () => { if (state.chart) renderTrendChart(state.chart); });

  byId("compare-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    const ids = Array.from(this.querySelectorAll("input[name=reportIds]:checked")).map((item) => item.value);
    const host = byId("compare-result"); host.replaceChildren(); host.classList.remove("portal-comparison-result"); host.classList.add("portal-empty");
    if (ids.length < 2) { host.appendChild(el("div", "portal-empty", "Select at least two reports.")); return; }
    if (ids.length > 6) { host.appendChild(el("div", "portal-empty", "Choose no more than six reports.")); return; }
    host.appendChild(el("div", "portal-empty", "Comparing selected reports…"));
    try {
      const data = await api("/api/reports/compare", { method: "POST", body: JSON.stringify({ reportIds: ids, language: "en" }) });
      host.replaceChildren();
      host.classList.remove("portal-empty");
      host.classList.add("portal-comparison-result");
      const exportLink = el("a", "portal-button secondary small", "Download comparison CSV");
      exportLink.href = `/api/reports/compare/export?reportIds=${encodeURIComponent(ids.join(","))}`;
      exportLink.style.marginBottom = "1rem";
      host.appendChild(exportLink);
      const reportCards = el("div", "portal-comparison-reports");
      (data.comparison?.reports || []).forEach((report) => {
        const card = el("article", "portal-data-item");
        card.append(el("strong", "", report.title));
        card.append(el("small", "", `${dateLabel(report.createdAt)} · ${report.overallRisk || "risk unavailable"}`));
        reportCards.appendChild(card);
      });
      host.appendChild(reportCards);
      host.appendChild(el("h3", "", "AI overview"));
      host.appendChild(el("p", "", data.aiComparison?.summary || "Numeric values from the selected reports are compared below."));
      if (data.aiComparison?.healthImpact) host.appendChild(el("p", "", data.aiComparison.healthImpact));
      (data.aiComparison?.keyDifferences || []).forEach((difference) => {
        const card = el("section", "portal-card span-6");
        card.append(el("h3", "", difference.label || difference.id || "Reported change"));
        if (difference.direction) card.append(el("small", "", `Direction: ${difference.direction}${difference.confidence ? ` · confidence ${difference.confidence}` : ""}`));
        if (difference.summary) card.append(el("p", "", difference.summary));
        if (difference.healthImpact) card.append(el("p", "", difference.healthImpact));
        host.appendChild(card);
      });
      host.appendChild(el("h3", "", "Numeric values"));
      (data.comparison?.metrics || []).forEach((metric) => {
        const card = el("section", "portal-card span-6");
        card.append(el("h3", "", metric.testName));
        card.append(el("p", "", metric.summary));
        if (metric.hasUnitMismatch) card.append(el("small", "", `Units differ across reports (${metric.units.join(", ")}); values are listed without calculating a net change.`));
        const list = el("ul", "portal-data-list");
        (metric.values || []).forEach((item) => list.appendChild(el("li", "portal-data-item", `${item.reportLabel}: ${item.value} ${item.unit} · ${item.status}`)));
        card.appendChild(list); host.appendChild(card);
      });
      if (!data.comparison?.metrics?.length) host.appendChild(el("div", "portal-empty", "No comparable numeric values were found in those reports."));
      (data.aiComparison?.notes || []).forEach((note) => host.appendChild(el("p", "", note)));
      if (data.aiComparison?.followUpQuestions?.length) addDataList(host, "Questions for your clinician", data.aiComparison.followUpQuestions, "");
    } catch (error) { host.classList.remove("portal-empty"); host.replaceChildren(el("div", "portal-status error", error.message)); }
  });

  async function loadReminders() {
    try {
      const data = await api("/api/reminders");
      state.reminders = data.reminders || [];
      byId("stat-reminders").textContent = String(state.reminders.filter((item) => item.active).length);
      renderReminders();
    } catch (error) { byId("reminder-list").replaceChildren(el("div", "portal-empty", error.message)); }
  }
  function renderReminders() {
    const host = byId("reminder-list"); host.replaceChildren();
    if (!state.reminders.length) { host.appendChild(el("div", "portal-empty", "No medicine reminders yet.")); return; }
    state.reminders.forEach((reminder) => {
      const row = el("div", "portal-reminder");
      const copy = el("div", "portal-reminder-copy");
      const reminderType = { medicine: "Medicine", appointment: "Appointment", test: "Medical test", follow_up: "Follow-up" }[reminder.reminderType] || "Reminder";
      copy.append(el("strong", "", `${reminderType}: ${reminder.medicine_name}${reminder.dosage ? ` · ${reminder.dosage}` : ""}`));
      const times = (reminder.reminder_times || []).map((slot) => typeof slot === "string" ? slot : slot.time).join(", ");
      copy.append(el("span", "", `${reminder.schedule} · ${times || "No time set"}${reminder.instructions ? ` · ${reminder.instructions}` : ""}`));
      const actions = el("div", "portal-reminder-actions");
      const edit = el("button", "portal-button secondary small", "Edit"); edit.type = "button";
      edit.addEventListener("click", () => {
        byId("reminder-edit-id").value = reminder.id;
        byId("reminder-type").value = reminder.reminderType || "medicine";
        byId("reminder-name").value = reminder.medicine_name || "";
        byId("reminder-dosage").value = reminder.dosage || "";
        byId("reminder-schedule").value = reminder.schedule || "";
        byId("reminder-times").value = (reminder.reminder_times || []).map((slot) => typeof slot === "string" ? slot : slot.time).filter(Boolean).join(", ");
        byId("reminder-instructions").value = reminder.instructions || "";
        byId("reminder-tone").value = reminder.alarm_tone || "default";
        byId("reminder-email").checked = Boolean(reminder.emailNotification);
        byId("reminder-submit").textContent = "Update reminder";
        byId("cancel-reminder-edit").hidden = false;
        showTab("reminders");
        byId("reminder-name").focus();
      });
      const toggle = el("button", "portal-button secondary small", reminder.active ? "Pause" : "Resume"); toggle.type = "button";
      toggle.addEventListener("click", async () => { try { await api(`/api/reminders/${reminder.id}`, { method: "PATCH", body: JSON.stringify({ active: !reminder.active }) }); await loadReminders(); } catch (error) { notify(error.message, "error"); } });
      const remove = el("button", "portal-button danger small", "Delete"); remove.type = "button";
      remove.addEventListener("click", async () => { try { await api(`/api/reminders/${reminder.id}`, { method: "DELETE" }); await loadReminders(); } catch (error) { notify(error.message, "error"); } });
      actions.append(edit, toggle, remove); row.append(copy, actions); host.appendChild(row);
    });
  }
  function renderReminderSuggestions() {
    const host = byId("reminder-suggestions");
    host.replaceChildren();
    const medicines = state.selectedReport?.analysis_json?.medicines || [];
    const suggestions = medicines.filter((item) => item && item.name).slice(0, 8);
    if (!suggestions.length) return;
    host.appendChild(el("p", "portal-suggestion-label", "Suggestions from the selected report · check each detail against the prescription."));
    suggestions.forEach((medicine) => {
      const row = el("div", "portal-reminder-suggestion");
      const copy = el("div");
      copy.append(el("strong", "", medicine.name));
      copy.append(el("small", "", [medicine.dosage, medicine.frequency].filter(Boolean).join(" · ") || "Schedule not extracted"));
      const use = el("button", "portal-button secondary small", "Use"); use.type = "button";
      use.addEventListener("click", () => {
        byId("reminder-edit-id").value = "";
        byId("reminder-name").value = medicine.name || "";
        byId("reminder-dosage").value = medicine.dosage || "";
        byId("reminder-schedule").value = medicine.frequency || "";
        byId("reminder-instructions").value = medicine.notes || medicine.purpose || "Use exactly as written in the prescription.";
        byId("reminder-times").focus();
        byId("reminder-submit").textContent = "Save reminder";
        byId("cancel-reminder-edit").hidden = true;
      });
      row.append(copy, use); host.appendChild(row);
    });
  }
  function cancelReminderEdit() {
    byId("reminder-form").reset();
    byId("reminder-edit-id").value = "";
    byId("reminder-submit").textContent = "Save reminder";
    byId("cancel-reminder-edit").hidden = true;
    showStatus(byId("reminder-status"), "");
  }
  byId("cancel-reminder-edit").addEventListener("click", cancelReminderEdit);
  byId("reminder-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    const name = byId("reminder-name").value.trim(); const schedule = byId("reminder-schedule").value.trim();
    const reminderTimes = byId("reminder-times").value.split(",").map((value) => value.trim()).filter(Boolean).map((time) => ({ time }));
    if (!name || !schedule || !reminderTimes.length) return showStatus(byId("reminder-status"), "Enter a medicine, schedule, and at least one time.", "error");
    const editId = byId("reminder-edit-id").value;
    try {
      const body = JSON.stringify({ reminderType: byId("reminder-type").value, medicineName: name, dosage: byId("reminder-dosage").value.trim(), schedule, instructions: byId("reminder-instructions").value.trim(), reminderTimes, alarmTone: byId("reminder-tone").value, emailNotification: byId("reminder-email").checked, reportId: state.selectedReportId });
      await api(editId ? `/api/reminders/${encodeURIComponent(editId)}` : "/api/reminders", { method: editId ? "PATCH" : "POST", body });
      cancelReminderEdit(); showStatus(byId("reminder-status"), editId ? "Reminder updated." : "Reminder saved.", "success"); await loadReminders();
    } catch (error) { showStatus(byId("reminder-status"), error.message, "error"); }
  });
  byId("enable-notifications").addEventListener("click", async function () {
    if (!("Notification" in window)) return showStatus(byId("workspace-notice"), "Browser notifications are not supported here.", "error");
    const permission = await Notification.requestPermission();
    state.notificationReady = permission === "granted";
    this.textContent = state.notificationReady ? "Alerts enabled" : "Enable notifications";
    showStatus(byId("workspace-notice"), state.notificationReady ? "Browser reminders are enabled while this workspace is open." : "Allow notifications in your browser settings to receive reminders.", state.notificationReady ? "success" : "error");
  });
  function checkReminderTimes() {
    const now = new Date(); const hhmm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    state.reminders.filter((item) => item.active).forEach((reminder) => {
      (reminder.reminder_times || []).forEach((slot) => {
        const time = typeof slot === "string" ? slot : slot.time;
        const key = `${reminder.id}:${now.toDateString()}:${time}`;
        if (time !== hhmm || state.alerted.has(key)) return;
        state.alerted.add(key);
        const typeLabel = { medicine: "Medicine", appointment: "Appointment", test: "Medical test", follow_up: "Follow-up" }[reminder.reminderType] || "Reminder";
        const message = `${typeLabel}: ${reminder.medicine_name}${reminder.dosage ? ` · ${reminder.dosage}` : ""}`;
        const tone = ["default", "soft", "beep", "alert"].includes(reminder.alarm_tone) ? reminder.alarm_tone : "default";
        const sound = new Audio(`/static/audio/${tone}.mp3`);
        state.alarmAudio = sound;
        sound.addEventListener("ended", () => { if (state.alarmAudio === sound) { state.alarmAudio = null; byId("workspace-notice").querySelector("button")?.remove(); } }, { once: true });
        sound.play().catch(() => { if (state.alarmAudio === sound) { state.alarmAudio = null; byId("workspace-notice").querySelector("button")?.remove(); } });
        if (state.notificationReady && Notification.permission === "granted") new Notification("MediScan AI reminder", { body: message });
        notify(message, "success");
      });
    });
  }
  window.setInterval(checkReminderTimes, 15000);

  function renderChat(messages) {
    const log = byId("chat-log"); log.replaceChildren();
    if (!messages?.length) { log.appendChild(el("div", "portal-chat-empty", "Ask a question about this report's wording or values.")); return; }
    messages.forEach((message) => {
      const bubble = el("article", `portal-chat-message ${message.role === "user" ? "user" : "assistant"}`);
      bubble.appendChild(el("div", "", message.message));
      if (message.role === "assistant") {
        const actions = el("div", "portal-chat-tools");
        const humanize = el("button", "portal-button secondary small", "Simplify"); humanize.type = "button";
        humanize.addEventListener("click", async () => { try { const data = await api("/api/chat/humanize", { method: "POST", body: JSON.stringify({ reportId: state.selectedReportId, message: message.message }) }); bubble.querySelector("div").textContent = data.reply || message.message; } catch (error) { notify(error.message, "error"); } });
        const speak = el("button", "portal-button secondary small", "Read aloud"); speak.type = "button";
        speak.addEventListener("click", () => { if (!("speechSynthesis" in window)) return notify("Speech playback is not available in this browser.", "error"); window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(message.message); utterance.lang = state.selectedReport?.insights_json?.preferredLanguage === "hi" ? "hi-IN" : "en-IN"; window.speechSynthesis.speak(utterance); });
        actions.append(humanize, speak); bubble.appendChild(actions);
      }
      log.appendChild(bubble);
    });
    log.scrollTop = log.scrollHeight;
  }
  byId("chat-report").addEventListener("change", async function () {
    if (!this.value) return renderChat([]);
    await selectReport(this.value, true);
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => { byId("chat-input").value = button.dataset.prompt; byId("chat-input").focus(); }));
  byId("chat-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    const reportId = byId("chat-report").value; const message = byId("chat-input").value.trim();
    if (!reportId) return showStatus(byId("chat-status"), "Select a report first.", "error");
    if (!message) return;
    const button = this.querySelector("button[type=submit]"); button.disabled = true;
    const before = state.selectedReport?.chat_messages || [];
    renderChat([...before, { role: "user", message }]);
    try {
      const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ reportId, message }) });
      byId("chat-input").value = "";
      renderChat(data.messages || [...before, { role: "user", message }, { role: "assistant", message: data.reply }]);
      if (state.selectedReport) state.selectedReport.chat_messages = data.messages || [];
    } catch (error) { showStatus(byId("chat-status"), error.message, "error"); renderChat(before); }
    finally { button.disabled = false; }
  });
  byId("voice-input").addEventListener("click", function () {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) return showStatus(byId("chat-status"), "Voice input is not available in this browser.", "error");
    const recognition = new Recognition(); recognition.lang = state.selectedReport?.insights_json?.preferredLanguage === "hi" ? "hi-IN" : "en-IN"; recognition.interimResults = false;
    recognition.onresult = (event) => { byId("chat-input").value = event.results[0][0].transcript; };
    recognition.onerror = () => showStatus(byId("chat-status"), "Voice input could not be captured. Check microphone permissions.", "error");
    recognition.start();
  });

  function renderPlaces(kind, values) {
    const host = byId(kind === "hospitals" ? "places-hospitals" : "places-doctors"); host.replaceChildren();
    if (!values?.length) { host.appendChild(el("div", "portal-empty", `No ${kind} found nearby.`)); return; }
    values.forEach((value) => {
      const item = el("li", "portal-data-item");
      const title = value.name || "Care provider";
      const verifiedDoctor = kind === "doctors" && value.source === "verified_directory";
      item.append(el("strong", "", verifiedDoctor && !title.startsWith("Dr.") ? `Dr. ${title}` : title));
      const specialty = value.specialty || value.hospital_type || "Healthcare provider";
      const distance = value.distance_km != null ? ` · ${Number(value.distance_km).toFixed(1)} km` : "";
      item.append(el("small", "", `${specialty}${distance}${value.rating ? ` · ${value.rating}★` : ""}`));
      const sourceLabel = value.source === "verified_directory"
        ? "MediScanAI verified directory"
        : value.source === "google_places"
          ? "Google Places listing (not independently verified)"
          : value.source === "live_osm"
            ? "OpenStreetMap listing (not independently verified)"
            : "";
      if (sourceLabel) item.append(el("small", "", sourceLabel));
      if (value.address || value.hospital?.address) item.append(el("small", "", value.address || value.hospital.address));
      const actions = el("div", "portal-hospital-actions");
      const latitude = value.latitude ?? value.hospital?.latitude; const longitude = value.longitude ?? value.hospital?.longitude;
      if (latitude != null && longitude != null) {
        const route = el("a", "portal-button secondary small", "Directions"); route.href = `/navigation/?destination_lat=${encodeURIComponent(latitude)}&destination_lng=${encodeURIComponent(longitude)}`; actions.appendChild(route);
      }
      const favoriteId = kind === "hospitals" ? value.id : value.doctor_id;
      if (favoriteId != null && Number.isInteger(Number(favoriteId))) {
        const savedIds = kind === "hospitals" ? state.savedHospitalIds : state.savedDoctorIds;
        const saved = savedIds.has(String(favoriteId));
        const favorite = el("button", "portal-button secondary small", saved ? "Saved" : "Save");
        favorite.type = "button";
        favorite.disabled = saved;
        favorite.addEventListener("click", () => saveFavorite(kind, favoriteId, favorite));
        actions.appendChild(favorite);
      }
      if (kind === "doctors" && value.doctor_id) { const profile = el("a", "portal-button secondary small", "Profile"); profile.href = `/doctors/${encodeURIComponent(value.doctor_id)}/`; actions.appendChild(profile); }
      if (kind === "doctors") { const browse = el("a", "portal-button small", "Appointments"); browse.href = "/doctors/"; actions.appendChild(browse); }
      if (actions.childElementCount) item.appendChild(actions);
      host.appendChild(item);
    });
  }
  byId("places-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    const params = new URLSearchParams({ lat: byId("places-lat").value, lng: byId("places-lng").value, radius: byId("places-radius").value, specialty: byId("places-specialty").value });
    showStatus(byId("places-status"), "Searching nearby…");
    try {
      const [hospitals, doctors] = await Promise.all([api(`/api/places/hospitals?${params.toString()}`), api(`/api/places/doctors?${params.toString()}`)]);
      renderPlaces("hospitals", hospitals.hospitals || []); renderPlaces("doctors", doctors.doctors || []);
      showStatus(byId("places-status"), `Found ${hospitals.total_found || 0} hospitals and ${doctors.total_found || 0} doctors.`, "success");
    } catch (error) { showStatus(byId("places-status"), error.message, "error"); }
  });
  byId("use-location").addEventListener("click", function () {
    if (!navigator.geolocation) return showStatus(byId("places-status"), "Location is not available in this browser.", "error");
    showStatus(byId("places-status"), "Requesting your location…");
    navigator.geolocation.getCurrentPosition(async (position) => {
      const lat = position.coords.latitude; const lng = position.coords.longitude;
      byId("places-lat").value = lat.toFixed(6); byId("places-lng").value = lng.toFixed(6);
      try { await api("/api/location/update/", { method: "POST", body: JSON.stringify({ latitude: lat, longitude: lng, is_manual: false }) }); } catch (_) { /* Search still works for this visit. */ }
      showStatus(byId("places-status"), "Location set. Search to see nearby care options.", "success");
    }, () => showStatus(byId("places-status"), "Location permission was not granted. Enter coordinates instead.", "error"), { enableHighAccuracy: true, timeout: 10000 });
  });

  function renderSavedItems(hostId, items, kind) {
    const host = byId(hostId);
    host.replaceChildren();
    if (!items.length) {
      host.appendChild(el("div", "portal-empty", `No saved ${kind} yet.`));
      return;
    }
    items.forEach((item) => {
      const row = el("div", "portal-data-item");
      row.appendChild(el("strong", "", item.name));
      row.appendChild(el("small", "", item.address || item.specialty || ""));
      const remove = el("button", "portal-button secondary small", "Remove");
      remove.type = "button";
      remove.addEventListener("click", async () => {
        const path = kind === "hospitals" ? "/api/favorites/hospitals" : "/api/favorites/doctors";
        const key = kind === "hospitals" ? "hospitalId" : "doctorId";
        try {
          await api(path, { method: "DELETE", body: JSON.stringify({ [key]: item.id }) });
          await loadAccountSettings();
        } catch (error) {
          notify(error.message, "error");
        }
      });
      row.appendChild(remove);
      host.appendChild(row);
    });
  }

  async function loadAccountSettings() {
    try {
      const [profileData, preferenceData, hospitalData, doctorData] = await Promise.all([
        api("/api/auth/profile"),
        api("/api/notifications/preferences"),
        api("/api/favorites/hospitals"),
        api("/api/favorites/doctors"),
      ]);
      const profile = profileData.profile || {};
      byId("profile-name").value = profile.fullName || "";
      byId("profile-blood").value = profile.bloodGroup || "unknown";
      byId("profile-gender").value = profile.gender || "prefer_not_to_say";
      byId("profile-emergency-name").value = profile.emergencyContactName || "";
      byId("profile-emergency-phone").value = profile.emergencyContactPhone || "";
      byId("profile-location").value = profile.locationAddress || "";

      const preferences = preferenceData.preferences || {};
      const preferenceForm = byId("notification-preferences-form");
      Object.keys(preferences).forEach((key) => {
        const input = preferenceForm.elements.namedItem(key);
        if (input) input.checked = Boolean(preferences[key]);
      });

      state.savedHospitalIds = new Set((hospitalData.hospitals || []).map((item) => String(item.id)));
      state.savedDoctorIds = new Set((doctorData.doctors || []).map((item) => String(item.id)));
      renderSavedItems("saved-hospitals", hospitalData.hospitals || [], "hospitals");
      renderSavedItems("saved-doctors", doctorData.doctors || [], "doctors");
    } catch (error) {
      showStatus(byId("profile-status"), error.message, "error");
    }
  }

  byId("account-profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      fullName: byId("profile-name").value.trim(),
      bloodGroup: byId("profile-blood").value,
      gender: byId("profile-gender").value,
      emergencyContactName: byId("profile-emergency-name").value.trim(),
      emergencyContactPhone: byId("profile-emergency-phone").value.trim(),
      locationAddress: byId("profile-location").value.trim(),
    };
    try {
      await api("/api/auth/profile", { method: "PATCH", body: JSON.stringify(payload) });
      showStatus(byId("profile-status"), "Profile saved.", "success");
      document.querySelector(".portal-user").textContent = payload.fullName || document.querySelector(".portal-user").textContent;
    } catch (error) {
      showStatus(byId("profile-status"), error.message, "error");
    }
  });

  byId("notification-preferences-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {};
    form.querySelectorAll("input[type=checkbox]").forEach((input) => { payload[input.name] = input.checked; });
    try {
      await api("/api/notifications/preferences", { method: "PATCH", body: JSON.stringify(payload) });
      showStatus(byId("notification-status"), "Notification choices saved.", "success");
    } catch (error) {
      showStatus(byId("notification-status"), error.message, "error");
    }
  });

  async function saveFavorite(kind, id, button) {
    const hospital = kind === "hospitals";
    const endpoint = hospital ? "/api/favorites/hospitals" : "/api/favorites/doctors";
    const payload = hospital ? { hospitalId: id } : { doctorId: id };
    try {
      await api(endpoint, { method: "POST", body: JSON.stringify(payload) });
      button.textContent = "Saved";
      button.disabled = true;
      if (hospital) state.savedHospitalIds.add(String(id));
      else state.savedDoctorIds.add(String(id));
    } catch (error) {
      notify(error.message, "error");
    }
  }

  byId("sign-out").addEventListener("click", async function () {
    try { await api("/api/auth/logout", { method: "POST", body: "{}" }); } catch (_) { /* Always return to the public page. */ }
    window.location.assign("/");
  });
  const themeButton = document.querySelector("[data-theme-toggle]");
  function setTheme(theme) { document.body.classList.remove("dark", "light"); document.body.classList.add(theme); document.documentElement.style.colorScheme = theme; try { localStorage.setItem("ms-theme", theme); } catch (_) { /* optional */ } }
  themeButton?.addEventListener("click", () => setTheme(document.body.classList.contains("dark") ? "light" : "dark"));
  try { const theme = localStorage.getItem("ms-theme"); if (theme === "dark" || theme === "light") setTheme(theme); } catch (_) { /* light default */ }
  if ("Notification" in window && Notification.permission === "granted") {
    state.notificationReady = true;
    byId("enable-notifications").textContent = "Alerts enabled";
  }

  function applyNoticeQuery() {
    const query = new URLSearchParams(window.location.search);
    if (query.get("welcome") === "1") notify("Your workspace is ready.", "success");
    const requestedTab = query.get("tab");
    if (["dashboard", "upload", "trends", "compare", "reminders", "chat", "healthcare", "account"].includes(requestedTab)) showTab(requestedTab);
  }
  loadHistory().catch((error) => notify(error.message, "error"));
  loadAccountSettings();
  applyNoticeQuery();
}());
