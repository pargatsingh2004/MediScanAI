"""Django views and JSON endpoints for the vanilla HTML workspace."""

import json
import logging
import re
import csv
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import content_disposition_header, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
import requests

from .models import (
    Doctor, DoctorRecommendation, MedicalFinding, MedicalReport, MedicineReminder,
    ReportAnalysis, ReportChatMessage, Specialty, UserLocation, EmailOTP,
    SavedDoctor, SavedHospital, Hospital, NotificationPreference, HealthcareProfile,
)
from backend.authentication.services.otp_service import create_verification_otp, can_resend, verify_otp
from modules.authentication.backend.services.account_service import create_account, verify_email_code
from modules.chatbot.backend.services.chat_service import generate_reply, rewrite_reply
from modules.doctor_finder.backend.services.doctor_service import get_recommendations
from modules.hospital_finder.backend.services.hospital_service import haversine_distance, search_nearby_hospitals
from modules.health_trends.backend.services.trends_service import build_trends, iter_csv_rows as trend_csv_rows
from modules.maps_navigation.backend.services.navigation_service import calculate_route
from modules.medical_ocr.backend.services.ocr_service import extract_from_bytes, extract_from_path
from modules.reminders.backend.services.reminder_service import normalize_times
from modules.report_analysis.backend.services.analysis_service import (
    analyze_report,
    generate_comparison_summary,
)
from modules.report_comparison.backend.services.comparison_service import (
    build_comparison,
    iter_csv_rows as comparison_csv_rows,
)
from shared.email.email_service import send_notification
from .workspace_analysis import normalize_language

logger = logging.getLogger(__name__)
User = get_user_model()
ALLOWED_REPORT_TYPES = {"application/pdf", "image/jpeg", "image/jpg", "image/png"}
ALLOWED_REPORT_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _error(message, status=400, **extra):
    return JsonResponse({"error": str(message), **extra}, status=status)


def _user_or_error(request):
    if not request.user.is_authenticated:
        return None, _error("Sign in to continue.", 401, requiresAuth=True)
    return request.user, None


def _valid_report_file(file_obj):
    mime_type = (getattr(file_obj, "content_type", "") or "").lower()
    suffix = Path(file_obj.name).suffix.lower()
    return mime_type in ALLOWED_REPORT_TYPES or suffix in ALLOWED_REPORT_SUFFIXES


def _report_dict(report):
    return {
        "id": str(report.id),
        "user_id": str(report.user_id),
        "title": report.title or report.original_filename,
        "original_filename": report.original_filename,
        "mime_type": report.mime_type or "application/octet-stream",
        "file_url": reverse("api_report_file", args=[report.id]),
        "file_size": report.file_size,
        "storage_bucket": "django-media",
        "storage_path": report.file.name,
        "ocr_text": report.ocr_text or None,
        "ocr_raw_text": report.ocr_raw_text or None,
        "ocr_structured": report.ocr_structured or None,
        "ocr_engine": report.ocr_engine or None,
        "ocr_status": report.ocr_status,
        "analysis_json": report.analysis_json or None,
        "insights_json": report.insights_json or None,
        "report_status": report.status,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


def _report_detail(report):
    result = _report_dict(report)
    result["chat_messages"] = [
        {
            "id": str(item.id),
            "report_id": str(report.id),
            "user_id": str(item.user_id),
            "role": item.role,
            "message": item.message,
            "response_json": None,
            "created_at": item.created_at.isoformat(),
        }
        for item in report.chat_messages.filter(user=report.user)
    ]
    result["health_alerts"] = [
        {
            "id": f"{report.id}-{index}",
            "report_id": str(report.id),
            "alert_type": str(item.get("severity", "low")),
            "message": f'{item.get("title", "Report alert")}: {item.get("reason", "Review this finding with a clinician.")}',
            "created_at": report.updated_at.isoformat(),
        }
        for index, item in enumerate((report.insights_json or {}).get("alerts", []))
        if isinstance(item, dict)
    ]
    return result


def _reminder_dict(item):
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "report_id": str(item.report_id) if item.report_id else None,
        "reminderType": item.reminder_type,
        "medicine_name": item.medicine_name,
        "dosage": item.dosage or None,
        "schedule": item.schedule,
        "instructions": item.instructions or None,
        "reminder_times": item.reminder_times or [],
        "alarm_tone": item.alarm_tone,
        "active": item.active,
        "emailNotification": item.email_notification,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _navigation_url(origin_lat, origin_lng, dest_lat, dest_lng):
    return f"https://www.google.com/maps/dir/?api=1&origin={origin_lat},{origin_lng}&destination={dest_lat},{dest_lng}&travelmode=driving"


def _google_doctor_places(latitude, longitude, radius, specialty):
    api_key = settings.GOOGLE_PLACES_API_KEY or settings.GOOGLE_MAPS_API_KEY
    if not api_key or "your-google" in api_key:
        return []
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={
                "query": f"{specialty} doctor clinic" if specialty else "doctor clinic physician",
                "location": f"{latitude},{longitude}",
                "radius": radius,
                "key": api_key,
            },
            timeout=8,
        )
        response.raise_for_status()
        results = []
        for index, place in enumerate(response.json().get("results", [])):
            coordinates = (place.get("geometry") or {}).get("location") or {}
            dest_lat, dest_lng = coordinates.get("lat"), coordinates.get("lng")
            if dest_lat is None or dest_lng is None:
                continue
            results.append({
                "id": place.get("place_id") or f"google-doctor-{index}",
                "name": place.get("name", "Medical clinic"),
                "place_id": place.get("place_id", ""),
                "address": place.get("formatted_address") or place.get("vicinity", "Address available via Google Maps"),
                "latitude": dest_lat,
                "longitude": dest_lng,
                "rating": place.get("rating", 0),
                "reviews_count": place.get("user_ratings_total", 0),
                "distance_km": haversine_distance(latitude, longitude, dest_lat, dest_lng),
                "specialty": "Clinic or healthcare provider",
                "navigation_url": _navigation_url(latitude, longitude, dest_lat, dest_lng),
                "source": "google_places",
            })
        return sorted(results, key=lambda item: item["distance_km"])
    except Exception:
        logger.exception("Google Places doctor search failed")
        return []


