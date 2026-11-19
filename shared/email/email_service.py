from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_notification(subject, recipient, template_name=None, context=None, text_body=None):
    """Send one configured email and report whether the backend accepted it."""
    recipient = str(recipient or "").strip()
    if not recipient:
        raise ValueError("A recipient email address is required.")
    context = context or {}
    body = text_body
    if template_name:
        body = render_to_string(template_name, context)
    if not body:
        raise ValueError("An email body or template is required.")
    message = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[recipient],
    )
    return message.send(fail_silently=False) == 1


def send_module_notification(user, preference_key, subject, text_body=None, template_name=None, context=None):
    preference = getattr(user, "notification_preference", None)
    if not getattr(user, "email", "") or preference is None or not preference.email_enabled:
        return False
    if preference_key and not getattr(preference, preference_key, False):
        return False
    return send_notification(
        subject=subject,
        recipient=user.email,
        template_name=template_name,
        context=context,
        text_body=text_body,
    )
    return True
