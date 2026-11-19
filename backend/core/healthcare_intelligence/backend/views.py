import os
import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import (
    HealthcareProfile,
    Specialty,
    Hospital,
    Doctor,
    MedicalReport,
    ReportAnalysis,
    MedicalFinding,
    DoctorRecommendation,
    HospitalRecommendation,
    UserLocation,
    NavigationHistory,
    Appointment,
    DoctorHospital,
    DoctorQualification,
)
from .serializers import (
    SpecialtySerializer,
    HospitalSerializer,
    DoctorSerializer,
    MedicalReportSerializer,
    ReportAnalysisSerializer,
    AppointmentSerializer,
)
from .services.report_extractor import ReportExtractor
from .services.medical_nlp import MedicalNLP
from .services.specialty_recommender import SpecialtyRecommender
from .services.hospital_finder import HospitalFinder, haversine_distance
from .services.doctor_recommender import DoctorRecommender
from .services.directions_service import DirectionsService

logger = logging.getLogger(__name__)
User = get_user_model()


def get_current_user_or_demo(request):
    """Return the central session user without creating or impersonating accounts."""
    return request.user if request.user.is_authenticated else None


# ==============================================================================
# HTML TEMPLATE VIEWS (HTML5 + CSS3 + Vanilla JavaScript)
# ==============================================================================