def _osm_places(latitude, longitude, radius, kind, specialty=""):
    if kind == "doctors":
        clauses = (
            f'node["amenity"="doctors"](around:{radius},{latitude},{longitude});'
            f'node["amenity"="clinic"](around:{radius},{latitude},{longitude});'
            f'node["healthcare"="doctor"](around:{radius},{latitude},{longitude});'
            f'node["healthcare"="clinic"](around:{radius},{latitude},{longitude});'
        )
        generic_name = "Unnamed healthcare listing"
    else:
        clauses = (
            f'node["amenity"="hospital"](around:{radius},{latitude},{longitude});'
            f'way["amenity"="hospital"](around:{radius},{latitude},{longitude});'
            f'node["healthcare"="hospital"](around:{radius},{latitude},{longitude});'
        )
        generic_name = "Unnamed hospital listing"
    query = f"[out:json][timeout:8];({clauses});out center 25;"
    try:
        response = requests.get("https://overpass-api.de/api/interpreter", params={"data": query}, timeout=9)
        response.raise_for_status()
        results = []
        for place in response.json().get("elements", []):
            tags = place.get("tags") or {}
            center = place.get("center") or {}
            dest_lat = place.get("lat", center.get("lat"))
            dest_lng = place.get("lon", center.get("lon"))
            if dest_lat is None or dest_lng is None:
                continue
            address = ", ".join(filter(None, [tags.get("addr:street"), tags.get("addr:suburb"), tags.get("addr:city")]))
            results.append({
                "id": str(place.get("id", "")),
                "name": tags.get("name") or tags.get("name:en") or generic_name,
                "place_id": f"osm_{kind}_{place.get('id', '')}",
                "address": address or f"{dest_lat:.4f}, {dest_lng:.4f}",
                "latitude": dest_lat,
                "longitude": dest_lng,
                "rating": 0,
                "reviews_count": 0,
                "distance_km": haversine_distance(latitude, longitude, dest_lat, dest_lng),
                "specialty": "Clinic or healthcare provider" if kind == "doctors" else "",
                "hospital_type": "Hospital" if kind == "hospitals" else "",
                "phone": tags.get("phone") or tags.get("contact:phone", ""),
                "navigation_url": _navigation_url(latitude, longitude, dest_lat, dest_lng),
                "source": "live_osm",
            })
        return sorted(results, key=lambda item: item["distance_km"])
    except Exception:
        logger.exception("Live OpenStreetMap lookup failed")
        return []


def _persist_analysis(report, extracted, language):
    payload = analyze_report(
        extracted.get("cleaned_text", ""),
        raw_text=extracted.get("raw_text", ""),
        filename=report.original_filename,
        file_bytes=report.file.read() if report.file else b"",
        language=language,
    )
    report.file.seek(0)
    report.ocr_text = extracted.get("cleaned_text", "")
    report.ocr_raw_text = extracted.get("raw_text", "")
    report.ocr_engine = extracted.get("engine", "unknown")
    report.ocr_status = "completed" if extracted.get("success") else "failed"
    report.analysis_json = payload["analysis"]
    report.insights_json = payload["insights"]
    report.status = "analyzed" if extracted.get("success") else "failed"
    report.save()

    specialty = None
    if payload["specialties"]:
        specialty = Specialty.objects.filter(code=payload["specialties"][0]["code"]).first()
    analysis_record, _ = ReportAnalysis.objects.update_or_create(
        report=report,
        defaults={
            "summary": payload["summary"]["summary"],
            "detected_conditions": payload["summary"]["detected_conditions"],
            "precautions": payload["summary"]["precautions"],
            "suggested_questions": payload["summary"]["suggested_questions"],
            "overall_risk": payload["summary"]["overall_risk"],
            "requires_urgent_care": payload["summary"]["requires_urgent_care"],
            "urgency_reason": payload["summary"]["urgency_reason"],
            "authenticity_hash": extracted.get("sha256", ""),
            "confidence_score": payload["summary"]["confidence_score"],
            "primary_specialty": specialty,
        },
    )
    analysis_record.findings.all().delete()
    analysis_record.relevant_specialties.clear()
    for item in payload["findings"]:
        MedicalFinding.objects.create(
            analysis=analysis_record,
            test_name=item["test_name"],
            metric_key=item["metric_key"],
            measured_value=item["measured_value"],
            numeric_value=item["numeric_value"],
            unit=item["unit"],
            reference_range=item["reference_range"],
            status=item["status"],
            severity=item["severity"],
            clinical_significance=item["clinical_significance"],
        )
    codes = [item["code"] for item in payload["specialties"]]
    analysis_record.relevant_specialties.add(*Specialty.objects.filter(code__in=codes))
    return payload


