import logging
from typing import List, Dict, Any, Optional
from .hospital_finder import haversine_distance
from .doctor_ranking import DoctorRankingEngine

logger = logging.getLogger(__name__)


class DoctorRecommender:
    """Matches and ranks verified doctors for a user's location, medical report, and clinical specialties."""

    @classmethod
    def recommend_doctors(
        cls,
        specialty_codes: List[str] = None,
        user_latitude: Optional[float] = None,
        user_longitude: Optional[float] = None,
        report_findings: Optional[List[Dict[str, Any]]] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Finds and ranks doctors using multi-factor ranking."""
        from django.db.models import Prefetch
        from backend.core.healthcare_intelligence.backend.models import Doctor, DoctorHospital, DoctorQualification

        specialty_codes = specialty_codes or ["general_medicine"]
        primary_code = specialty_codes[0] if specialty_codes else "general_medicine"

        # Query verified doctors
        doctors_qs = (
            Doctor.objects.filter(verified=True)
            .select_related("primary_specialty")
            .prefetch_related(
                "secondary_specialties",
                Prefetch(
                    "qualifications",
                    queryset=DoctorQualification.objects.filter(verification_status="verified"),
                ),
                Prefetch(
                    "hospital_affiliations",
                    queryset=DoctorHospital.objects.filter(hospital__verified=True).select_related("hospital"),
                ),
            )
        )

        ranked_list = []
        for doc in doctors_qs:
            doc_primary = doc.primary_specialty.code.lower()
            doc_secondaries = [s.code.lower() for s in doc.secondary_specialties.all()]

            # Determine match level
            if doc_primary in specialty_codes:
                match_level = "primary"
            elif any(code in doc_secondaries for code in specialty_codes):
                match_level = "secondary"
            elif "general_medicine" in doc_primary:
                match_level = "general"
            else:
                continue  # Specialty doesn't match requested filter

            # Determine distance to doctor's primary hospital
            distance_km = None
            primary_hospital = None
            affiliations = doc.hospital_affiliations.all()
            for aff in affiliations:
                h = aff.hospital
                if aff.is_primary or primary_hospital is None:
                    primary_hospital = h
                if user_latitude is not None and user_longitude is not None:
                    dist = haversine_distance(user_latitude, user_longitude, h.latitude, h.longitude)
                    if distance_km is None or dist < distance_km:
                        distance_km = dist

            # Compute multi-factor ranking score
            score_data = DoctorRankingEngine.compute_score(
                specialty_match_level=match_level,
                distance_km=distance_km,
                experience_years=doc.experience_years,
                rating=doc.rating,
                is_available=doc.appointment_available,
            )

            # Build clinical recommendation reason
            qual_str = ", ".join([q.degree for q in doc.qualifications.all()[:2]])
            qualification_text = f" ({qual_str})" if qual_str else ""
            hosp_str = f" at {primary_hospital.name}" if primary_hospital else ""
            dist_str = f" ({distance_km} km away)" if distance_km is not None else ""
            rating_str = f" and {doc.rating}★ rating" if doc.rating > 0 else ""
            reason = (
                f"Recommended based on {doc.primary_specialty.name} specialization{qualification_text} "
                f"with {doc.experience_years} years experience{rating_str}{hosp_str}{dist_str}."
            )

            ranked_list.append({
                "_doctor": doc,
                "doctor_id": doc.id,
                "name": doc.name,
                "source": "verified_directory",
                "profile_image": doc.profile_image,
                "specialty": doc.primary_specialty.name,
                "specialty_code": doc.primary_specialty.code,
                "experience_years": doc.experience_years,
                "rating": doc.rating,
                "reviews_count": doc.reviews_count,
                "verified": doc.verified,
                "consultation_fee": float(doc.consultation_fee),
                "appointment_available": doc.appointment_available,
                "distance_km": distance_km,
                "hospital": {
                    "id": primary_hospital.id if primary_hospital else None,
                    "name": primary_hospital.name if primary_hospital else None,
                    "address": primary_hospital.address if primary_hospital else "",
                    "latitude": primary_hospital.latitude if primary_hospital else None,
                    "longitude": primary_hospital.longitude if primary_hospital else None,
                    "phone": primary_hospital.phone if primary_hospital else "",
                } if primary_hospital else None,
                "match_score": score_data["total_score"],
                "score_breakdown": score_data["breakdown"],
                "recommendation_reason": reason,
                "priority": "high" if score_data["total_score"] >= 80 else "moderate",
            })

        # Sort by total score descending, then distance ascending
        ranked_list.sort(key=lambda x: (x["match_score"], -(x["distance_km"] if x["distance_km"] is not None else 9999)), reverse=True)
        return ranked_list[:max_results]