@login_required
def healthcare_dashboard_view(request):
    """Main Healthcare Intelligence Dashboard."""
    user = get_current_user_or_demo(request)
    recent_reports = MedicalReport.objects.filter(user=user).select_related("analysis")[:5]
    hospitals_count = Hospital.objects.count()
    doctors_count = Doctor.objects.count()
    specialties_count = Specialty.objects.count()

    # Get latest user location
    user_location = UserLocation.objects.filter(user=user).first()

    context = {
        "title": "Healthcare Intelligence Dashboard",
        "user": user,
        "recent_reports": recent_reports,
        "hospitals_count": hospitals_count,
        "doctors_count": doctors_count,
        "specialties_count": specialties_count,
        "user_location": user_location,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
    return render(request, "healthcare_intelligence/healthcare_dashboard.html", context)


def nearby_hospitals_view(request):
    """Interactive Nearby Hospitals discovery page."""
    user = get_current_user_or_demo(request)
    specialties = Specialty.objects.filter(is_active=True)
    user_location = UserLocation.objects.filter(user=user).first()

    default_lat = user_location.latitude if user_location else 28.5367
    default_lng = user_location.longitude if user_location else 77.2882

    context = {
        "title": "Find Nearby Hospitals",
        "specialties": specialties,
        "user_location": user_location,
        "default_lat": default_lat,
        "default_lng": default_lng,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
    return render(request, "healthcare_intelligence/nearby_hospitals.html", context)


def find_doctors_view(request):
    """Find and compare suitable nearby doctors."""
    user = get_current_user_or_demo(request)
    specialties = Specialty.objects.filter(is_active=True)
    selected_spec = request.GET.get("specialty", "")
    user_location = UserLocation.objects.filter(user=user).first()

    default_lat = user_location.latitude if user_location else 28.5367
    default_lng = user_location.longitude if user_location else 77.2882

    context = {
        "title": "Find Verified Doctors",
        "specialties": specialties,
        "selected_specialty": selected_spec,
        "user_location": user_location,
        "default_lat": default_lat,
        "default_lng": default_lng,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
    return render(request, "healthcare_intelligence/find_doctors.html", context)


def doctor_profile_view(request, doctor_id):
    """Comprehensive verified doctor profile."""
    doctor = get_object_or_404(
        Doctor.objects.select_related("primary_specialty")
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
        ),
        id=doctor_id,
        verified=True,
    )
    user = get_current_user_or_demo(request)
    user_location = UserLocation.objects.filter(user=user).first()

    # Calculate distance to doctor's primary hospital
    primary_aff = (
        doctor.hospital_affiliations.filter(is_primary=True, hospital__verified=True).first()
        or doctor.hospital_affiliations.filter(hospital__verified=True).first()
    )
    distance_km = None
    if user_location and primary_aff:
        distance_km = haversine_distance(
            user_location.latitude, user_location.longitude,
            primary_aff.hospital.latitude, primary_aff.hospital.longitude
        )

    context = {
        "title": f"Dr. {doctor.name} - Profile",
        "doctor": doctor,
        "primary_aff": primary_aff,
        "distance_km": distance_km,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
    return render(request, "healthcare_intelligence/doctor_profile.html", context)


def hospital_details_view(request, hospital_id):
    """Detailed hospital profile and list of affiliated doctors."""
    hospital = get_object_or_404(
        Hospital.objects.filter(verified=True).prefetch_related(
            "specialties",
            "affiliated_doctors__doctor__primary_specialty",
        ),
        id=hospital_id,
    )
    user = get_current_user_or_demo(request)
    user_location = UserLocation.objects.filter(user=user).first()

    distance_km = None
    if user_location:
        distance_km = haversine_distance(
            user_location.latitude, user_location.longitude,
            hospital.latitude, hospital.longitude
        )

    nav_url = DirectionsService.get_navigation_url(
        hospital.latitude, hospital.longitude,
        user_location.latitude if user_location else None,
        user_location.longitude if user_location else None
    )

    context = {
        "title": hospital.name,
        "hospital": hospital,
        "distance_km": distance_km,
        "navigation_url": nav_url,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
    return render(request, "healthcare_intelligence/hospital_details.html", context)


@login_required
def report_analysis_view(request, report_id=None):
    """Medical Report Upload & AI Healthcare Analysis workbench."""
    user = get_current_user_or_demo(request)
    active_report = None
    if report_id:
        active_report = get_object_or_404(MedicalReport, id=report_id, user=user)

    recent_reports = MedicalReport.objects.filter(user=user)[:8]

    context = {
        "title": "Medical Report Analysis",
        "active_report": active_report,
        "recent_reports": recent_reports,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
    return render(request, "healthcare_intelligence/report_analysis.html", context)


def map_navigation_view(request):
    """Interactive Google Maps directions and live navigation interface."""
    user = get_current_user_or_demo(request)
    hospital_id = request.GET.get("hospital_id")
    doctor_id = request.GET.get("doctor_id")

    hospital = None
    if hospital_id:
        hospital = Hospital.objects.filter(id=hospital_id, verified=True).first()

    doctor = None
    if doctor_id:
        doctor = Doctor.objects.filter(id=doctor_id, verified=True).first()
        if not hospital and doctor:
            primary_aff = doctor.hospital_affiliations.filter(
                is_primary=True,
                hospital__verified=True,
            ).first()
            if primary_aff:
                hospital = primary_aff.hospital

    user_location = UserLocation.objects.filter(user=user).first()
    default_lat = user_location.latitude if user_location else 28.5367
    default_lng = user_location.longitude if user_location else 77.2882

    destination_lat = hospital.latitude if hospital else None
    destination_lng = hospital.longitude if hospital else None
    destination_name = hospital.name if hospital else ""
    external_destination = False

    if not hospital:
        try:
            candidate_lat = float(request.GET.get("destination_lat", ""))
            candidate_lng = float(request.GET.get("destination_lng", ""))
        except (TypeError, ValueError):
            candidate_lat = candidate_lng = None
        if (
            candidate_lat is not None
            and candidate_lng is not None
            and -90 <= candidate_lat <= 90
            and -180 <= candidate_lng <= 180
        ):
            destination_lat = candidate_lat
            destination_lng = candidate_lng
            destination_name = request.GET.get("hospital_name", "").strip() or "Selected destination"
            external_destination = True

    initial_nav_url = (
        DirectionsService.get_navigation_url(destination_lat, destination_lng, default_lat, default_lng)
        if destination_lat is not None and destination_lng is not None
        else ""
    )

    context = {
        "title": "Hospital Navigation",
        "hospital": hospital,
        "external_destination": external_destination,
        "destination_name": destination_name,
        "doctor": doctor,
        "user_location": user_location,
        "origin_lat": default_lat,
        "origin_lng": default_lng,
        "destination_lat": destination_lat,
        "destination_lng": destination_lng,
        "initial_nav_url": initial_nav_url,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
    return render(request, "healthcare_intelligence/map_navigation.html", context)


# ==============================================================================
# REST API ENDPOINTS (Fetch API / JSON)
# ==============================================================================

class UpdateLocationAPIView(APIView):
    """Save or update user's coordinates with explicit permission."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = get_current_user_or_demo(request)
        try:
            data = request.data
            lat = float(data.get("latitude"))
            lng = float(data.get("longitude"))
            address = data.get("address", "")
            radius = int(data.get("radius_meters", 10000))
            is_manual = bool(data.get("is_manual", False))

            loc = UserLocation.objects.create(
                user=user,
                latitude=lat,
                longitude=lng,
                address=address,
                search_radius_meters=radius,
                is_manual=is_manual,
            )

            # Also update profile
            profile, _ = HealthcareProfile.objects.get_or_create(user=user)
            profile.current_latitude = lat
            profile.current_longitude = lng
            profile.location_address = address
            profile.preferred_search_radius = radius
            profile.save()

            return Response({
                "success": True,
                "message": "User location updated successfully.",
                "location": {
                    "latitude": lat,
                    "longitude": lng,
                    "address": address,
                    "radius_meters": radius,
                },
            })
        except Exception as e:
            logger.error(f"Error updating location: {e}")
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class NearbyHospitalsAPIView(APIView):
    """Returns nearby hospitals sorted by distance or rating."""

    def get(self, request):
        user = get_current_user_or_demo(request)
        user_loc = UserLocation.objects.filter(user=user).first()

        try:
            lat = float(request.GET.get("latitude", user_loc.latitude if user_loc else 28.5367))
            lng = float(request.GET.get("longitude", user_loc.longitude if user_loc else 77.2882))
            radius = int(request.GET.get("radius_meters", user_loc.search_radius_meters if user_loc else 10000))
            specialty_code = request.GET.get("specialty")
            hospital_type = request.GET.get("hospital_type")
            sort_by = request.GET.get("sort_by", "distance")

            hospitals = HospitalFinder.search_nearby_hospitals(
                latitude=lat,
                longitude=lng,
                radius_meters=radius,
                specialty_code=specialty_code,
                hospital_type=hospital_type,
                sort_by=sort_by,
            )

            return Response({
                "success": True,
                "total_found": len(hospitals),
                "hospitals": hospitals,
            })
        except Exception as e:
            logger.error(f"Error fetching nearby hospitals: {e}")
            return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DoctorRecommendationsAPIView(APIView):
    """Returns smart doctor recommendations based on specialties, location, and ranking."""

    def get(self, request):
        user = get_current_user_or_demo(request)
        user_loc = UserLocation.objects.filter(user=user).first()

        try:
            specialty_codes = request.GET.getlist("specialty")
            if not specialty_codes and request.GET.get("specialty"):
                specialty_codes = [request.GET.get("specialty")]

            report_id = request.GET.get("report_id")
            if not specialty_codes and report_id:
                report = MedicalReport.objects.filter(id=report_id, user=user).select_related("analysis").first()
                if report and hasattr(report, "analysis"):
                    specialty_codes = [s.code for s in report.analysis.relevant_specialties.all()]

            lat = float(request.GET.get("latitude", user_loc.latitude if user_loc else 28.5367))
            lng = float(request.GET.get("longitude", user_loc.longitude if user_loc else 77.2882))

            recommendations = DoctorRecommender.recommend_doctors(
                specialty_codes=specialty_codes,
                user_latitude=lat,
                user_longitude=lng,
                max_results=12,
            )

            clean_doctors = [
                {k: v for k, v in d.items() if k != "_doctor"}
                for d in recommendations
            ]

            return Response({
                "success": True,
                "total_recommended": len(clean_doctors),
                "doctors": clean_doctors,
            })
        except Exception as e:
            logger.error(f"Error fetching doctor recommendations: {e}")
            return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UploadReportAPIView(APIView):
    """Uploads, validates, extracts OCR, evaluates clinical findings, and recommends specialties."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = get_current_user_or_demo(request)
        file_obj = request.FILES.get("file")

        if not file_obj:
            return Response({"success": False, "error": "A medical report file is required."}, status=status.HTTP_400_BAD_REQUEST)

        # File validation
        ext = os.path.splitext(file_obj.name)[1].lower()
        if ext not in [".pdf", ".jpg", ".jpeg", ".png"]:
            return Response(
                {"success": False, "error": "Invalid format. Only PDF, JPG, JPEG, and PNG files are supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_size_mb = getattr(settings, "MAX_REPORT_SIZE_MB", 20)
        if file_obj.size > (max_size_mb * 1024 * 1024):
            return Response(
                {"success": False, "error": f"File size exceeds the limit of {max_size_mb}MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 1. Create Report model
            report = MedicalReport.objects.create(
                user=user,
                title=os.path.splitext(file_obj.name)[0],
                original_filename=file_obj.name,
                file=file_obj,
                file_type="pdf" if ext == ".pdf" else "image",
                file_size=file_obj.size,
                status="processing",
            )

            # 2. Extract Text via PyMuPDF / pypdf / OCR
            file_path = report.file.path
            extraction_result = ReportExtractor.extract(file_path, mime_type=file_obj.content_type)
            extracted_text = extraction_result["cleaned_text"]

            report.ocr_text = extracted_text
            report.ocr_raw_text = extraction_result["raw_text"]
            report.ocr_status = "completed" if extraction_result["success"] else "failed"
            report.save()

            # 3. Medical NLP Parsing & Clinical Finding Extraction
            findings_data = MedicalNLP.extract_findings_from_text(extracted_text)
            analysis_summary = MedicalNLP.analyze_report_findings(findings_data, raw_text=extracted_text)

            # 4. Specialty Recommendation
            specialties_recs = SpecialtyRecommender.recommend_specialties(
                text=extracted_text, findings=findings_data, top_k=3
            )

            # 5. Persist ReportAnalysis
            primary_spec = None
            if specialties_recs:
                primary_spec = Specialty.objects.filter(code=specialties_recs[0]["code"]).first()

            analysis = ReportAnalysis.objects.create(
                report=report,
                summary=analysis_summary["summary"],
                detected_conditions=analysis_summary["detected_conditions"],
                precautions=analysis_summary["precautions"],
                suggested_questions=analysis_summary["suggested_questions"],
                overall_risk=analysis_summary["overall_risk"],
                requires_urgent_care=analysis_summary["requires_urgent_care"],
                urgency_reason=analysis_summary["urgency_reason"],
                authenticity_hash=extraction_result["sha256"],
                confidence_score=analysis_summary["confidence_score"],
                primary_specialty=primary_spec,
            )

            for rec in specialties_recs:
                s_obj = Specialty.objects.filter(code=rec["code"]).first()
                if s_obj:
                    analysis.relevant_specialties.add(s_obj)

            # 6. Persist individual MedicalFindings
            for f in findings_data:
                MedicalFinding.objects.create(
                    analysis=analysis,
                    test_name=f["test_name"],
                    metric_key=f["metric_key"],
                    measured_value=f["measured_value"],
                    numeric_value=f["numeric_value"],
                    unit=f["unit"],
                    reference_range=f["reference_range"],
                    status=f["status"],
                    severity=f["severity"],
                    clinical_significance=f["clinical_significance"],
                )

            # 7. Match Suitable Doctors
            user_loc = UserLocation.objects.filter(user=user).first()
            lat = user_loc.latitude if user_loc else 28.5367
            lng = user_loc.longitude if user_loc else 77.2882
            spec_codes = [s["code"] for s in specialties_recs]

            doctor_recs = DoctorRecommender.recommend_doctors(
                specialty_codes=spec_codes,
                user_latitude=lat,
                user_longitude=lng,
                report_findings=findings_data,
                max_results=5,
            )

            # Persist DoctorRecommendations
            for doc_item in doctor_recs:
                doc_instance = doc_item.get("_doctor")
                if not doc_instance and doc_item.get("doctor_id"):
                    doc_instance = Doctor.objects.filter(id=doc_item["doctor_id"]).first()
                if doc_instance:
                    DoctorRecommendation.objects.create(
                    user=user,
                    report=report,
                    doctor=doc_instance,
                    specialty=doc_instance.primary_specialty,
                    match_score=doc_item["match_score"],
                    distance_km=doc_item["distance_km"],
                    score_breakdown=doc_item["score_breakdown"],
                    recommendation_reason=doc_item["recommendation_reason"],
                    priority=doc_item["priority"],
                )

            report.status = "analyzed"
            report.save()

            return Response({
                "success": True,
                "message": "Report uploaded and analyzed successfully.",
                "report_id": str(report.id),
                "summary": analysis_summary["summary"],
                "overall_risk": analysis_summary["overall_risk"],
                "requires_urgent_care": analysis_summary["requires_urgent_care"],
                "urgency_reason": analysis_summary["urgency_reason"],
                "detected_conditions": analysis_summary["detected_conditions"],
                "findings": findings_data,
                "specialties": specialties_recs,
                "doctors": [
                    {
                        "doctor_id": d["doctor_id"],
                        "name": d["name"],
                        "specialty": d["specialty"],
                        "rating": d["rating"],
                        "experience_years": d["experience_years"],
                        "match_score": d["match_score"],
                        "distance_km": d["distance_km"],
                        "hospital": d["hospital"],
                        "recommendation_reason": d["recommendation_reason"],
                    }
                    for d in doctor_recs
                ],
                "precautions": analysis_summary["precautions"],
                "suggested_questions": analysis_summary["suggested_questions"],
                "authenticity_hash": extraction_result["sha256"],
            })

        except Exception as e:
            logger.error(f"Error in report processing pipeline: {e}", exc_info=True)
            if "report" in locals():
                report.status = "failed"
                report.save()
            return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CalculateRouteAPIView(APIView):
    """Calculates route summary, travel duration, and Google Maps Navigation link."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = get_current_user_or_demo(request)
        try:
            data = request.data
            origin_lat = float(data.get("origin_lat"))
            origin_lng = float(data.get("origin_lng"))
            dest_lat = float(data.get("destination_lat"))
            dest_lng = float(data.get("destination_lng"))
            travel_mode = data.get("travel_mode", "DRIVING")
            hospital_id = data.get("hospital_id")

            route = DirectionsService.calculate_route_summary(
                origin_lat=origin_lat,
                origin_lng=origin_lng,
                destination_lat=dest_lat,
                destination_lng=dest_lng,
                travel_mode=travel_mode,
            )

            # Record navigation event if hospital is provided
            if hospital_id:
                hosp = Hospital.objects.filter(id=hospital_id).first()
                if hosp:
                    NavigationHistory.objects.create(
                        user=user,
                        destination_hospital=hosp,
                        origin_latitude=origin_lat,
                        origin_longitude=origin_lng,
                        destination_latitude=dest_lat,
                        destination_longitude=dest_lng,
                        travel_mode=travel_mode.upper(),
                        distance_text=route["distance_text"],
                        distance_meters=route["distance_meters"],
                        duration_text=route["duration_text"],
                        duration_seconds=route["duration_seconds"],
                        navigation_url=route["navigation_url"],
                    )

            return Response({
                "success": True,
                "route": route,
            })
        except Exception as e:
            logger.error(f"Error calculating route: {e}")
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BookAppointmentAPIView(APIView):
    """Books a verified doctor consultation."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = get_current_user_or_demo(request)
        try:
            data = request.data
            doctor_id = data.get("doctor_id")
            hospital_id = data.get("hospital_id")
            appt_date = data.get("appointment_date")
            appt_time = data.get("appointment_time", "10:00")
            reason = data.get("reason_for_visit", "")
            phone = data.get("contact_phone", "")

            doctor = get_object_or_404(Doctor, id=doctor_id, verified=True, appointment_available=True)
            if hospital_id:
                hospital = get_object_or_404(Hospital, id=hospital_id, verified=True)
            else:
                primary_aff = doctor.hospital_affiliations.filter(is_primary=True, hospital__verified=True).first()
                if primary_aff is None:
                    return Response(
                        {"success": False, "error": "No verified affiliated hospital is available for this doctor."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                hospital = primary_aff.hospital

            if not appt_date or not phone:
                return Response(
                    {"success": False, "error": "Appointment date and contact phone are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            appointment = Appointment.objects.create(
                user=user,
                doctor=doctor,
                hospital=hospital,
                appointment_date=appt_date,
                appointment_time=appt_time,
                reason_for_visit=reason,
                contact_phone=phone or "9999999999",
                status="requested",
            )

            return Response({
                "success": True,
                "message": f"Appointment requested with Dr. {doctor.name} at {hospital.name}.",
                "appointment_id": appointment.id,
                "appointment_date": str(appointment.appointment_date),
                "appointment_time": str(appointment.appointment_time),
            })
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SpecialtiesListAPIView(APIView):
    """List all active medical specialties."""

    def get(self, request):
        specialties = Specialty.objects.filter(is_active=True)
        serializer = SpecialtySerializer(specialties, many=True)
        return Response({"success": True, "specialties": serializer.data})
