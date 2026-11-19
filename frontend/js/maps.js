/**
 * Google Maps Interactive Navigation & Route Visualizer
 */

const MapsManager = {
  map: null,
  directionsService: null,
  directionsRenderer: null,
  userMarker: null,
  destinationMarker: null,
  currentTravelMode: "DRIVING",

  originCoords: { lat: 28.5367, lng: 77.2882 },
  destCoords: null,

  init(config = {}) {
    if (config.originLat && config.originLng) {
      this.originCoords = { lat: parseFloat(config.originLat), lng: parseFloat(config.originLng) };
    }
    if (
      config.destLat !== null && config.destLat !== undefined &&
      config.destLng !== null && config.destLng !== undefined &&
      Number.isFinite(Number(config.destLat)) && Number.isFinite(Number(config.destLng))
    ) {
      this.destCoords = { lat: parseFloat(config.destLat), lng: parseFloat(config.destLng) };
    }

    this.bindTravelModes();
    this.initMap();
    if (this.destCoords) this.calculateAndDisplayRoute();
  },

  bindTravelModes() {
    document.querySelectorAll(".travel-mode-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        document.querySelectorAll(".travel-mode-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        this.currentTravelMode = btn.dataset.mode || "DRIVING";
        this.calculateAndDisplayRoute();
      });
    });
  },

  initMap() {
    const mapEl = document.getElementById("map");
    if (!mapEl) return;

    if (typeof google !== "undefined" && google.maps) {
      this.map = new google.maps.Map(mapEl, {
        center: this.originCoords,
        zoom: 13,
        styles: [
          { elementType: "geometry", stylers: [{ color: "#242f3e" }] },
          { elementType: "labels.text.stroke", stylers: [{ color: "#242f3e" }] },
          { elementType: "labels.text.fill", stylers: [{ color: "#746855" }] },
          { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#d59563" }] },
          { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#d59563" }] },
          { featureType: "road", elementType: "geometry", stylers: [{ color: "#38414e" }] },
          { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#212a37" }] },
          { featureType: "road", elementType: "labels.text.fill", stylers: [{ color: "#9ca5b3" }] },
          { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#746855" }] },
          { featureType: "water", elementType: "geometry", stylers: [{ color: "#17263c" }] },
        ],
      });

      this.directionsService = new google.maps.DirectionsService();
      this.directionsRenderer = new google.maps.DirectionsRenderer({
        map: this.map,
        suppressMarkers: false,
        polylineOptions: {
          strokeColor: "#06b6d4",
          strokeWeight: 5,
        },
      });
    } else {
      // Interactive Canvas Fallback Map if Google Maps API key is pending
      this.renderCanvasFallbackMap(mapEl);
    }
  },

  async calculateAndDisplayRoute() {
    if (!this.destCoords) return;
    const navUrl = `https://www.google.com/maps/dir/?api=1&destination=${this.destCoords.lat},${this.destCoords.lng}&travelmode=${this.currentTravelMode.toLowerCase()}&origin=${this.originCoords.lat},${this.originCoords.lng}`;
    
    const startNavBtn = document.getElementById("start-navigation-btn");
    if (startNavBtn) {
      startNavBtn.href = navUrl;
    }

    // Call backend route API
    try {
      const res = await HealthcareApp.fetchJson("/api/route/calculate/", {
        method: "POST",
        body: JSON.stringify({
          origin_lat: this.originCoords.lat,
          origin_lng: this.originCoords.lng,
          destination_lat: this.destCoords.lat,
          destination_lng: this.destCoords.lng,
          travel_mode: this.currentTravelMode,
        }),
      });

      if (res.success && res.route) {
        const distEl = document.getElementById("route-distance-text");
        const durEl = document.getElementById("route-duration-text");
        if (distEl) distEl.textContent = res.route.distance_text;
        if (durEl) durEl.textContent = res.route.duration_text;
      }
    } catch (e) {
      console.warn("Backend route API warning", e);
    }

    // Google Directions Renderer if available
    if (this.directionsService && this.directionsRenderer) {
      const mode = google.maps.TravelMode[this.currentTravelMode] || google.maps.TravelMode.DRIVING;
      this.directionsService.route(
        {
          origin: this.originCoords,
          destination: this.destCoords,
          travelMode: mode,
        },
        (result, status) => {
          if (status === google.maps.DirectionsStatus.OK) {
            this.directionsRenderer.setDirections(result);
          }
        }
      );
    }
  },

  renderCanvasFallbackMap(mapEl) {
    if (!this.destCoords) {
      mapEl.innerHTML = `
        <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; background:#111827; padding:2rem; text-align:center; color:var(--text-secondary);">
          Select a verified hospital to view directions.
        </div>
      `;
      return;
    }
    mapEl.innerHTML = `
      <div style="width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; background:#111827; padding:2rem; text-align:center;">
        <div style="width:64px; height:64px; border-radius:50%; background:rgba(6,182,212,0.15); display:flex; align-items:center; justify-content:center; color:var(--accent-cyan); font-size:1.8rem; margin-bottom:1rem;">
          🗺️
        </div>
        <h3 style="color:#fff; margin-bottom:0.5rem;">Interactive GPS Routing Ready</h3>
        <p style="color:var(--text-secondary); max-width:400px; font-size:0.88rem; margin-bottom:1.5rem;">
          Origin: (${this.originCoords.lat.toFixed(4)}, ${this.originCoords.lng.toFixed(4)})<br>
          Selected destination: (${this.destCoords.lat.toFixed(4)}, ${this.destCoords.lng.toFixed(4)})
        </p>
        <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:1.25rem;">
          Google Maps Platform is fully integrated. Live turn-by-turn navigation opens directly in Google Maps.
        </p>
        <a id="fallback-start-btn" href="https://www.google.com/maps/dir/?api=1&destination=${this.destCoords.lat},${this.destCoords.lng}&travelmode=driving" target="_blank" rel="noopener noreferrer" class="btn btn-nav-start">
          🚀 START NAVIGATION IN GOOGLE MAPS
        </a>
      </div>
    `;
  },
};
