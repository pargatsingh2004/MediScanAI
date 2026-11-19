import uuid
import hashlib
import secrets
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class EmailOTP(models.Model):
    """Short-lived hashed email verification code."""
    PURPOSE_CHOICES = [
        ("verify_email", "Verify email"),
        ("password_reset", "Password reset"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_otps")
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(default=timezone.now)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "created_at"]),
        ]

    @classmethod
    def hash_code(cls, code):
        return hashlib.sha256(str(code).encode("utf-8")).hexdigest()

    @classmethod
    def create_for_user(cls, user, purpose="verify_email", lifetime_minutes=10):
        cls.objects.filter(user=user, purpose=purpose, consumed_at__isnull=True).update(consumed_at=timezone.now())
        code = f"{secrets.randbelow(1000000):06d}"
        record = cls.objects.create(
            user=user,
            purpose=purpose,
            code_hash=cls.hash_code(code),
            expires_at=timezone.now() + timedelta(minutes=lifetime_minutes),
        )
        return record, code

    def is_valid(self, code):
        if self.consumed_at is not None:
            return False
        if timezone.now() >= self.expires_at:
            return False
        if self.attempts >= 5:
            return False
        return secrets.compare_digest(self.code_hash, self.hash_code(code))

    def __str__(self):
        return f"{self.purpose} OTP for {self.user.email}"


class NotificationPreference(models.Model):
    """Central per-user consent for optional email notifications."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    email_enabled = models.BooleanField(default=False)
    report_analysis = models.BooleanField(default=True)
    ocr_completed = models.BooleanField(default=True)
    health_trends = models.BooleanField(default=True)
    report_comparison = models.BooleanField(default=True)
    chatbot_summary = models.BooleanField(default=False)
    reminders = models.BooleanField(default=True)
    hospital_information = models.BooleanField(default=True)
    doctor_information = models.BooleanField(default=True)
    maps_information = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class HealthcareProfile(models.Model):
    """Healthcare details attached to each user."""
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("prefer_not_to_say", "Prefer not to say"),
    ]
    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"), ("A-", "A-"),
        ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"),
        ("O+", "O+"), ("O-", "O-"),
        ("unknown", "Unknown"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="healthcare_profile",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="prefer_not_to_say")
    blood_group = models.CharField(max_length=10, choices=BLOOD_GROUP_CHOICES, default="unknown")
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=25, blank=True)
    current_latitude = models.FloatField(null=True, blank=True)
    current_longitude = models.FloatField(null=True, blank=True)
    location_address = models.CharField(max_length=255, blank=True)
    preferred_search_radius = models.IntegerField(default=10000, help_text="Search radius in meters")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"HealthcareProfile({self.user.username})"


class Specialty(models.Model):
    """Medical specialty classifications."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    keywords = models.JSONField(default=list, help_text="Keywords mapping to this specialty")
    icon_name = models.CharField(max_length=50, default="stethoscope")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Specialties"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Hospital(models.Model):
    """Verified hospital and healthcare facility details."""
    HOSPITAL_TYPE_CHOICES = [
        ("General", "General Hospital"),
        ("Multi-Specialty", "Multi-Specialty Hospital"),
        ("Super-Specialty", "Super-Specialty Hospital"),
        ("Clinic", "Clinic / Health Center"),
        ("Government", "Government Hospital"),
        ("Private", "Private Hospital"),
    ]

    name = models.CharField(max_length=200, db_index=True)
    place_id = models.CharField(max_length=200, blank=True, null=True, unique=True)
    address = models.TextField()
    latitude = models.FloatField(db_index=True)
    longitude = models.FloatField(db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    rating = models.FloatField(default=0.0)
    reviews_count = models.IntegerField(default=0)
    hospital_type = models.CharField(max_length=50, choices=HOSPITAL_TYPE_CHOICES, default="Multi-Specialty")
    emergency_services = models.BooleanField(default=False)
    opening_hours = models.JSONField(default=dict, blank=True)
    specialties = models.ManyToManyField(Specialty, related_name="hospitals", blank=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-rating", "name"]

    def __str__(self):
        return f"{self.name} ({self.hospital_type})"


class Doctor(models.Model):
    """Verified medical practitioners."""
    name = models.CharField(max_length=150, db_index=True)
    profile_image = models.CharField(max_length=500, blank=True, default="/static/img/doctor-placeholder.svg")
    registration_number = models.CharField(max_length=80, blank=True, help_text="Medical Council Registration ID")
    registration_council = models.CharField(max_length=150, blank=True)
    primary_specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name="doctors")
    secondary_specialties = models.ManyToManyField(Specialty, related_name="secondary_doctors", blank=True)
    experience_years = models.PositiveIntegerField(default=1)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=500.00)
    rating = models.FloatField(default=0.0)
    reviews_count = models.IntegerField(default=0)
    verified = models.BooleanField(default=False)
    appointment_available = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-rating", "-experience_years", "name"]

    def __str__(self):
        return f"Dr. {self.name} - {self.primary_specialty.name}"