def _read_upload(file_obj):
    pieces = []
    for chunk in file_obj.chunks():
        pieces.append(chunk)
    file_bytes = b"".join(pieces)
    file_obj.seek(0)
    return file_bytes


def _guest_payload(file_obj, language):
    file_bytes = _read_upload(file_obj)
    extracted = extract_from_bytes(file_bytes, file_obj.name, getattr(file_obj, "content_type", ""))
    if not extracted.get("cleaned_text", "").strip():
        raise ValueError("No readable report text was detected. Upload a clearer PDF or image.")
    payload = analyze_report(
        extracted["cleaned_text"],
        raw_text=extracted.get("raw_text", ""),
        filename=file_obj.name,
        file_bytes=file_bytes,
        language=language,
    )
    return extracted, payload


def _save_uploaded_report(request, file_obj, language):
    file_bytes = _read_upload(file_obj)
    if len(file_bytes) > getattr(settings, "MAX_REPORT_SIZE_BYTES", 20 * 1024 * 1024):
        raise ValueError("File size exceeds the configured upload limit.")
    report = MedicalReport(
        user=request.user,
        title=Path(file_obj.name).stem[:255],
        original_filename=Path(file_obj.name).name[:255],
        mime_type=getattr(file_obj, "content_type", "") or "application/octet-stream",
        file_type="pdf" if Path(file_obj.name).suffix.lower() == ".pdf" else "image",
        file_size=len(file_bytes),
        status="processing",
        ocr_status="processing",
    )
    report.file.save(Path(file_obj.name).name, ContentFile(file_bytes), save=False)
    report.save()
    try:
        extracted = extract_from_path(report.file.path, report.mime_type)
        if not extracted.get("cleaned_text", "").strip():
            raise ValueError("No readable report text was detected. Upload a clearer PDF or image.")
        payload = _persist_analysis(report, extracted, language)
        return report, extracted, payload
    except Exception:
        report.status = "failed"
        report.ocr_status = "failed"
        report.save(update_fields=["status", "ocr_status", "updated_at"])
        raise


