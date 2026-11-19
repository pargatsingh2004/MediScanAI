"""Use the central Django session permission for private reports."""

from backend.authentication.permissions import IsAuthenticatedModuleUser

__all__ = ["IsAuthenticatedModuleUser"]
