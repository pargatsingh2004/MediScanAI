from django.db import migrations, models


SEEDED_DOCTOR_REGISTRATIONS = (
    "DMC/R/14290",
    "DMC/R/22819",
    "DMC/R/18744",
    "DMC/R/31045",
    "DMC/R/20932",
    "DMC/R/26781",
    "DMC/R/33418",
    "DMC/R/16503",
)


def unverify_sample_directory(apps, schema_editor):
    Hospital = apps.get_model("healthcare_intelligence", "Hospital")
    Doctor = apps.get_model("healthcare_intelligence", "Doctor")
    DoctorQualification = apps.get_model("healthcare_intelligence", "DoctorQualification")

    sample_hospitals = Hospital.objects.filter(place_id__contains="_sample_")
    sample_hospitals.update(
        verified=False,
        rating=0,
        reviews_count=0,
        emergency_services=False,
    )

    sample_doctors = Doctor.objects.filter(registration_number__in=SEEDED_DOCTOR_REGISTRATIONS)
    sample_doctors.update(
        verified=False,
        rating=0,
        reviews_count=0,
        appointment_available=False,
    )
    DoctorQualification.objects.filter(doctor__in=sample_doctors).update(
        verification_status="pending"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("healthcare_intelligence", "0005_alter_notificationpreference_email_enabled"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hospital",
            name="emergency_services",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="hospital",
            name="verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="doctor",
            name="rating",
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name="doctor",
            name="reviews_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="doctor",
            name="verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="doctor",
            name="appointment_available",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="doctorqualification",
            name="verification_status",
            field=models.CharField(
                choices=[("verified", "Verified"), ("pending", "Pending Verification")],
                default="pending",
                max_length=30,
            ),
        ),
        migrations.RunPython(unverify_sample_directory, migrations.RunPython.noop),
    ]