def _registration_email(request, user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    confirm_url = request.build_absolute_uri(reverse("confirm_email", args=[uid, token]))
    record, otp = create_verification_otp(user, "verify_email")
    body = render_to_string("healthcare_intelligence/email_confirm.txt", {
        "user": user,
        "confirm_url": confirm_url,
        "otp": otp,
    })
    send_notification("Confirm your MediScan AI account", user.email, text_body=body)


@ensure_csrf_cookie
def landing_page(request):
    return render(request, "healthcare_intelligence/landing.html", {
        "is_signed_in": request.user.is_authenticated,
        "landing_specialties": ["Cardiology", "Endocrinology", "Nephrology", "Haematology", "Gastroenterology", "Neurology", "Oncology", "Pulmonology", "Orthopaedics", "Dermatology"],
    })


@ensure_csrf_cookie
def workspace_page(request):
    if not request.user.is_authenticated:
        return redirect(f"/login/?next=/workspace/")
    reports = MedicalReport.objects.filter(user=request.user).order_by("-created_at")[:100]
    return render(request, "healthcare_intelligence/workspace.html", {
        "reports": reports,
        "user": request.user,
        "specialties": Specialty.objects.filter(is_active=True),
        "max_report_size_mb": settings.MAX_REPORT_SIZE_MB,
    })


@ensure_csrf_cookie
def auth_page(request):
    mode = "signup" if request.path.rstrip("/").endswith("signup") else "login"
    return render(request, "healthcare_intelligence/auth.html", {
        "mode": mode,
        "confirmed": request.GET.get("confirmed") == "1",
        "reset": request.GET.get("reset") == "1",
        "next_url": request.GET.get("next", "/workspace/"),
    })


@ensure_csrf_cookie
def info_page(request, page):
    content = {
        "about": ("About MediScan AI", "MediScan AI helps people review medical reports in clearer language and prepare for conversations with healthcare professionals.", ["Read report text and recognized lab values.", "Keep reports and follow-up notes together in a private workspace.", "Find doctors, hospitals, routes, and appointment options." ]),
        "contact": ("Contact", "For project support, account questions, or accessibility feedback, contact the administrator of this MediScan AI deployment.", ["For medical questions, contact a licensed healthcare professional.", "For emergencies, contact local emergency services." ]),
        "privacy": ("Privacy", "Report files and workspace records are associated with the account that uploads them. The report preview on the home page is temporary and does not create a saved report record.", ["Only upload files you are authorized to share.", "Delete reports from your workspace when you no longer need them.", "If an AI provider key is configured, report text may be sent to that provider for analysis or assistant responses." ]),
        "terms": ("Terms of Use", "MediScan AI is an informational tool for understanding medical documents. It is not a medical device, diagnosis, or treatment service.", ["Review extracted values against the original report.", "Do not start, stop, or change treatment based only on an automated explanation.", "Consult a qualified clinician for decisions about your care." ]),
        "hipaa": ("Health Information and Security", "This deployment offers account-based access and private report records. Compliance requirements depend on the organization, hosting environment, and configuration operating the service.", ["Use a protected deployment and secure transport for real health records.", "Configure production email, database, storage, and access controls before inviting patients.", "This page does not certify a deployment as HIPAA compliant." ]),
    }
    title, intro, points = content[page]
    return render(request, "healthcare_intelligence/info_page.html", {"page": page, "page_title": title, "intro": intro, "points": points})


def confirm_email(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        return redirect("/login/?confirmed=1")
    return render(request, "healthcare_intelligence/email_invalid.html", status=400)


@require_http_methods(["POST"])
def auth_signup(request):
    data = _json_body(request)
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    full_name = str(data.get("fullName", "")).strip()
    if User.objects.filter(email__iexact=email).exists():
        return _error("This email is already registered. Log in or request another confirmation email.", 409)
    try:
        user = create_account(email=email, password=password, full_name=full_name)
        _registration_email(request, user)
    except ValidationError as exc:
        return _error(exc.messages[0] if getattr(exc, "messages", None) else "Unable to create this account.")
    except Exception:
        if "user" in locals():
            user.delete()
        logger.exception("Unable to send account confirmation email")
        return _error("We could not send the confirmation email. Check the email settings and try again.", 503)
    return JsonResponse({"message": "Signup received. Check your email to confirm your account before logging in.", "requiresEmailConfirmation": True})


@require_http_methods(["POST"])
def auth_login(request):
    data = _json_body(request)
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user_record = User.objects.filter(email__iexact=email).first()
    user = authenticate(request, username=user_record.username, password=password) if user_record else None
    if user_record and not user_record.is_active:
        return _error("Please confirm your email before logging in. Use resend verification if you need another email.", 403)
    if not user:
        return _error("Email or password is incorrect.", 401)
    login(request, user)
    return JsonResponse({"message": "Login successful.", "user": {"id": str(user.pk), "email": user.email, "full_name": user.get_full_name()}})


@require_http_methods(["POST"])
def auth_verify_otp(request):
    data = _json_body(request)
    email = str(data.get("email", "")).strip().lower()
    code = str(data.get("otp", data.get("code", ""))).strip()
    if not re.fullmatch(r"\d{6}", code):
        return _error("Enter the six-digit verification code.")
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return _error("The account could not be found.", 404)
    if not verify_email_code(user, code, "verify_email"):
        return _error("The verification code is invalid or expired.", 400)
    return JsonResponse({"message": "Email confirmed. You can sign in now.", "confirmed": True})


@require_http_methods(["POST"])
def auth_logout(request):
    logout(request)
    return JsonResponse({"message": "Signed out."})


@require_http_methods(["GET"])
def auth_session(request):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    user = request.user
    return JsonResponse({"profile": {"id": str(user.pk), "email": user.email, "full_name": user.get_full_name() or user.username}})


@require_http_methods(["POST"])
def auth_sync(request):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    return JsonResponse({"success": True, "profile": {"id": str(request.user.pk), "email": request.user.email, "full_name": request.user.get_full_name() or request.user.username}})


@require_http_methods(["GET", "PATCH"])
def auth_profile(request):
    user, error = _user_or_error(request)
    if error:
        return error
    profile, _ = HealthcareProfile.objects.get_or_create(user=user)
    if request.method == "PATCH":
        data = _json_body(request)
        if "fullName" in data:
            parts = str(data["fullName"]).strip().split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.save(update_fields=["first_name", "last_name"])
        field_aliases = {
            "dateOfBirth": "date_of_birth",
            "gender": "gender",
            "bloodGroup": "blood_group",
            "emergencyContactName": "emergency_contact_name",
            "emergencyContactPhone": "emergency_contact_phone",
            "locationAddress": "location_address",
            "preferredSearchRadius": "preferred_search_radius",
        }
        for request_field, field in field_aliases.items():
            if request_field not in data:
                continue
            setattr(profile, field, data[request_field])
        if data.get("latitude") is not None:
            profile.current_latitude = data["latitude"]
        if data.get("longitude") is not None:
            profile.current_longitude = data["longitude"]
        profile.save()
    return JsonResponse({"profile": {
        "id": str(user.pk),
        "email": user.email,
        "fullName": user.get_full_name(),
        "dateOfBirth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "gender": profile.gender,
        "bloodGroup": profile.blood_group,
        "emergencyContactName": profile.emergency_contact_name,
        "emergencyContactPhone": profile.emergency_contact_phone,
        "locationAddress": profile.location_address,
        "preferredSearchRadius": profile.preferred_search_radius,
        "latitude": profile.current_latitude,
        "longitude": profile.current_longitude,
    }})


@require_http_methods(["POST"])
def auth_resend(request):
    email = str(_json_body(request).get("email", "")).strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=False).first()
    if user:
        latest = EmailOTP.objects.filter(user=user, purpose="verify_email").order_by("-created_at").first()
        if latest and not can_resend(latest, cooldown_seconds=60):
            return _error("Please wait before requesting another verification code.", 429)
        try:
            _registration_email(request, user)
        except Exception:
            logger.exception("Unable to resend account confirmation email")
            return _error("Unable to send the confirmation email right now.", 503)
    return JsonResponse({"message": "If an unconfirmed account exists for this address, a confirmation email has been sent."})


@require_http_methods(["POST"])
def auth_password_reset(request):
    data = _json_body(request)
    email = str(data.get("email", "")).strip().lower()
    otp = str(data.get("otp", "")).strip()
    password = str(data.get("password", ""))
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user:
        if otp:
            if len(password) < 8:
                return _error("Password must be at least 8 characters long.")
            if not verify_otp(user, "password_reset", otp):
                return _error("The password reset code is invalid or expired.", 400)
            user.set_password(password)
            user.save(update_fields=["password"])
            return JsonResponse({"message": "Password updated. Sign in with your new password.", "reset": True})
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_url = request.build_absolute_uri(reverse("reset_password", args=[uid, token]))
        try:
            latest_reset = EmailOTP.objects.filter(user=user, purpose="password_reset").order_by("-created_at").first()
            if latest_reset and not can_resend(latest_reset, cooldown_seconds=60):
                return _error("Please wait before requesting another password reset code.", 429)
            record, reset_otp = EmailOTP.create_for_user(user, "password_reset")
            send_mail(
                "Reset your MediScan AI password",
                f"Use this six-digit code: {reset_otp}\nThe code expires after 10 minutes.\n\n"
                f"Or open this link to set a new password: {reset_url}",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Unable to send password reset email")
            return _error("Unable to send password reset instructions right now.", 503)
    return JsonResponse({"message": "If an account exists for that email, password reset instructions have been sent."})


@ensure_csrf_cookie
def reset_password(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if not user or not user.is_active or not default_token_generator.check_token(user, token):
        return render(request, "healthcare_intelligence/email_invalid.html", status=400)
    if request.method == "POST":
        password = request.POST.get("password", "")
        if len(password) >= 8:
            user.set_password(password)
            user.save(update_fields=["password"])
            return redirect("/login/?reset=1")
        return render(request, "healthcare_intelligence/reset_password.html", {"error": "Password must be at least 8 characters long."})
    return render(request, "healthcare_intelligence/reset_password.html")


@require_http_methods(["POST"])
def guest_report_preview(request):
    if request.COOKIES.get("mediscan_guest_preview") == "1":
        return _error("Your free report preview is already used. Create an account or sign in to analyze more reports.", 403, limitReached=True, requiresAuth=True)
    file_obj = request.FILES.get("file")
    if not file_obj:
        return _error("A file is required.")
    if not _valid_report_file(file_obj):
        return _error("Only JPG, PNG, and PDF files are supported.")
    if file_obj.size > getattr(settings, "MAX_REPORT_SIZE_BYTES", 20 * 1024 * 1024):
        return _error("File size exceeds the configured upload limit.")
    try:
        extracted, payload = _guest_payload(file_obj, request.POST.get("language", "en"))
    except ValueError as exc:
        return _error(str(exc), 422)
    except Exception:
        logger.exception("Guest report preview failed")
        return _error("Report preview failed. Please try a clearer PDF or image.", 500)
    preview = {
        "id": "guest-preview",
        "filename": file_obj.name,
        "createdAt": timezone.now().isoformat(),
        "extractedText": extracted.get("cleaned_text", ""),
        "analysis": payload["analysis"],
        "insights": payload["insights"],
    }
    response = JsonResponse({"success": True, "language": normalize_language(request.POST.get("language")), "preview": preview})
    response.set_cookie("mediscan_guest_preview", "1", max_age=60 * 60 * 24 * 120, httponly=True, samesite="Lax", secure=not settings.DEBUG)
    return response


@require_http_methods(["POST"])
def report_upload(request):
    user, error = _user_or_error(request)
    if error:
        return error
    file_obj = request.FILES.get("file")
    if not file_obj:
        return _error("A file is required.")
    if not _valid_report_file(file_obj):
        return _error("Only JPG, PNG, and PDF files are supported.")
    try:
        report, extracted, payload = _save_uploaded_report(request, file_obj, request.POST.get("language", "en"))
    except ValueError as exc:
        return _error(str(exc), 422)
    except Exception:
        logger.exception("Report processing failed")
        return _error("Report processing failed. Please try another clear PDF or image.", 500)
    return JsonResponse({
        "success": True,
        "language": normalize_language(request.POST.get("language")),
        "reportId": str(report.id),
        "filename": report.title or report.original_filename,
        "createdAt": report.created_at.isoformat(),
        "report": _report_dict(report),
        "extractedText": extracted.get("cleaned_text", ""),
        "analysis": payload["analysis"],
        "insights": payload["insights"],
    })


@require_http_methods(["GET"])
def report_history(request):
    user, error = _user_or_error(request)
    if error:
        return error
    reports = MedicalReport.objects.filter(user=user).order_by("-created_at")
    return JsonResponse({"reports": [_report_dict(item) for item in reports]})


@require_http_methods(["GET", "DELETE"])
def report_detail(request, report_id):
    user, error = _user_or_error(request)
    if error:
        return error
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    if request.method == "DELETE":
        if report.file:
            report.file.delete(save=False)
        report.delete()
        return JsonResponse({"message": "Report deleted."})
    return JsonResponse({"report": _report_detail(report)})


@require_http_methods(["GET"])
def report_file(request, report_id):
    user, error = _user_or_error(request)
    if error:
        return error
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    if not report.file:
        return _error("The original report file is unavailable.", 404)
    response = FileResponse(report.file.open("rb"), content_type=report.mime_type or "application/octet-stream")
    response["Content-Disposition"] = content_disposition_header(True, report.original_filename or "medical-report")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["POST"])
def report_ocr(request, report_id):
    user, error = _user_or_error(request)
    if error:
        return error
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    try:
        extracted = extract_from_path(report.file.path, report.mime_type)
        if not extracted.get("cleaned_text", "").strip():
            return _error("No readable text was detected in this report.", 422)
        payload = _persist_analysis(report, extracted, request.GET.get("language", "en"))
        return JsonResponse({"report": _report_detail(report), "ocr": {"text": report.ocr_text, "rawText": report.ocr_raw_text, "engine": report.ocr_engine}, "analysis": payload["analysis"], "insights": payload["insights"]})
    except Exception:
        logger.exception("Report OCR refresh failed")
        return _error("Unable to reprocess this report.", 500)


@require_http_methods(["GET"])
def report_insights(request, report_id):
    user, error = _user_or_error(request)
    if error:
        return error
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    return JsonResponse({"reportId": str(report.id), "insights": report.insights_json or {}, "analysis": report.analysis_json or {}})


@require_http_methods(["POST"])
def report_explanation(request, report_id):
    user, error = _user_or_error(request)
    if error:
        return error
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    data = _json_body(request)
    request_text = str(data.get("message", data.get("question", ""))).strip()
    if not request_text:
        return _error("A question or report phrase is required.")
    answer = generate_reply(request_text, report, report.chat_messages.filter(user=user).values_list("message", flat=True), (report.insights_json or {}).get("preferredLanguage", "en"))
    return JsonResponse({"reply": answer, "explanation": answer})


@require_http_methods(["POST"])
def report_compare(request):
    user, error = _user_or_error(request)
    if error:
        return error
    data = _json_body(request)
    report_ids = list(dict.fromkeys(str(item).strip() for item in data.get("reportIds", []) if str(item).strip())) if isinstance(data.get("reportIds"), list) else []
    if len(report_ids) < 2:
        return _error("Select at least two reports to compare.")
    if len(report_ids) > 6:
        return _error("You can compare up to six reports at a time.")
    reports_by_id = {
        str(item.id): item
        for item in MedicalReport.objects.filter(user=user, id__in=report_ids)
        .select_related("analysis")
        .prefetch_related("analysis__findings")
    }
    reports = sorted(
        (reports_by_id[item] for item in report_ids if item in reports_by_id),
        key=lambda item: item.created_at,
    )
    if len(reports) < 2:
        return _error("The selected reports are not available for comparison.", 404)
    comparison = build_comparison(reports)
    ai_comparison = generate_comparison_summary(
        comparison["reports"], comparison["metrics"], data.get("language", "en")
    )
    return JsonResponse({"comparison": comparison, "aiComparison": ai_comparison, "diagnostics": {"requestedReportIds": report_ids, "selectedReportIds": [str(item.id) for item in reports], "missingReportIds": [item for item in report_ids if item not in reports_by_id]}})


@require_http_methods(["POST"])
def report_chat(request):
    user, error = _user_or_error(request)
    if error:
        return error
    data = _json_body(request)
    report_id = str(data.get("reportId", "")).strip()
    question = str(data.get("message", data.get("question", ""))).strip()
    if not report_id or not question:
        return _error("reportId and message are required.")
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    history = list(report.chat_messages.filter(user=user).order_by("created_at").values_list("message", flat=True))
    ReportChatMessage.objects.create(user=user, report=report, role="user", message=question)
    reply = generate_reply(question, report, history, (report.insights_json or {}).get("preferredLanguage", "en"))
    ReportChatMessage.objects.create(user=user, report=report, role="assistant", message=reply)
    messages = [
        {"id": str(item.id), "report_id": str(report.id), "user_id": str(user.pk), "role": item.role, "message": item.message, "response_json": None, "created_at": item.created_at.isoformat()}
        for item in report.chat_messages.filter(user=user)
    ]
    return JsonResponse({"message": "Chat response generated.", "reply": reply, "messages": messages})


@require_http_methods(["POST"])
def chat_humanize(request):
    user, error = _user_or_error(request)
    if error:
        return error
    data = _json_body(request)
    report_id = str(data.get("reportId", "")).strip()
    message = str(data.get("message", "")).strip()
    if not report_id or not message:
        return _error("reportId and message are required.")
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    return JsonResponse({"message": "Assistant reply rewritten.", "reply": rewrite_reply(message, (report.insights_json or {}).get("preferredLanguage", "en"))})


@require_http_methods(["GET", "POST"])
def medicine_reminders(request):
    user, error = _user_or_error(request)
    if error:
        return error
    if request.method == "GET":
        reminders = MedicineReminder.objects.filter(user=user)
        report_id = request.GET.get("reportId")
        if report_id:
            reminders = reminders.filter(report_id=report_id)
        return JsonResponse({"reminders": [_reminder_dict(item) for item in reminders]})
    data = _json_body(request)
    name = str(data.get("medicineName", "")).strip()
    schedule = str(data.get("schedule", "")).strip()
    times = data.get("reminderTimes", [])
    if not name or not schedule or not isinstance(times, list) or not times:
        return _error("Medicine name, schedule, and at least one reminder time are required.")
    try:
        normalized = normalize_times(times)
    except ValueError as exc:
        return _error(str(exc))
    report = None
    if data.get("reportId"):
        report = get_object_or_404(MedicalReport, id=data["reportId"], user=user)
    tone = data.get("alarmTone", "default")
    if tone not in {"default", "soft", "beep", "alert"}:
        tone = "default"
    reminder_type = str(data.get("reminderType", "medicine"))
    if reminder_type not in {"medicine", "appointment", "test", "follow_up"}:
        reminder_type = "medicine"
    item = MedicineReminder.objects.create(
        user=user,
        report=report,
        reminder_type=reminder_type,
        medicine_name=name,
        dosage=str(data.get("dosage", "") or ""),
        schedule=schedule,
        instructions=str(data.get("instructions", "") or ""),
        reminder_times=normalized,
        alarm_tone=tone,
        active=bool(data.get("active", True)),
        email_notification=bool(data.get("emailNotification", True)),
    )
    return JsonResponse({"message": "Reminder created.", "reminder": _reminder_dict(item)}, status=201)


@require_http_methods(["PATCH", "DELETE"])
def medicine_reminder_detail(request, reminder_id):
    user, error = _user_or_error(request)
    if error:
        return error
    item = get_object_or_404(MedicineReminder, id=reminder_id, user=user)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"message": "Reminder deleted."})
    data = _json_body(request)
    for key, field in (
        ("medicineName", "medicine_name"),
        ("dosage", "dosage"),
        ("schedule", "schedule"),
        ("instructions", "instructions"),
        ("active", "active"),
        ("alarmTone", "alarm_tone"),
        ("emailNotification", "email_notification"),
    ):
        if key in data:
            setattr(item, field, data[key])
    if "reminderTimes" in data:
        try:
            item.reminder_times = normalize_times(data["reminderTimes"])
        except ValueError as exc:
            return _error(str(exc))
    if "reminderType" in data:
        reminder_type = str(data["reminderType"])
        if reminder_type not in {"medicine", "appointment", "test", "follow_up"}:
            return _error("Invalid reminder type.")
        item.reminder_type = reminder_type
    if item.alarm_tone not in {"default", "soft", "beep", "alert"}:
        item.alarm_tone = "default"
    item.save()
    return JsonResponse({"reminder": _reminder_dict(item)})


