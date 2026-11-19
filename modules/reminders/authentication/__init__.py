"""Use the central Django session permission for user reminders."""

from backend.authentication.permissions import IsAuthenticatedModuleUser

__all__ = ["IsAuthenticatedModuleUser"]
