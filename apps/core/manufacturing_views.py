import csv

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render

from apps.assets.manufacturing import compare_manufacturing, manufacturing_candidates
from apps.assets.models import Asset

from .manufacturing_forms import ManufacturingSearchForm


def manufacturing_search(request):
    form = ManufacturingSearchForm(request.GET)
    rows = []
    if form.is_valid():
        candidates = manufacturing_candidates(
            Asset.public.select_related("region", "manufacturing_profile")
            .prefetch_related("sources")
        )
        rows = [compare_manufacturing(asset, form.cleaned_data) for asset in candidates]
        if form.cleaned_data.get("outcome"):
            rows = [row for row in rows if row["state"] == form.cleaned_data["outcome"]]
        rows.sort(key=lambda row: (
            {"match": 0, "reference": 1, "unknown": 2}[row["state"]],
            not row["evidence_usable"],
            row["asset"].public_name.casefold(), str(row["asset"].pk),
        ))
        if request.GET.get("download") == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                'attachment; filename="cosolve-manufacturing-comparison.csv"'
            )
            writer = csv.writer(response)

            def write(values):
                writer.writerow([
                    "'" + value if isinstance(value, str)
                    and value.lstrip().startswith(("=", "+", "-", "@")) else value
                    for value in values
                ])

            write(["Planning comparison only; not a quote, capacity or service commitment"])
            write(["Requirement", "Value"])
            for field in form:
                write([field.label, form.cleaned_data.get(field.name) or "Not specified"])
            write([])
            write([
                "Asset", "Outcome", "Processes", "Materials", "Service modes", "Access",
                "Comparison", "Evidence notes", "Profile", "Public source",
            ])
            for row in rows:
                write([
                    row["asset"].public_name, row["label"],
                    *["; ".join(row[key]) for key in (
                        "process_labels", "material_labels", "service_mode_labels", "access_labels"
                    )],
                    "; ".join(f"{check['label']}: {check['status']} - {check['text']}"
                              for check in row["checks"]),
                    row["notes"], request.build_absolute_uri(row["asset"].get_absolute_url()),
                    row["source_url"],
                ])
            return response
    params = request.GET.copy()
    params.pop("page", None)
    params["download"] = "csv"
    return render(request, "core/manufacturing.html", {
        "form": form,
        "page_obj": Paginator(rows, 12).get_page(request.GET.get("page")),
        "result_count": len(rows),
        "download_query": params.urlencode(),
    })
