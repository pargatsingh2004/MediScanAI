/**
 * Medical Report Upload & AI Processing Workbench
 */

const ReportUploadManager = {
  selectedFile: null,

  init() {
    this.bindDropZone();
  },

  bindDropZone() {
    const dropZone = document.getElementById("report-drop-zone");
    const fileInput = document.getElementById("report-file-input");
    const uploadForm = document.getElementById("report-upload-form");

    if (!dropZone || !fileInput) return;

    // Click to select
    dropZone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        this.handleFileSelected(e.target.files[0]);
      }
    });

    // Drag-and-drop
    ["dragenter", "dragover"].forEach((event) => {
      dropZone.addEventListener(event, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.style.borderColor = "var(--accent-teal)";
        dropZone.style.background = "rgba(13, 148, 136, 0.08)";
      });
    });

    ["dragleave", "drop"].forEach((event) => {
      dropZone.addEventListener(event, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.style.borderColor = "var(--border-card)";
        dropZone.style.background = "var(--bg-secondary)";
      });
    });

    dropZone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        this.handleFileSelected(e.dataTransfer.files[0]);
      }
    });

    if (uploadForm) {
      uploadForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.uploadAndAnalyze();
      });
    }
  },

  handleFileSelected(file) {
    const validExts = [".pdf", ".jpg", ".jpeg", ".png"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();

    if (!validExts.includes(ext)) {
      HealthcareApp.showToast("Unsupported format. Please upload a PDF, JPG, JPEG, or PNG document.", "error");
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      HealthcareApp.showToast("File size exceeds 20MB limit.", "error");
      return;
    }

    this.selectedFile = file;
    const infoEl = document.getElementById("selected-file-info");
    const nameEl = document.getElementById("selected-file-name");
    const sizeEl = document.getElementById("selected-file-size");
    const analyzeBtn = document.getElementById("analyze-btn");

    if (nameEl) nameEl.textContent = file.name;
    if (sizeEl) sizeEl.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
    if (infoEl) infoEl.style.display = "flex";
    if (analyzeBtn) analyzeBtn.disabled = false;

    HealthcareApp.showToast(`Selected: ${file.name}`, "info");
  },

  async uploadAndAnalyze() {
    if (!this.selectedFile) {
      HealthcareApp.showToast("Please choose a medical report first.", "error");
      return;
    }

    const analyzeBtn = document.getElementById("analyze-btn");
    const spinner = document.getElementById("analysis-spinner");
    const resultsContainer = document.getElementById("analysis-results-wrap");

    if (analyzeBtn) analyzeBtn.disabled = true;
    if (spinner) spinner.style.display = "flex";
    if (resultsContainer) resultsContainer.style.display = "none";

    HealthcareApp.showToast("Uploading document and running AI extraction pipeline...", "info");

    const formData = new FormData();
    formData.append("file", this.selectedFile);

    try {
      const data = await HealthcareApp.fetchJson("/api/reports/upload/", {
        method: "POST",
        body: formData,
      });

      HealthcareApp.showToast("Analysis complete!", "success");
      this.renderAnalysisResults(data);
    } catch (err) {
      console.error(err);
      HealthcareApp.showToast(err.message || "Failed to process report.", "error");
    } finally {
      if (spinner) spinner.style.display = "none";
      if (analyzeBtn) analyzeBtn.disabled = false;
    }
  },

  renderAnalysisResults(data) {
    const wrap = document.getElementById("analysis-results-wrap");
    if (!wrap) return;

    wrap.style.display = "block";
    wrap.scrollIntoView({ behavior: "smooth" });

    // Summary
    const summaryEl = document.getElementById("analysis-summary-text");
    if (summaryEl) summaryEl.textContent = data.summary;

    // Overall Risk Badge
    const riskBadge = document.getElementById("overall-risk-badge");
    if (riskBadge) {
      riskBadge.className = `badge badge-${data.overall_risk}`;
      riskBadge.textContent = `${data.overall_risk.toUpperCase()} RISK`;
    }

    // Urgent Care Alert
    const urgentBox = document.getElementById("urgent-care-box");
    if (urgentBox) {
      if (data.requires_urgent_care) {
        urgentBox.style.display = "block";
        document.getElementById("urgent-care-reason").textContent = data.urgency_reason;
      } else {
        urgentBox.style.display = "none";
      }
    }

    // Detected Conditions Tags
    const condList = document.getElementById("detected-conditions-list");
    if (condList) {
      if (data.detected_conditions && data.detected_conditions.length > 0) {
        condList.innerHTML = data.detected_conditions
          .map((c) => `<span class="badge badge-high" style="font-size:0.85rem;padding:0.4rem 0.8rem;">⚠️ ${c}</span>`)
          .join(" ");
      } else {
        condList.innerHTML = '<span style="color:var(--text-muted);font-size:0.88rem;">No pathological conditions detected.</span>';
      }
    }

    // Recommended Specialties
    const specList = document.getElementById("recommended-specialties-list");
    if (specList && data.specialties) {
      specList.innerHTML = data.specialties
        .map(
          (s) => `
          <div style="background:var(--bg-secondary);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);padding:0.85rem;display:flex;justify-content:space-between;align-items:center;">
            <div>
              <strong style="color:#fff;">${s.name}</strong>
              <p style="font-size:0.8rem;color:var(--text-muted);margin-top:0.2rem;">${s.description}</p>
            </div>
            <span class="badge badge-verified" style="font-size:0.85rem;">${s.relevance_percent}% Match</span>
          </div>
        `
        )
        .join("");
    }

    // Findings Table
    const tbody = document.getElementById("findings-table-body");
    if (tbody && data.findings) {
      if (data.findings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:1.5rem;color:var(--text-muted);">No standard numerical biomarkers identified.</td></tr>';
      } else {
        tbody.innerHTML = data.findings
          .map((f) => {
            const badgeClass = f.status === "normal" ? "badge-normal" : f.severity === "critical" ? "badge-critical" : "badge-high";
            return `
              <tr>
                <td><strong>${f.test_name}</strong></td>
                <td><span style="font-weight:700;color:#fff;">${f.measured_value}</span> ${f.unit}</td>
                <td style="color:var(--text-muted);">${f.reference_range}</td>
                <td><span class="badge ${badgeClass}">${f.status}</span></td>
                <td style="font-size:0.82rem;color:var(--text-secondary);">${f.clinical_significance}</td>
              </tr>
            `;
          })
          .join("");
      }
    }

    // Precautions
    const precList = document.getElementById("precautions-list");
    if (precList && data.precautions) {
      precList.innerHTML = data.precautions.map((p) => `<li>${p}</li>`).join("");
    }

    // Questions to Ask Doctor
    const qList = document.getElementById("suggested-questions-list");
    if (qList && data.suggested_questions) {
      qList.innerHTML = data.suggested_questions.map((q) => `<li>💬 "${q}"</li>`).join("");
    }

    // Recommended Doctors
    const docWrap = document.getElementById("recommended-doctors-row");
    if (docWrap && data.doctors) {
      if (data.doctors.length === 0) {
        docWrap.innerHTML = '<div style="color:var(--text-muted);font-size:0.88rem;">No direct doctor recommendations found.</div>';
      } else {
        docWrap.innerHTML = data.doctors
          .map((d) => `
            <div class="card" style="display:flex;flex-direction:column;justify-content:space-between;gap:0.75rem;">
              <div>
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                  <div>
                    <h4 style="color:#fff;">Dr. ${d.name}</h4>
                    <span style="color:var(--accent-cyan);font-size:0.85rem;font-weight:600;">${d.specialty}</span>
                  </div>
                  <span class="badge badge-verified">${d.match_score}% Match</span>
                </div>
                <p style="font-size:0.82rem;color:var(--text-muted);margin-top:0.4rem;">${d.experience_years} yrs exp • ${d.rating}★</p>
                <p style="font-size:0.82rem;color:var(--text-secondary);margin-top:0.3rem;">🏥 ${d.hospital ? d.hospital.name : 'Hospital'} (${d.distance_km || 0} km)</p>
                <p style="font-size:0.8rem;color:#94a3b8;margin-top:0.35rem;font-style:italic;">"${d.recommendation_reason}"</p>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-top:0.5rem;">
                <a href="/doctors/${d.doctor_id}/" class="btn btn-outline" style="font-size:0.8rem;">Profile</a>
                <a href="/navigation/?destination_lat=${d.hospital ? d.hospital.latitude : ''}&destination_lng=${d.hospital ? d.hospital.longitude : ''}&hospital_name=${encodeURIComponent(d.hospital ? d.hospital.name : '')}" class="btn btn-primary" style="font-size:0.8rem;">Directions</a>
              </div>
            </div>
          `)
          .join("");
      }
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  ReportUploadManager.init();
});
