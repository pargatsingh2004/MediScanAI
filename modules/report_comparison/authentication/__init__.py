"""Use the central Django session permission for report comparison."""

from backend.authentication.permissions import IsAuthenticatedModuleUser

__all__ = ["IsAuthenticatedModuleUser"]
