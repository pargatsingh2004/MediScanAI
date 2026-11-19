from django.contrib import admin

from .backend.models import (
    Appointment,
    Doctor,
    DoctorQualification,
    DoctorRecommendation,
    EmailOTP,
    HealthcareProfile,
    Hospital,
    MedicalFinding,
    MedicalReport,
    MedicineReminder,
    NavigationHistory,
    NotificationPreference,
    ReportAnalysis,
    ReportChatMessage,
    SavedDoctor,
    SavedHospital,
    Specialty,
)


@admin.register(MedicalReport)
class MedicalReportAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "ocr_status", "created_at")
    list_filter = ("status", "ocr_status", "created_at")
    search_fields = ("title", "original_filename", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MedicineReminder)
class MedicineReminderAdmin(admin.ModelAdmin):
    list_display = ("medicine_name", "reminder_type", "user", "active", "email_notification")
    list_filter = ("reminder_type", "active", "email_notification")
    search_fields = ("medicine_name", "user__email")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "expires_at", "attempts", "consumed_at")
    list_filter = ("purpose", "consumed_at")
    readonly_fields = ("code_hash", "created_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "email_enabled", "updated_at")
    list_filter = ("email_enabled",)
    search_fields = ("user__email",)


admin.site.register(HealthcareProfile)
admin.site.register(Specialty)
admin.site.register(Hospital)
admin.site.register(Doctor)
admin.site.register(DoctorQualification)
admin.site.register(ReportAnalysis)
admin.site.register(MedicalFinding)
admin.site.register(DoctorRecommendation)
admin.site.register(Appointment)
admin.site.register(NavigationHistory)
admin.site.register(ReportChatMessage)
admin.site.register(SavedHospital)
admin.site.register(SavedDoctor)
