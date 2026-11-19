from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from backend.core.healthcare_intelligence.backend.models import MedicineReminder
from modules.reminders.backend.services.reminder_service import due_reminders
from shared.email.email_service import send_module_notification


class Command(BaseCommand):
    help = "Send consented reminder emails due in the current local minute."

    def handle(self, *args, **options):
        now = timezone.localtime()
        due_time = now.strftime("%H:%M")
        sent = 0
        failures = []

        reminders = due_reminders(now)
        for reminder in reminders:
            if reminder.last_notified_at:
                last_sent = timezone.localtime(reminder.last_notified_at)
                if last_sent.date() == now.date() and last_sent.strftime("%H:%M") == due_time:
                    continue

            subject = f"MediScan AI {reminder.get_reminder_type_display().lower()} reminder"
            body = (
                f"This is your requested {reminder.get_reminder_type_display().lower()} reminder: "
                f"{reminder.medicine_name}.\n\n"
                f"Schedule: {reminder.schedule}\n"
                "Check your original instructions and contact your clinician if you have questions."
            )
            try:
                with transaction.atomic():
                    locked = MedicineReminder.objects.select_for_update().get(pk=reminder.pk)
                    if locked.last_notified_at:
                        last_sent = timezone.localtime(locked.last_notified_at)
                        if last_sent.date() == now.date() and last_sent.strftime("%H:%M") == due_time:
                            continue
                    did_send = send_module_notification(
                        locked.user,
                        "reminders",
                        subject,
                        text_body=body,
                    )
                    if did_send:
                        locked.last_notified_at = timezone.now()
                        locked.save(update_fields=["last_notified_at", "updated_at"])
                        sent += 1
            except Exception as exc:
                failures.append(f"Reminder {reminder.pk}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder email(s)."))
        if failures:
            for failure in failures:
                self.stderr.write(self.style.ERROR(failure))
            raise CommandError(f"Failed to send {len(failures)} due reminder email(s).")
