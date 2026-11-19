import json
import os

from django.core.management.base import BaseCommand

from backend.core.healthcare_intelligence.backend.models import Specialty


class Command(BaseCommand):
    help = "Load specialty categories without importing unverified sample provider records."

    def handle(self, *args, **options):
        project_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
        )
        specialty_file = os.path.join(
            project_dir,
            "modules",
            "report_analysis",
            "data_science",
            "datasets",
            "specialties.json",
        )
        if not os.path.isfile(specialty_file):
            self.stderr.write(self.style.ERROR(f"Specialty dataset was not found: {specialty_file}"))
            return

        with open(specialty_file, "r", encoding="utf-8") as source:
            specialties = json.load(source)
        created = 0
        for item in specialties:
            _, was_created = Specialty.objects.get_or_create(
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "icon_name": item.get("icon_name", "stethoscope"),
                    "keywords": item.get("keywords", []),
                    "is_active": True,
                },
            )
            created += int(was_created)

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(specialties)} specialties ({created} new)."
        ))
        self.stdout.write(
            "Provider sample datasets are intentionally not imported. "
            "Add providers only after verifying their identity, location, and contact details."
        )
