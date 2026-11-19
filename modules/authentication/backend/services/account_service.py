"""Small account operations built on the project's configured Django user."""

import re
import secrets

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from backend.authentication.services.otp_service import verify_otp

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@transaction.atomic
def create_account(email, password, full_name=""):
    """Create an inactive account; email confirmation remains the activation gate."""
    email = str(email or "").strip().lower()
    password = str(password or "")
    full_name = str(full_name or "").strip()
    if not EMAIL_RE.fullmatch(email):
        raise ValidationError("A valid email address is required.")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")

    user_model = get_user_model()
    if user_model.objects.filter(email__iexact=email).exists():
        raise ValidationError("This email is already registered.")

    username = email[:150]
    if user_model.objects.filter(username=username).exists():
        username = f"{email[:120]}-{secrets.token_hex(4)}"
    names = full_name.split(" ", 1)
    return user_model.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=names[0] if names else "",
        last_name=names[1] if len(names) > 1 else "",
        is_active=False,
    )


@transaction.atomic
def verify_email_code(user, code, purpose="verify_email"):
    """Consume a valid one-time code and activate email-verification accounts."""
    if not verify_otp(user, purpose, code):
        return False
    if purpose == "verify_email" and not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    return True
