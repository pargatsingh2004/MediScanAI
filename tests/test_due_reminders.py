from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from backend.core.healthcare_intelligence.backend.models import MedicineReminder, NotificationPreference


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DueReminderCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reminder-user",
            email="reminder@example.com",
            password="SecurePassword123",
        )
        now = timezone.localtime()
        self.reminder = MedicineReminder.objects.create(
            user=self.user,
            reminder_type="appointment",
            medicine_name="Clinic follow-up",
            schedule="Daily",
            reminder_times=[now.strftime("%H:%M")],
            email_notification=True,
        )

    def test_reminders_are_not_emailed_without_explicit_consent(self):
        call_command("send_due_reminders")

        self.assertEqual(len(mail.outbox), 0)
        self.reminder.refresh_from_db()
        self.assertIsNone(self.reminder.last_notified_at)

    def test_due_reminder_is_sent_once_with_consent(self):
        NotificationPreference.objects.create(
            user=self.user,
            email_enabled=True,
            reminders=True,
        )

        call_command("send_due_reminders")
        call_command("send_due_reminders")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Clinic follow-up", mail.outbox[0].body)
        self.reminder.refresh_from_db()
        self.assertIsNotNone(self.reminder.last_notified_at)