@require_http_methods(["GET", "PATCH"])
def notification_preferences(request):
    user, error = _user_or_error(request)
    if error:
        return error
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    if request.method == "PATCH":
        data = _json_body(request)
        allowed = [
            "email_enabled", "report_analysis", "ocr_completed", "health_trends",
            "report_comparison", "chatbot_summary", "reminders",
            "hospital_information", "doctor_information", "maps_information",
        ]
        for field in allowed:
            if field in data:
                setattr(preference, field, bool(data[field]))
        preference.save()
    return JsonResponse({"preferences": {
        field: getattr(preference, field)
        for field in [
            "email_enabled", "report_analysis", "ocr_completed", "health_trends",
            "report_comparison", "chatbot_summary", "reminders",
            "hospital_information", "doctor_information", "maps_information",
        ]
    }})


@require_http_methods(["GET", "POST", "DELETE"])
def favorite_hospitals(request):
    user, error = _user_or_error(request)
    if error:
        return error
    if request.method == "GET":
        saved = SavedHospital.objects.filter(user=user).select_related("hospital")
        return JsonResponse({"hospitals": [
            {
                "id": item.hospital.id,
                "name": item.hospital.name,
                "address": item.hospital.address,
                "phone": item.hospital.phone,
                "latitude": item.hospital.latitude,
                "longitude": item.hospital.longitude,
                "savedAt": item.created_at.isoformat(),
            }
            for item in saved
        ]})
    data = _json_body(request)
    hospital_id = data.get("hospitalId")
    if not hospital_id:
        return _error("hospitalId is required.")
    hospital = get_object_or_404(Hospital, id=hospital_id)
    if request.method == "DELETE":
        SavedHospital.objects.filter(user=user, hospital=hospital).delete()
        return JsonResponse({"saved": False})
    saved, _ = SavedHospital.objects.get_or_create(user=user, hospital=hospital)
    return JsonResponse({"saved": True, "savedAt": saved.created_at.isoformat()}, status=201)


