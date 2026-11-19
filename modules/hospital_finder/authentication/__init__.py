"""Use the central Django session permission for saved hospitals."""

from backend.authentication.permissions import IsAuthenticatedModuleUser

__all__ = ["IsAuthenticatedModuleUser"]