class DoctorQualification(models.Model):
    """Verified educational credentials and medical degrees."""
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="qualifications")
    degree = models.CharField(max_length=100)  # MBBS, MD, DM, MS, DNB
    field_of_study = models.CharField(max_length=150, blank=True)
    institution = models.CharField(max_length=200)
    year_completed = models.PositiveIntegerField()
    verification_status = models.CharField(
        max_length=30,
        choices=[("verified", "Verified"), ("pending", "Pending Verification")],
        default="pending",
    )

    def __str__(self):
        return f"{self.degree} - {self.doctor.name}"


class DoctorHospital(models.Model):
    """Affiliation bridge between doctors and hospitals."""
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="hospital_affiliations")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="affiliated_doctors")
    designation = models.CharField(max_length=120, default="Consultant")
    department = models.CharField(max_length=120, blank=True)
    visiting_days = models.JSONField(default=list, blank=True)
    consultation_timings = models.CharField(max_length=100, default="10:00 AM - 02:00 PM")
    room_number = models.CharField(max_length=50, blank=True)
    is_primary = models.BooleanField(default=True)

    class Meta:
        unique_together = ("doctor", "hospital")

    def __str__(self):
        return f"Dr. {self.doctor.name} at {self.hospital.name}"


class MedicalReport(models.Model):
    """Uploaded medical documents and processing status."""
    FILE_TYPE_CHOICES = [
        ("pdf", "PDF Document"),
        ("image", "Image (JPG/PNG)"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("analyzed", "Analysis Complete"),
        ("failed", "Analysis Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    title = models.CharField(max_length=255, blank=True)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="reports/%Y/%m/")
    mime_type = models.CharField(max_length=120, blank=True)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default="pdf")
    file_size = models.BigIntegerField(default=0)
    ocr_text = models.TextField(blank=True)
    ocr_raw_text = models.TextField(blank=True)
    ocr_engine = models.CharField(max_length=80, blank=True)
    ocr_structured = models.JSONField(default=dict, blank=True)
    ocr_status = models.CharField(max_length=20, default="pending")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    analysis_json = models.JSONField(default=dict, blank=True)
    insights_json = models.JSONField(default=dict, blank=True)
    report_date = models.DateField(null=True, blank=True)
    lab_name = models.CharField(max_length=200, blank=True)
    patient_name = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or self.original_filename


class ReportAnalysis(models.Model):
    """Clinical analysis, findings, and risk classifications."""
    RISK_LEVEL_CHOICES = [
        ("low", "Low Risk"),
        ("moderate", "Moderate Risk"),
        ("high", "High Risk"),
        ("critical", "Critical"),
    ]

    report = models.OneToOneField(MedicalReport, on_delete=models.CASCADE, related_name="analysis")
    summary = models.TextField(blank=True)
    detected_conditions = models.JSONField(default=list, blank=True)
    precautions = models.JSONField(default=list, blank=True)
    suggested_questions = models.JSONField(default=list, blank=True)
    overall_risk = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default="low")
    requires_urgent_care = models.BooleanField(default=False)
    urgency_reason = models.TextField(blank=True)
    authenticity_hash = models.CharField(max_length=128, blank=True)
    confidence_score = models.FloatField(default=85.0)
    primary_specialty = models.ForeignKey(
        Specialty, on_delete=models.SET_NULL, null=True, blank=True, related_name="matched_analyses"
    )
    relevant_specialties = models.ManyToManyField(Specialty, related_name="analyses", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Analysis for {self.report.original_filename} ({self.overall_risk})"


class MedicalFinding(models.Model):
    """Individual biomarker and laboratory test findings."""
    STATUS_CHOICES = [
        ("normal", "Normal"),
        ("high", "High"),
        ("low", "Low"),
        ("abnormal", "Abnormal"),
        ("critical", "Critical"),
    ]
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("moderate", "Moderate"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    analysis = models.ForeignKey(ReportAnalysis, on_delete=models.CASCADE, related_name="findings")
    test_name = models.CharField(max_length=150)
    metric_key = models.CharField(max_length=100, blank=True)
    measured_value = models.CharField(max_length=80)
    numeric_value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=40, blank=True)
    reference_range = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="normal")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="low")
    clinical_significance = models.TextField(blank=True)

    class Meta:
        ordering = ["-severity", "test_name"]

    def __str__(self):
        return f"{self.test_name}: {self.measured_value} {self.unit} ({self.status})"