@require_http_methods(["GET", "POST", "DELETE"])
def favorite_doctors(request):
    user, error = _user_or_error(request)
    if error:
        return error
    if request.method == "GET":
        saved = SavedDoctor.objects.filter(user=user).select_related("doctor", "doctor__primary_specialty")
        return JsonResponse({"doctors": [
            {
                "id": item.doctor.id,
                "name": item.doctor.name,
                "specialty": item.doctor.primary_specialty.name,
                "phone": item.doctor.phone,
                "savedAt": item.created_at.isoformat(),
            }
            for item in saved
        ]})
    data = _json_body(request)
    doctor_id = data.get("doctorId")
    if not doctor_id:
        return _error("doctorId is required.")
    doctor = get_object_or_404(Doctor, id=doctor_id)
    if request.method == "DELETE":
        SavedDoctor.objects.filter(user=user, doctor=doctor).delete()
        return JsonResponse({"saved": False})
    saved, _ = SavedDoctor.objects.get_or_create(user=user, doctor=doctor)
    return JsonResponse({"saved": True, "savedAt": saved.created_at.isoformat()}, status=201)


@require_http_methods(["GET"])
def health_trends(request):
    user, error = _user_or_error(request)
    if error:
        return error
    return JsonResponse(build_trends(user))


@require_http_methods(["GET"])
def health_trends_export(request):
    user, error = _user_or_error(request)
    if error:
        return error
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="mediscan-health-trends.csv"'
    writer = csv.writer(response)
    writer.writerow(["metric", "report", "date", "value", "unit", "status"])
    writer.writerows(trend_csv_rows(user))
    return response


