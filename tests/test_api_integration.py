import os
import json
from django.test import TestCase, Client
from django.core import mail
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from backend.core.healthcare_intelligence.backend.models import Specialty, Hospital, Doctor, EmailOTP
from backend.core.healthcare_intelligence.backend.services.hospital_finder import HospitalFinder

User = get_user_model()


class APIIntegrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="test_user", password="TestPassword123")
        self.client.force_login(self.user)
        self.specialty = Specialty.objects.create(
            name="Cardiology", code="cardiology", description="Heart health", keywords=["heart", "cholesterol"]
        )
        self.hospital = Hospital.objects.create(
            name="Test Apollo Hospital",
            address="Sarita Vihar, New Delhi",
            latitude=28.5367,
            longitude=77.2882,
            rating=4.8,
            reviews_count=200,
            verified=True,
        )
        self.hospital.specialties.add(self.specialty)
        self.doctor = Doctor.objects.create(
            name="Rajesh Sharma",
            registration_number="DMC-101",
            primary_specialty=self.specialty,
            experience_years=15,
            rating=4.9,
            consultation_fee=1000.0,
            verified=True,
        )

    def test_pages_render_status_200(self):
        pages = ["/", "/hospitals/", "/doctors/", "/reports/", "/navigation/"]
        for p in pages:
            res = self.client.get(p)
            self.assertEqual(res.status_code, 200, f"Page {p} returned status {res.status_code}")
        navigation = self.client.get("/navigation/")
        self.assertContains(navigation, "No verified hospital selected")
        self.assertNotContains(navigation, "Emergency Care Facility")

    def test_external_map_destination_is_supported_without_verification_claim(self):
        response = self.client.get(
            "/navigation/?destination_lat=28.6&destination_lng=77.3&hospital_name=Map%20Listing"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["destination_lat"], 28.6)
        self.assertContains(response, "Map Listing")
        self.assertContains(response, "not independently verified")

        invalid = self.client.get("/navigation/?destination_lat=91&destination_lng=77")
        self.assertIsNone(invalid.context["destination_lat"])
        self.assertFalse(invalid.context["external_destination"])

    def test_hospitals_api(self):
        res = self.client.get("/api/hospitals/nearby/?latitude=28.53&longitude=77.28&radius_meters=15000")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertTrue(len(data["hospitals"]) > 0)

    @override_settings(GOOGLE_PLACES_API_KEY="", GOOGLE_MAPS_API_KEY="")
    def test_hospital_search_excludes_unverified_records(self):
        Hospital.objects.create(
            name="Unverified Sample Clinic",
            address="Sample address",
            latitude=28.5368,
            longitude=77.2883,
        )
        hospitals = HospitalFinder.search_nearby_hospitals(28.5367, 77.2882, 5000)
        self.assertEqual([hospital["name"] for hospital in hospitals], ["Test Apollo Hospital"])
        self.assertTrue(hospitals[0]["verified"])

    def test_doctors_recommend_api(self):
        res = self.client.get("/api/doctors/recommend/?specialty=cardiology&latitude=28.53&longitude=77.28")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertTrue(len(data["doctors"]) > 0)

    def test_route_calculation_api(self):
        payload = {
            "origin_lat": 28.5367,
            "origin_lng": 77.2882,
            "destination_lat": 28.5603,
            "destination_lng": 77.2758,
            "travel_mode": "DRIVING",
            "hospital_id": self.hospital.id,
        }
        res = self.client.post("/api/route/calculate/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("distance_text", data["route"])

    def test_private_writes_require_authentication(self):
        self.client.logout()
        user_count = User.objects.count()
        cases = [
            ("/api/location/update/", {"latitude": 28.5, "longitude": 77.2}),
            ("/api/route/calculate/", {
                "origin_lat": 28.5,
                "origin_lng": 77.2,
                "destination_lat": 28.6,
                "destination_lng": 77.3,
                "travel_mode": "DRIVING",
            }),
            ("/api/appointments/book/", {
                "doctor_id": self.doctor.id,
                "hospital_id": self.hospital.id,
                "appointment_date": "2030-01-01",
                "contact_phone": "555-0100",
            }),
        ]
        for path, payload in cases:
            response = self.client.post(
                path,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertIn(response.status_code, (401, 403), path)
        self.assertEqual(User.objects.count(), user_count)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_otp_verification(self):
        signup = self.client.post(
            "/api/auth/signup",
            data=json.dumps({
                "email": "otp-user@example.com",
                "password": "StrongPassword123",
                "fullName": "OTP User",
            }),
            content_type="application/json",
        )
        self.assertEqual(signup.status_code, 200)
        otp = EmailOTP.objects.select_related("user").get(
            user__email="otp-user@example.com",
            purpose="verify_email",
        )
        self.assertEqual(len(otp.code_hash), 64)
        code = next(
            line.strip()
            for line in mail.outbox[-1].body.splitlines()
            if len(line.strip()) == 6 and line.strip().isdigit()
        )
        verify = self.client.post(
            "/api/auth/verify-otp",
            data=json.dumps({"email": "otp-user@example.com", "otp": code}),
            content_type="application/json",
        )
        self.assertEqual(verify.status_code, 200)
        user = User.objects.get(email="otp-user@example.com")
        self.assertTrue(user.is_active)

    def test_favorite_hospital_is_user_owned(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/favorites/hospitals",
            data=json.dumps({"hospitalId": self.hospital.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        response = self.client.get("/api/favorites/hospitals")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["hospitals"]), 1)

    def test_reminder_supports_consented_notification_types(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/reminders",
            data=json.dumps({
                "reminderType": "appointment",
                "medicineName": "Cardiology follow-up",
                "schedule": "Next Monday",
                "reminderTimes": ["09:30"],
                "emailNotification": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        reminder = response.json()["reminder"]
        self.assertEqual(reminder["reminderType"], "appointment")
        self.assertTrue(reminder["emailNotification"])

    def test_profile_and_trends_export_are_user_owned(self):
        self.client.force_login(self.user)
        profile = self.client.patch(
            "/api/auth/profile",
            data=json.dumps({
                "fullName": "MediScan Test",
                "bloodGroup": "O+",
                "preferredSearchRadius": 12000,
            }),
            content_type="application/json",
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["profile"]["bloodGroup"], "O+")

        export = self.client.get("/api/analytics/trends/export")
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export["Content-Type"], "text/csv")
        self.assertIn("metric,report,date,value,unit,status", export.content.decode("utf-8"))

    def test_report_upload_and_analysis_api(self):
        sample_report_content = (
            b"CLINICAL LABORATORY REPORT\n"
            b"Patient: Test Patient\n"
            b"HbA1c: 7.9 %\n"
            b"Fasting Blood Sugar: 155 mg/dL\n"
            b"Total Cholesterol: 235 mg/dL\n"
            b"Serum Creatinine: 0.9 mg/dL\n"
        )
        test_file = SimpleUploadedFile("sample_lab_report.pdf", sample_report_content, content_type="application/pdf")
        res = self.client.post("/api/reports/upload/", {"file": test_file})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("findings", data)
        self.assertIn("specialties", data)
        self.assertIn("overall_risk", data)
