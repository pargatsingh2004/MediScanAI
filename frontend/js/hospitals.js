/**
 * Nearby Hospitals Client-Side Manager
 * Fetches nearby verified hospitals and updates cards and map markers dynamically.
 */

const HospitalsManager = {
  hospitals: [],

  init() {
    this.bindEvents();
    this.loadHospitals();
  },

  bindEvents() {
    const radiusSlider = document.getElementById("radius-slider");
    const radiusValText = document.getElementById("radius-val-text");
    const specialtySelect = document.getElementById("specialty-filter");
    const typeSelect = document.getElementById("type-filter");
    const sortSelect = document.getElementById("sort-filter");
    const detectBtn = document.getElementById("detect-loc-btn");

    if (radiusSlider && radiusValText) {
      radiusSlider.addEventListener("input", (e) => {
        const km = (parseInt(e.target.value) / 1000).toFixed(0);
        radiusValText.textContent = `${km} km`;
      });
      radiusSlider.addEventListener("change", () => this.loadHospitals());
    }

    if (specialtySelect) specialtySelect.addEventListener("change", () => this.loadHospitals());
    if (typeSelect) typeSelect.addEventListener("change", () => this.loadHospitals());
    if (sortSelect) sortSelect.addEventListener("change", () => this.loadHospitals());

    if (detectBtn) {
      detectBtn.addEventListener("click", () => {
        UserLocationManager.detectCurrentLocation(() => {
          this.loadHospitals();
        });
      });
    }
  },

  async loadHospitals() {
    const listContainer = document.getElementById("hospitals-list");
    const countEl = document.getElementById("results-count-text");
    if (!listContainer) return;

    listContainer.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-muted);">Finding nearby hospitals...</div>';

    const coords = UserLocationManager.getCoordinates();
    const radiusSlider = document.getElementById("radius-slider");
    const specialtySelect = document.getElementById("specialty-filter");
    const typeSelect = document.getElementById("type-filter");
    const sortSelect = document.getElementById("sort-filter");

    const radius = radiusSlider ? radiusSlider.value : 10000;
    const specialty = specialtySelect ? specialtySelect.value : "";
    const hospitalType = typeSelect ? typeSelect.value : "";
    const sortBy = sortSelect ? sortSelect.value : "distance";

    const params = new URLSearchParams({
      latitude: coords.latitude,
      longitude: coords.longitude,
      radius_meters: radius,
      sort_by: sortBy,
    });
    if (specialty) params.append("specialty", specialty);
    if (hospitalType) params.append("hospital_type", hospitalType);

    try {
      const res = await HealthcareApp.fetchJson(`/api/hospitals/nearby/?${params.toString()}`);
      this.hospitals = res.hospitals || [];

      if (countEl) {
        countEl.textContent = `Found ${this.hospitals.length} hospital(s)`;
      }

      this.renderHospitalCards(this.hospitals);

      // Notify map if initialized
      if (typeof MapsManager !== "undefined" && MapsManager.updateHospitalMarkers) {
        MapsManager.updateHospitalMarkers(this.hospitals);
      }
    } catch (e) {
      console.error(e);
      listContainer.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--accent-rose);">Error loading hospitals: ${e.message}</div>`;
    }
  },

  renderHospitalCards(hospitals) {
    const listContainer = document.getElementById("hospitals-list");
    if (!listContainer) return;

    if (hospitals.length === 0) {
      listContainer.innerHTML = `
        <div style="padding: 3rem 1rem; text-align: center; color: var(--text-muted); background: var(--bg-card); border-radius: var(--radius-md);">
          <h3>No hospitals found in this radius</h3>
          <p style="margin-top: 0.5rem; font-size: 0.88rem;">Try increasing your search radius or clearing active specialty filters.</p>
        </div>
      `;
      return;
    }

    listContainer.innerHTML = hospitals
      .map((h) => {
        const rating = Number(h.rating) || 0;
        const ratingStars = rating > 0 ? "★".repeat(Math.round(rating)) + "☆".repeat(5 - Math.round(rating)) : "";
        const sourceLabel = h.source === "verified_database"
          ? "MediScanAI verified directory"
          : "Google Places listing (not independently verified)";
        const detailsUrl = h.id ? `/hospitals/${h.id}/` : "#";
        const navUrl = `/navigation/?destination_lat=${h.latitude}&destination_lng=${h.longitude}&hospital_name=${encodeURIComponent(h.name)}`;

        return `
          <article class="hospital-card">
            <div class="hospital-card-head">
              <div>
                <h3 class="hospital-name">${h.name}</h3>
                <div class="hospital-meta" style="margin-top: 0.35rem;">
                  ${rating > 0 ? `<span class="rating-pill">${rating} ${ratingStars}</span><span>(${h.reviews_count} reviews)</span>` : ""}
                  <span class="badge ${h.verified ? "badge-verified" : ""}">${h.hospital_type}</span>
                  ${h.emergency_services ? '<span class="badge badge-critical">24/7 Emergency</span>' : ''}
                </div>
              </div>
              <span class="distance-pill">${h.distance_km} km away</span>
            </div>

            <p class="hospital-address">📍 ${h.address}</p>
            <p style="font-size:0.78rem;color:var(--text-muted);">${sourceLabel}</p>

            ${h.phone ? `<p style="font-size: 0.82rem; color: var(--text-muted);">📞 ${h.phone}</p>` : ''}

            <div class="hospital-actions">
              ${h.id ? `<a href="${detailsUrl}" class="btn btn-outline" style="font-size:0.82rem;padding:0.4rem 0.8rem;">View Details</a>` : ''}
              <a href="${navUrl}" class="btn btn-primary" style="font-size:0.82rem;padding:0.4rem 0.8rem;">Directions & Route</a>
              <a href="https://www.google.com/maps/dir/?api=1&destination=${h.latitude},${h.longitude}&travelmode=driving" target="_blank" rel="noopener noreferrer" class="btn btn-success" style="font-size:0.82rem;padding:0.4rem 0.8rem;">START NAVIGATION</a>
            </div>
          </article>
        `;
      })
      .join("");
  },
};

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("hospitals-list")) {
    HospitalsManager.init();
  }
});
