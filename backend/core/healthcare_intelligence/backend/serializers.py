from rest_framework import serializers
from django.urls import reverse
from .models import (
    HealthcareProfile,
    Specialty,
    Hospital,
    Doctor,
    DoctorQualification,
    DoctorHospital,
    MedicalReport,
    ReportAnalysis,
    MedicalFinding,
    DoctorRecommendation,
    HospitalRecommendation,
    UserLocation,
    NavigationHistory,
    Appointment,
)


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "name", "code", "description", "keywords", "icon_name", "is_active"]


class HospitalSerializer(serializers.ModelSerializer):
    specialties = SpecialtySerializer(many=True, read_only=True)
    distance_km = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = Hospital
        fields = [
            "id",
            "name",
            "place_id",
            "address",
            "latitude",
            "longitude",
            "phone",
            "email",
            "website",
            "rating",
            "reviews_count",
            "hospital_type",
            "emergency_services",
            "opening_hours",
            "specialties",
            "verified",
            "distance_km",
        ]


class DoctorQualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorQualification
        fields = ["id", "degree", "field_of_study", "institution", "year_completed", "verification_status"]


class DoctorHospitalSerializer(serializers.ModelSerializer):
    hospital_name = serializers.CharField(source="hospital.name", read_only=True)
    hospital_address = serializers.CharField(source="hospital.address", read_only=True)
    hospital_latitude = serializers.FloatField(source="hospital.latitude", read_only=True)
    hospital_longitude = serializers.FloatField(source="hospital.longitude", read_only=True)
    hospital_phone = serializers.CharField(source="hospital.phone", read_only=True)

    class Meta:
        model = DoctorHospital
        fields = [
            "id",
            "hospital",
            "hospital_name",
            "hospital_address",
            "hospital_latitude",
            "hospital_longitude",
            "hospital_phone",
            "designation",
            "department",
            "visiting_days",
            "consultation_timings",
            "room_number",
            "is_primary",
        ]


class DoctorSerializer(serializers.ModelSerializer):
    primary_specialty = SpecialtySerializer(read_only=True)
    secondary_specialties = SpecialtySerializer(many=True, read_only=True)
    qualifications = serializers.SerializerMethodField()
    hospital_affiliations = serializers.SerializerMethodField()
    distance_km = serializers.FloatField(read_only=True, required=False)
    match_score = serializers.FloatField(read_only=True, required=False)
    recommendation_reason = serializers.CharField(read_only=True, required=False)

    def get_qualifications(self, doctor):
        qualifications = doctor.qualifications.filter(verification_status="verified")
        return DoctorQualificationSerializer(qualifications, many=True).data

    def get_hospital_affiliations(self, doctor):
        affiliations = doctor.hospital_affiliations.filter(hospital__verified=True)
        return DoctorHospitalSerializer(affiliations, many=True).data

    class Meta:
        model = Doctor
        fields = [
            "id",
            "name",
            "profile_image",
            "registration_number",
            "registration_council",
            "primary_specialty",
            "secondary_specialties",
            "experience_years",
            "bio",
            "phone",
            "email",
            "consultation_fee",
            "rating",
            "reviews_count",
            "verified",
            "appointment_available",
            "qualifications",
            "hospital_affiliations",
            "distance_km",
            "match_score",
            "recommendation_reason",
        ]


class MedicalFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalFinding
        fields = [
            "id",
            "test_name",
            "metric_key",
            "measured_value",
            "numeric_value",
            "unit",
            "reference_range",
            "status",
            "severity",
            "clinical_significance",
        ]


class ReportAnalysisSerializer(serializers.ModelSerializer):
    findings = MedicalFindingSerializer(many=True, read_only=True)
    primary_specialty = SpecialtySerializer(read_only=True)
    relevant_specialties = SpecialtySerializer(many=True, read_only=True)

    class Meta:
        model = ReportAnalysis
        fields = [
            "id",
            "summary",
            "detected_conditions",
            "precautions",
            "suggested_questions",
            "overall_risk",
            "requires_urgent_care",
            "urgency_reason",
            "authenticity_hash",
            "confidence_score",
            "primary_specialty",
            "relevant_specialties",
            "findings",
            "created_at",
        ]


class MedicalReportSerializer(serializers.ModelSerializer):
    analysis = ReportAnalysisSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = MedicalReport
        fields = [
            "id",
            "title",
            "original_filename",
            "file_type",
            "file_size",
            "file_url",
            "ocr_status",
            "status",
            "report_date",
            "lab_name",
            "patient_name",
            "analysis",
            "created_at",
        ]

    def get_file_url(self, obj):
        if obj.file:
            return reverse("api_report_file", args=[obj.id])
        return None


class DoctorRecommendationSerializer(serializers.ModelSerializer):
    doctor = DoctorSerializer(read_only=True)
    specialty = SpecialtySerializer(read_only=True)

    class Meta:
        model = DoctorRecommendation
        fields = [
            "id",
            "report",
            "doctor",
            "specialty",
            "match_score",
            "relevance_score",
            "distance_km",
            "score_breakdown",
            "recommendation_reason",
            "priority",
            "created_at",
        ]


class HospitalRecommendationSerializer(serializers.ModelSerializer):
    hospital = HospitalSerializer(read_only=True)

    class Meta:
        model = HospitalRecommendation
        fields = [
            "id",
            "report",
            "hospital",
            "distance_km",
            "match_score",
            "recommendation_reason",
            "created_at",
        ]


class UserLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLocation
        fields = [
            "id",
            "latitude",
            "longitude",
            "address",
            "city",
            "state",
            "postal_code",
            "country",
            "accuracy_meters",
            "is_manual",
            "search_radius_meters",
            "timestamp",
        ]


class NavigationHistorySerializer(serializers.ModelSerializer):
    hospital_name = serializers.CharField(source="destination_hospital.name", read_only=True)

    class Meta:
        model = NavigationHistory
        fields = [
            "id",
            "destination_hospital",
            "hospital_name",
            "destination_doctor",
            "origin_latitude",
            "origin_longitude",
            "destination_latitude",
            "destination_longitude",
            "travel_mode",
            "distance_text",
            "distance_meters",
            "duration_text",
            "duration_seconds",
            "navigation_url",
            "started_at",
        ]


class AppointmentSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source="doctor.name", read_only=True)
    hospital_name = serializers.CharField(source="hospital.name", read_only=True)
    specialty_name = serializers.CharField(source="doctor.primary_specialty.name", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "doctor",
            "doctor_name",
            "hospital",
            "hospital_name",
            "specialty_name",
            "appointment_date",
            "appointment_time",
            "reason_for_visit",
            "status",
            "contact_phone",
            "notes",
            "created_at",
        ]
