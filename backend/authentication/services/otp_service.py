from django.utils import timezone
from django.db import transaction

from backend.core.healthcare_intelligence.backend.models import EmailOTP


def create_verification_otp(user, purpose="verify_email", lifetime_minutes=10):
    return EmailOTP.create_for_user(user, purpose=purpose, lifetime_minutes=lifetime_minutes)


def can_resend(record, cooldown_seconds=60):
    if record is None:
        return True
    elapsed = (timezone.now() - record.last_sent_at).total_seconds()
    return elapsed >= cooldown_seconds


@transaction.atomic
def verify_otp(user, purpose, code):
    """Consume one valid code and count failed attempts without racing requests."""
    record = (
        EmailOTP.objects.select_for_update()
        .filter(user=user, purpose=purpose, consumed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if record is None:
        return False

    is_valid = record.is_valid(code)
    if record.attempts < 5 and record.consumed_at is None and timezone.now() < record.expires_at:
        record.attempts += 1
    if is_valid:
        record.consumed_at = timezone.now()
    record.save(update_fields=["attempts", "consumed_at"])
    return is_valid
