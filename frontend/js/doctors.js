/**
 * Verified Doctor Recommendation & Booking Manager
 */

const DoctorsManager = {
  doctors: [],

  init() {
    this.bindEvents();
    this.loadDoctors();
  },

  bindEvents() {
    const specSelect = document.getElementById("doctor-specialty-filter");
    if (specSelect) {
      specSelect.addEventListener("change", () => this.loadDoctors());
    }

    const apptForm = document.getElementById("appointment-booking-form");
    if (apptForm) {
      apptForm.addEventListener("submit", (e) => this.handleBookingSubmit(e));
    }
  },

  async loadDoctors() {
    const grid = document.getElementById("doctors-grid");
    if (!grid) return;

    grid.innerHTML = '<div style="grid-column: 1/-1; padding:2rem; text-align:center; color:var(--text-muted);">Finding recommended doctors...</div>';

    const coords = UserLocationManager.getCoordinates();
    const specSelect = document.getElementById("doctor-specialty-filter");
    const specialty = specSelect ? specSelect.value : "";

    const params = new URLSearchParams({
      latitude: coords.latitude,
      longitude: coords.longitude,
    });
    if (specialty) params.append("specialty", specialty);

    try {
      const res = await HealthcareApp.fetchJson(`/api/doctors/recommend/?${params.toString()}`);
      this.doctors = res.doctors || [];
      this.renderDoctorCards(this.doctors);
    } catch (e) {
      console.error(e);
      grid.innerHTML = `<div style="grid-column: 1/-1; padding:2rem; text-align:center; color:var(--accent-rose);">Error loading doctors: ${e.message}</div>`;
    }
  },

  renderDoctorCards(doctors) {
    const grid = document.getElementById("doctors-grid");
    if (!grid) return;

    if (doctors.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1/-1; padding: 3rem 1rem; text-align: center; color: var(--text-muted); background: var(--bg-card); border-radius: var(--radius-md);">
          <h3>No matching doctors found</h3>
          <p style="margin-top: 0.5rem; font-size: 0.88rem;">Try selecting a different specialty or clearing filters.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = doctors
      .map((d) => {
        const rating = Number(d.rating) || 0;
        const ratingStars = rating > 0 ? "★".repeat(Math.round(rating)) : "";
        const hospName = d.hospital ? d.hospital.name : "";
        const distText = d.distance_km !== null ? `${d.distance_km} km` : "Nearby";

        return `
          <article class="doctor-card">
            <div>
              <div class="doctor-header">
                <img src="${d.profile_image || '/static/img/doctor-placeholder.svg'}" alt="Dr. ${d.name}" class="doctor-avatar" />
                <div class="doctor-info">
                  <h3 class="doctor-name">Dr. ${d.name}</h3>
                  <span class="doctor-specialty">${d.specialty}</span>
                  <span class="doctor-experience">${d.experience_years} years experience${rating > 0 ? ` • <span style="color:#fbbf24;">${rating} ${ratingStars}</span>` : ""}</span>
                </div>
              </div>

              <div style="margin-top: 0.85rem;">
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:var(--text-secondary);">
                  <span>Match Score</span>
                  <span style="font-weight:700; color:var(--accent-cyan);">${d.match_score}%</span>
                </div>
                <div class="match-score-bar-wrap">
                  <div class="match-score-bar" style="width: ${d.match_score}%;"></div>
                </div>
              </div>

              <div style="margin-top: 0.85rem; font-size: 0.82rem; color: var(--text-muted);">
                ${hospName ? `<p>🏥 ${hospName} (${distText})</p>` : ""}
                <p style="margin-top: 0.35rem; font-style: italic; color: #94a3b8;">"${d.recommendation_reason}"</p>
              </div>
            </div>

            <div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle);">
                <span style="font-size:0.8rem; color:var(--text-muted);">Consultation</span>
                <span class="doctor-fee">₹${d.consultation_fee}</span>
              </div>

              <div class="doctor-actions">
                <a href="/doctors/${d.doctor_id}/" class="btn btn-outline" style="font-size:0.82rem;">Profile</a>
                ${d.appointment_available && d.hospital ? `<button type="button" class="btn btn-primary" style="font-size:0.82rem;" onclick="DoctorsManager.openAppointmentModal(${d.doctor_id}, 'Dr. ${d.name}', ${d.hospital.id}, '${hospName}')">Book Visit</button>` : '<span class="btn btn-outline" style="font-size:0.82rem;">Appointments unavailable</span>'}
              </div>
            </div>
          </article>
        `;
      })
      .join("");
  },

  openAppointmentModal(doctorId, doctorName, hospitalId, hospitalName) {
    const docIdInput = document.getElementById("booking-doctor-id");
    const hospIdInput = document.getElementById("booking-hospital-id");
    const titleEl = document.getElementById("booking-modal-title");
    const subEl = document.getElementById("booking-modal-subtitle");

    if (docIdInput) docIdInput.value = doctorId;
    if (hospIdInput) hospIdInput.value = hospitalId || "";
    if (titleEl) titleEl.textContent = `Book Appointment with ${doctorName}`;
    if (subEl) subEl.textContent = `At ${hospitalName}`;

    // Set default date to tomorrow
    const dateInput = document.getElementById("booking-date");
    if (dateInput) {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      dateInput.value = tomorrow.toISOString().split("T")[0];
      dateInput.min = new Date().toISOString().split("T")[0];
    }

    HealthcareApp.openModal("appointment-modal");
  },

  async handleBookingSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    const payload = {
      doctor_id: form.doctor_id.value,
      hospital_id: form.hospital_id.value || null,
      appointment_date: form.appointment_date.value,
      appointment_time: form.appointment_time.value,
      reason_for_visit: form.reason_for_visit.value,
      contact_phone: form.contact_phone.value,
    };

    try {
      const res = await HealthcareApp.fetchJson("/api/appointments/book/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      HealthcareApp.showToast(res.message || "Appointment booked successfully!", "success");
      HealthcareApp.closeModal("appointment-modal");
      form.reset();
    } catch (err) {
      HealthcareApp.showToast(err.message || "Booking failed.", "error");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("doctors-grid")) {
    DoctorsManager.init();
  }
});
