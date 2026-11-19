/**
 * MediScanAI — User Location Detection Service
 * Uses HTML5 Geolocation API with manual fallback, radius management, and permission controls.
 */

const UserLocationManager = {
  currentCoords: null,
  currentRadiusMeters: 10000,

  init() {
    this.loadSavedLocation();
    this.bindLocationPill();
  },

  loadSavedLocation() {
    const saved = localStorage.getItem("mediscan_user_location");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        this.currentCoords = { latitude: parsed.latitude, longitude: parsed.longitude };
        this.currentRadiusMeters = parsed.radius_meters || 10000;
        this.updatePillDisplay(parsed.address || `${parsed.latitude.toFixed(3)}, ${parsed.longitude.toFixed(3)}`);
      } catch (e) {
        console.warn("Failed to parse saved location", e);
      }
    }
  },

  bindLocationPill() {
    const pill = document.getElementById("nav-location-pill");
    if (pill) {
      pill.addEventListener("click", () => {
        HealthcareApp.openModal("location-modal");
      });
    }
  },

  /**
   * Request user permission and obtain current GPS location
   */
  detectCurrentLocation(callback) {
    if (!navigator.geolocation) {
      HealthcareApp.showToast("Geolocation is not supported by your browser.", "error");
      return;
    }

    HealthcareApp.showToast("Detecting your location...", "info");

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const accuracy = pos.coords.accuracy;

        this.currentCoords = { latitude: lat, longitude: lng };
        const address = `GPS: ${lat.toFixed(4)}, ${lng.toFixed(4)} (±${Math.round(accuracy)}m)`;

        // Persist to backend and localStorage
        await this.saveLocation(lat, lng, address, this.currentRadiusMeters, false);
        this.updatePillDisplay(address);
        HealthcareApp.showToast("Location detected successfully!", "success");

        if (typeof callback === "function") {
          callback({ latitude: lat, longitude: lng, address });
        }
      },
      (err) => {
        let msg = "Unable to retrieve your location.";
        if (err.code === err.PERMISSION_DENIED) {
          msg = "Location permission was denied. You can manually enter coordinates.";
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          msg = "Location information is currently unavailable.";
        } else if (err.code === err.TIMEOUT) {
          msg = "The request to get user location timed out.";
        }
        HealthcareApp.showToast(msg, "error");
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    );
  },

  /**
   * Manually set location coordinates
   */
  async setManualLocation(lat, lng, address = "", callback) {
    const latNum = parseFloat(lat);
    const lngNum = parseFloat(lng);

    if (isNaN(latNum) || isNaN(lngNum) || latNum < -90 || latNum > 90 || lngNum < -180 || lngNum > 180) {
      HealthcareApp.showToast("Please enter valid latitude (-90 to 90) and longitude (-180 to 180).", "error");
      return false;
    }

    const label = address || `Manual: ${latNum.toFixed(4)}, ${lngNum.toFixed(4)}`;
    this.currentCoords = { latitude: latNum, longitude: lngNum };

    await this.saveLocation(latNum, lngNum, label, this.currentRadiusMeters, true);
    this.updatePillDisplay(label);
    HealthcareApp.showToast("Location updated manually.", "success");
    HealthcareApp.closeModal("location-modal");

    if (typeof callback === "function") {
      callback({ latitude: latNum, longitude: lngNum, address: label });
    }
    return true;
  },

  async saveLocation(latitude, longitude, address, radius_meters, is_manual) {
    localStorage.setItem(
      "mediscan_user_location",
      JSON.stringify({ latitude, longitude, address, radius_meters, is_manual })
    );

    try {
      await HealthcareApp.fetchJson("/api/location/update/", {
        method: "POST",
        body: JSON.stringify({
          latitude,
          longitude,
          address,
          radius_meters,
          is_manual,
        }),
      });
    } catch (e) {
      console.warn("Failed to sync location to server", e);
    }
  },

  updatePillDisplay(label) {
    const pillText = document.getElementById("location-pill-text");
    if (pillText) {
      pillText.textContent = label.length > 25 ? label.substring(0, 25) + "..." : label;
    }
  },

  getCoordinates() {
    return this.currentCoords || { latitude: 28.5367, longitude: 77.2882 };
  },
};

document.addEventListener("DOMContentLoaded", () => {
  UserLocationManager.init();
});
