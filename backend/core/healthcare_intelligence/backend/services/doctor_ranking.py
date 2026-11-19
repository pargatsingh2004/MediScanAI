from typing import Dict, Any


class DoctorRankingEngine:
    """Configurable multi-factor ranking algorithm for doctor recommendations.
    
    Default weights:
    - Specialty Relevance: 40%
    - Proximity / Distance: 20%
    - Qualifications & Experience: 20%
    - Verified Ratings: 15%
    - Appointment Availability: 5%
    """

    WEIGHT_SPECIALTY = 0.40
    WEIGHT_DISTANCE = 0.20
    WEIGHT_EXPERIENCE = 0.20
    WEIGHT_RATING = 0.15
    WEIGHT_AVAILABILITY = 0.05

    @classmethod
    def compute_score(
        cls,
        specialty_match_level: str,  # 'primary' | 'secondary' | 'general'
        distance_km: float,
        experience_years: int,
        rating: float,
        is_available: bool,
    ) -> Dict[str, Any]:
        """Calculates normalized sub-scores and final weighted recommendation score (0 - 100)."""

        # 1. Specialty Relevance Score (0 - 100)
        if specialty_match_level == "primary":
            spec_score = 100.0
        elif specialty_match_level == "secondary":
            spec_score = 75.0
        else:
            spec_score = 40.0

        # 2. Distance Score (0 - 100)
        # Closer is better: < 2km = 100, 10km = ~80, 25km = ~50, >50km = 10
        if distance_km is None or distance_km < 0:
            dist_score = 50.0  # neutral default when location unknown
        elif distance_km <= 2.0:
            dist_score = 100.0
        elif distance_km <= 10.0:
            dist_score = max(70.0, 100.0 - (distance_km - 2.0) * 3.75)
        elif distance_km <= 30.0:
            dist_score = max(30.0, 70.0 - (distance_km - 10.0) * 2.0)
        else:
            dist_score = max(10.0, 30.0 - (distance_km - 30.0) * 0.5)

        # 3. Experience Score (0 - 100)
        # 15+ years = 100, 10 years = ~80, 5 years = ~60, 1 year = 40
        exp_score = min(100.0, max(30.0, 30.0 + (experience_years * 4.67)))

        # 4. Rating Score (0 - 100)
        # 5.0 = 100, 4.5 = 90, 4.0 = 80, etc.
        rating_score = min(100.0, max(0.0, (rating / 5.0) * 100.0))

        # 5. Availability Score (0 - 100)
        avail_score = 100.0 if is_available else 25.0

        # Weighted Total
        total_score = (
            (spec_score * cls.WEIGHT_SPECIALTY)
            + (dist_score * cls.WEIGHT_DISTANCE)
            + (exp_score * cls.WEIGHT_EXPERIENCE)
            + (rating_score * cls.WEIGHT_RATING)
            + (avail_score * cls.WEIGHT_AVAILABILITY)
        )

        return {
            "total_score": round(total_score, 1),
            "breakdown": {
                "specialty_score": round(spec_score, 1),
                "distance_score": round(dist_score, 1),
                "experience_score": round(exp_score, 1),
                "rating_score": round(rating_score, 1),
                "availability_score": round(avail_score, 1),
            },
        }
