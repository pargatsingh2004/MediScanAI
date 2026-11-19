"""Validation and due-time helpers for reminder APIs and scheduled delivery."""

import re

from django.utils import timezone

from backend.core.healthcare_intelligence.backend.models import MedicineReminder

TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
REMINDER_TYPES = {"medicine", "appointment", "test", "follow_up"}
ALARM_TONES = {"default", "soft", "beep", "alert"}


def normalize_times(values):
    """Validate UI reminder times and return their canonical JSON representation."""
    if not isinstance(values, list) or not values:
        raise ValueError("At least one reminder time is required.")
    normalized = []
    seen = set()
    for value in values:
        if isinstance(value, str):
            time_value, label = value.strip(), None
        elif isinstance(value, dict):
            time_value = str(value.get("time", "")).strip()
            label = str(value.get("label", "")).strip() or None
        else:
            raise ValueError("Each reminder time must be a time string or object.")
        if not TIME_RE.fullmatch(time_value):
            raise ValueError("Reminder times must use HH:MM in 24-hour time.")
        if time_value in seen:
            continue
        seen.add(time_value)
        normalized.append({"time": time_value, "label": label})
    return normalized


def due_reminders(now=None):
    """Return active, email-enabled reminders due in the current local minute."""
    now = timezone.localtime(now or timezone.now())
    due_time = now.strftime("%H:%M")
    records = MedicineReminder.objects.filter(
        active=True,
        email_notification=True,
        user__is_active=True,
    ).select_related("user", "user__notification_preference").order_by("pk")
    due = []
    for reminder in records:
        times = {
            str(slot if isinstance(slot, str) else slot.get("time", "")).strip()
            for slot in (reminder.reminder_times or [])
            if isinstance(slot, (str, dict))
        }
        if due_time not in times:
            continue
        if reminder.last_notified_at:
            last_sent = timezone.localtime(reminder.last_notified_at)
            if last_sent.date() == now.date() and last_sent.strftime("%H:%M") == due_time:
                continue
        due.append(reminder)
    return due
