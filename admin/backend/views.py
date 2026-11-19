"""Staff-only operational overview for the MediScan AI Django admin."""

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.shortcuts import render

from backend.core.healthcare_intelligence.backend.models import (
    Appointment,
    Doctor,
    Hospital,
    MedicalReport,
    MedicineReminder,
    Specialty,
)


@staff_member_required(login_url="admin:login")
def dashboard(request):
    """Show aggregate system status and recent report processing state."""
    reports = MedicalReport.objects.select_related("user").order_by("-created_at")
    context = {
        "title": "MediScan AI operations",
        "counts": {
            "reports": MedicalReport.objects.count(),
            "doctors": Doctor.objects.filter(verified=True).count(),
            "hospitals": Hospital.objects.filter(verified=True).count(),
            "specialties": Specialty.objects.filter(is_active=True).count(),
            "active_reminders": MedicineReminder.objects.filter(active=True).count(),
            "open_appointments": Appointment.objects.filter(status__in=("requested", "confirmed")).count(),
        },
        "report_statuses": list(
            MedicalReport.objects.values("status").annotate(total=Count("id")).order_by("status")
        ),
        "recent_reports": reports[:10],
    }
    return render(request, "admin/healthcare_dashboard.html", context)