@require_http_methods(["GET"])
def report_comparison_export(request):
    user, error = _user_or_error(request)
    if error:
        return error
    report_ids = [
        item.strip()
        for item in request.GET.get("reportIds", "").split(",")
        if item.strip()
    ]
    if len(report_ids) < 2:
        return _error("Select at least two reports.")
    reports = list(
        MedicalReport.objects.filter(user=user, id__in=report_ids)
        .select_related("analysis")
        .prefetch_related("analysis__findings")
        .order_by("created_at")
    )
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="mediscan-report-comparison.csv"'
    writer = csv.writer(response)
    writer.writerow(["metric", "report", "date", "value", "unit", "reference_range", "status"])
    writer.writerows(comparison_csv_rows(reports))
    return response


@require_http_methods(["GET"])
def report_confidence(request):
    user, error = _user_or_error(request)
    if error:
        return error
    report_id = request.GET.get("reportId", "").strip()
    if not report_id:
        return _error("reportId is required.")
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    analysis_score = report.analysis.confidence_score if hasattr(report, "analysis") else 0
    ocr_score = 90 if report.ocr_status == "completed" and report.ocr_text else 25
    overall = round((ocr_score * 0.4) + (analysis_score * 0.6))
    def score(value, reason):
        level = "high" if value >= 80 else "medium" if value >= 55 else "low"
        return {"level": level, "score": value, "reasons": [reason]}
    confidence = {"reportId": str(report.id), "ocr": score(ocr_score, "Text was extracted from the uploaded document." if ocr_score > 50 else "OCR could not extract enough text."), "analysis": score(round(analysis_score), "Clinical values were compared with the local reference catalogue."), "overall": score(overall, "Combined OCR and analysis confidence.")}
    return JsonResponse({"reportId": str(report.id), "confidence": confidence, "storedConfidence": None})


