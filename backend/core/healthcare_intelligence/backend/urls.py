from django.urls import path
from .views import (
    healthcare_dashboard_view,
    nearby_hospitals_view,
    find_doctors_view,
    doctor_profile_view,
    hospital_details_view,
    report_analysis_view,
    map_navigation_view,
    UpdateLocationAPIView,
    NearbyHospitalsAPIView,
    DoctorRecommendationsAPIView,
    UploadReportAPIView,
    CalculateRouteAPIView,
    BookAppointmentAPIView,
    SpecialtiesListAPIView,
)

app_name = "healthcare_intelligence"

urlpatterns = [
    # HTML5 Frontend Pages
    path("healthcare/", healthcare_dashboard_view, name="dashboard"),
    path("hospitals/", nearby_hospitals_view, name="nearby_hospitals"),
    path("hospitals/<int:hospital_id>/", hospital_details_view, name="hospital_details"),
    path("doctors/", find_doctors_view, name="find_doctors"),
    path("doctors/<int:doctor_id>/", doctor_profile_view, name="doctor_profile"),
    path("reports/", report_analysis_view, name="report_analysis"),
    path("reports/<uuid:report_id>/", report_analysis_view, name="report_analysis_detail"),
    path("navigation/", map_navigation_view, name="map_navigation"),

    # REST APIs
    path("api/location/update/", UpdateLocationAPIView.as_view(), name="api_update_location"),
    path("api/hospitals/nearby/", NearbyHospitalsAPIView.as_view(), name="api_nearby_hospitals"),
    path("api/doctors/recommend/", DoctorRecommendationsAPIView.as_view(), name="api_recommend_doctors"),
    path("api/reports/upload/", UploadReportAPIView.as_view(), name="api_upload_report"),
    path("api/route/calculate/", CalculateRouteAPIView.as_view(), name="api_calculate_route"),
    path("api/appointments/book/", BookAppointmentAPIView.as_view(), name="api_book_appointment"),
    path("api/specialties/", SpecialtiesListAPIView.as_view(), name="api_specialties"),
]
