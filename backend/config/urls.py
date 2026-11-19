from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("admin/healthcare/", include("admin.backend.urls")),
    path("admin/", admin.site.urls),
    # Python-rendered MedScanAI landing page, account screens, workspace, and APIs.
    path("", include("backend.core.healthcare_intelligence.backend.workspace_urls")),
    # Healthcare Intelligence Module
    path("", include("backend.core.healthcare_intelligence.backend.urls")),
]

if settings.DEBUG:
    # Let Django's static-file finders serve both the root workspace assets and
    # the retained healthcare module assets during local development.
    urlpatterns += staticfiles_urlpatterns()
