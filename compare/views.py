"""Views for document comparison and result presentation."""
from __future__ import annotations

import logging
from io import BytesIO

from django.db import DatabaseError
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .forms import DocCompareForm
from .models import DiffResult
from .serializers import DiffResultSerializer
from .services import (
    DiffOptions,
    DocumentParseError,
    export_diff_pdf,
    perform_comparison,
    store_diff_result,
)


logger = logging.getLogger(__name__)


STORAGE_ERROR_MESSAGE = (
    "We couldn't save this comparison because the database isn't available. "
    "Configure the DATABASE_URL environment variable and run migrations to enable saved results and downloads."
)


@require_http_methods(["GET"])
def upload_page(request: HttpRequest) -> HttpResponse:
    """Render the document upload form."""

    form = DocCompareForm()
    return render(request, "compare/upload.html", {"form": form})


@require_http_methods(["POST"])
def compare_documents(request: HttpRequest) -> HttpResponse:
    """Accept file uploads, compute the diff, and render the result."""

    form = DocCompareForm(request.POST, request.FILES)
    if not form.is_valid():
        status = 422 if request.headers.get("HX-Request") else 400
        return render(request, "compare/upload.html", {"form": form}, status=status)

    options = DiffOptions.from_dict(form.cleaned_data)
    files = list(form.iter_files())
    try:
        diff, filenames = perform_comparison(files, options)
    except (DocumentParseError, ValueError) as exc:
        form.add_error(None, str(exc))
        status = 422 if request.headers.get("HX-Request") else 400
        return render(request, "compare/upload.html", {"form": form}, status=status)

    persisted = True
    storage_error: str | None = None
    saved: DiffResult | None = None
    try:
        saved = store_diff_result(diff, options, filenames)
    except DatabaseError as exc:
        persisted = False
        storage_error = STORAGE_ERROR_MESSAGE
        logger.warning("Failed to store diff result: %s", exc, exc_info=exc)

    generated_at = saved.created_at if saved else timezone.now()

    context = {
        "result": saved,
        "summary": diff.summary,
        "diff_html": diff.html,
        "options": options,
        "link_changes": diff.link_changes,
        "filenames": list(filenames),
        "generated_at": generated_at,
        "persisted": persisted and saved is not None,
        "storage_error": storage_error,
    }

    if request.headers.get("HX-Request"):
        if persisted and saved is not None:
            response = render(request, "compare/result.html", context)
            response["HX-Redirect"] = reverse("compare:result", args=[saved.pk])
            return response
        return render(request, "compare/result_section.html", context)

    if persisted and saved is not None:
        return redirect("compare:result", pk=saved.pk)

    return render(request, "compare/result.html", context, status=503)


@require_GET
def result_detail(request: HttpRequest, pk: str) -> HttpResponse:
    """Display a saved diff result."""

    result = get_object_or_404(DiffResult, pk=pk)
    context = {
        "result": result,
        "summary": result.summary,
        "diff_html": result.diff_html,
        "options": result.options,
        "link_changes": result.diff_json.get("linkChanges", []) if isinstance(result.diff_json, dict) else [],
        "filenames": result.source_filenames,
        "generated_at": result.created_at,
        "persisted": True,
        "storage_error": None,
    }
    return render(request, "compare/result.html", context)


@require_GET
def export_pdf(request: HttpRequest, pk: str) -> HttpResponse:
    """Return a generated PDF for the diff result."""

    result = get_object_or_404(DiffResult, pk=pk)
    pdf_bytes = export_diff_pdf(result)
    response = FileResponse(
        BytesIO(pdf_bytes),
        content_type="application/pdf",
        filename=f"docdiff-{pk}.pdf",
        as_attachment=True,
    )
    return response


@require_GET
def health_check(request: HttpRequest) -> JsonResponse:
    """Return a simple health status payload."""

    return JsonResponse({"status": "ok"})


@api_view(["POST"])
def api_compare(request: HttpRequest) -> Response:
    """API endpoint returning JSON diff output."""

    form = DocCompareForm(request.POST, request.FILES)
    form.full_clean()
    if not form.is_valid():
        return Response({"errors": form.errors}, status=400)

    options = DiffOptions.from_dict(form.cleaned_data)
    files = list(form.iter_files())
    diff, filenames = perform_comparison(files, options)
    saved = store_diff_result(diff, options, filenames)
    serializer = DiffResultSerializer(saved)
    return Response(serializer.data, status=201)
