"""Use the central Django session permission for private navigation history."""

from backend.authentication.permissions import IsAuthenticatedModuleUser

__all__ = ["IsAuthenticatedModuleUser"]
