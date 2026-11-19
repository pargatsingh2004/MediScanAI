from django.urls import path

from .views import dashboard

app_name = "project_admin"

urlpatterns = [
    path("", dashboard, name="dashboard"),
]
