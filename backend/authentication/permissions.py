from rest_framework import permissions


class IsAuthenticatedModuleUser(permissions.BasePermission):
    """Every privileged MediScanAI module uses the central Django session."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