class DoctorRecommendation(models.Model):
    """Ranked doctor recommendations computed for a user / report."""
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("moderate", "Moderate"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_recommendations")
    report = models.ForeignKey(MedicalReport, on_delete=models.SET_NULL, null=True, blank=True, related_name="doctor_recommendations")
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="recommendations")
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE)
    match_score = models.FloatField(default=0.0, help_text="Total weighted score 0-100")
    relevance_score = models.FloatField(default=0.0)
    distance_km = models.FloatField(null=True, blank=True)
    score_breakdown = models.JSONField(default=dict, blank=True)
    recommendation_reason = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="moderate")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-match_score", "distance_km"]

    def __str__(self):
        return f"Rec: Dr. {self.doctor.name} for {self.user.username} ({self.match_score}%)"


class HospitalRecommendation(models.Model):
    """Ranked hospital recommendations computed for a user / report."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hospital_recommendations")
    report = models.ForeignKey(MedicalReport, on_delete=models.SET_NULL, null=True, blank=True, related_name="hospital_recommendations")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="recommendations")
    distance_km = models.FloatField()
    match_score = models.FloatField(default=0.0)
    recommendation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["distance_km", "-match_score"]

    def __str__(self):
        return f"Rec: {self.hospital.name} ({self.distance_km} km)"


class UserLocation(models.Model):
    """User geolocation log and search coordinate history."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="locations")
    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=80, blank=True)
    accuracy_meters = models.FloatField(null=True, blank=True)
    is_manual = models.BooleanField(default=False)
    search_radius_meters = models.IntegerField(default=10000)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user.username} at ({self.latitude}, {self.longitude})"


class NavigationHistory(models.Model):
    """Tracks route directions and Google Maps navigation events."""
    TRAVEL_MODE_CHOICES = [
        ("DRIVING", "Driving"),
        ("WALKING", "Walking"),
        ("TRANSIT", "Transit"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="navigations")
    destination_hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="navigations")
    destination_doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    origin_latitude = models.FloatField()
    origin_longitude = models.FloatField()
    destination_latitude = models.FloatField()
    destination_longitude = models.FloatField()
    travel_mode = models.CharField(max_length=20, choices=TRAVEL_MODE_CHOICES, default="DRIVING")
    distance_text = models.CharField(max_length=50, blank=True)
    distance_meters = models.IntegerField(null=True, blank=True)
    duration_text = models.CharField(max_length=50, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    navigation_url = models.URLField(max_length=500)
    started_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Navigation to {self.destination_hospital.name} ({self.started_at})"


class Appointment(models.Model):
    """Appointments booked by users with doctors and hospitals."""
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="appointments")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="appointments")
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    reason_for_visit = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    contact_phone = models.CharField(max_length=30)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-appointment_date", "-appointment_time"]

    def __str__(self):
        return f"Appt: {self.user.username} with Dr. {self.doctor.name} on {self.appointment_date}"


class ReportChatMessage(models.Model):
    """Private assistant conversation attached to a user's medical report."""
    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="report_chat_messages")
    report = models.ForeignKey(MedicalReport, on_delete=models.CASCADE, related_name="chat_messages")
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.role}: {self.report.original_filename}"


class MedicineReminder(models.Model):
    """User managed medicine schedule and browser alarm preferences."""
    REMINDER_TYPE_CHOICES = [
        ("medicine", "Medicine"),
        ("appointment", "Appointment"),
        ("test", "Medical test"),
        ("follow_up", "Follow-up"),
    ]
    ALARM_TONE_CHOICES = [
        ("default", "Default"),
        ("soft", "Soft"),
        ("beep", "Beep"),
        ("alert", "Alert"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="medicine_reminders")
    report = models.ForeignKey(MedicalReport, on_delete=models.SET_NULL, null=True, blank=True, related_name="reminders")
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE_CHOICES, default="medicine")
    medicine_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=255, blank=True)
    schedule = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    reminder_times = models.JSONField(default=list, blank=True)
    alarm_tone = models.CharField(max_length=16, choices=ALARM_TONE_CHOICES, default="default")
    active = models.BooleanField(default=True)
    email_notification = models.BooleanField(default=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-active", "-created_at"]

    def __str__(self):
        return f"{self.medicine_name} reminder for {self.user}"


class SavedHospital(models.Model):
    """Hospital entries saved by an authenticated user."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_hospitals")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="saved_by_users")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "hospital")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} saved {self.hospital.name}"


class SavedDoctor(models.Model):
    """Doctor entries saved by an authenticated user."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_doctors")
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="saved_by_users")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "doctor")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} saved Dr. {self.doctor.name}"
