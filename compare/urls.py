"""URL routes for the compare app."""
from __future__ import annotations

from django.urls import path

from . import views

app_name = "compare"

urlpatterns = [
    path("", views.upload_page, name="upload"),
    path("compare/", views.compare_documents, name="compare"),
    path("result/<uuid:pk>/", views.result_detail, name="result"),
    path("export/pdf/<uuid:pk>/", views.export_pdf, name="export-pdf"),
    path("api/compare/", views.api_compare, name="api-compare"),
    path("health/", views.health_check, name="health"),
]