@require_http_methods(["GET", "POST"])
def doctor_recommendations(request):
    user, error = _user_or_error(request)
    if error:
        return error
    if request.method == "GET":
        report_id = request.GET.get("reportId", "").strip()
    else:
        report_id = str(_json_body(request).get("reportId", "")).strip()
    if not report_id:
        return _error("Select a report to get doctor recommendations.")
    report = get_object_or_404(MedicalReport, id=report_id, user=user)
    codes = []
    if hasattr(report, "analysis"):
        codes = list(report.analysis.relevant_specialties.values_list("code", flat=True))
    if not codes:
        codes = ["general_medicine"]
    location = UserLocation.objects.filter(user=user).first()
    doctors = get_recommendations(
        codes,
        location.latitude if location else None,
        location.longitude if location else None,
        limit=12,
    )
    return JsonResponse({"reportId": str(report.id), "recommendations": [{key: value for key, value in item.items() if key != "_doctor"} for item in doctors]})


@require_http_methods(["GET"])
def nearby_places(request, kind):
    try:
        latitude = float(request.GET.get("lat", request.GET.get("latitude", "28.5367")))
        longitude = float(request.GET.get("lng", request.GET.get("longitude", "77.2882")))
        radius = min(max(int(request.GET.get("radius", request.GET.get("radius_meters", "10000"))), 100), 50000)
        if kind == "hospitals":
            items = search_nearby_hospitals(latitude, longitude, radius)
            items = [item for item in items if item.get("distance_km", radius / 1000 + 1) <= radius / 1000]
            if not items:
                items = _osm_places(latitude, longitude, min(radius, 25000), "hospitals")
            key = "hospitals"
        else:
            specialty = request.GET.get("specialty", "")
            codes = [specialty] if specialty else ["general_medicine"]
            local_items = get_recommendations(codes, latitude, longitude, limit=20)
            local_items = [{key: value for key, value in item.items() if key != "_doctor"} for item in local_items]
            local_items = [item for item in local_items if item.get("distance_km", radius / 1000 + 1) <= radius / 1000]
            live_items = _google_doctor_places(latitude, longitude, radius, specialty)
            if not live_items:
                live_items = _osm_places(latitude, longitude, min(radius, 20000), "doctors", specialty)
            items = live_items + local_items
            seen = set()
            unique_items = []
            for item in items:
                place_key = item.get("place_id") or item.get("name", "").lower()
                if place_key in seen:
                    continue
                seen.add(place_key)
                unique_items.append(item)
            items = unique_items
            key = "doctors"
        return JsonResponse({"success": True, "total_found": len(items), key: items})
    except (TypeError, ValueError):
        return _error("Latitude, longitude, and search radius must be valid numbers.")
    except Exception:
        logger.exception("Nearby %s lookup failed", kind)
        return _error(f"Failed to search {kind}.", 500)


@require_http_methods(["POST"])
def route_preview(request):
    data = _json_body(request)
    try:
        origin_lat = float(data["origin_lat"])
        origin_lng = float(data["origin_lng"])
        dest_lat = float(data["destination_lat"])
        dest_lng = float(data["destination_lng"])
    except (KeyError, TypeError, ValueError):
        return _error("Origin and destination coordinates are required.")
    travel_mode = str(data.get("travel_mode", "DRIVING")).upper()
    if travel_mode not in {"DRIVING", "WALKING", "TRANSIT"}:
        travel_mode = "DRIVING"
    try:
        route = calculate_route(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode.lower())
    except ValueError as exc:
        return _error(str(exc))
    return JsonResponse({
        "success": True,
        "route": {
            "distance_text": route["distance_text"],
            "distance_meters": route["distance_meters"],
            "duration_text": route["duration_text"],
            "duration_seconds": route["duration_seconds"],
            "navigation_url": route["navigation_url"],
            "travel_mode": travel_mode,
        },
    })
