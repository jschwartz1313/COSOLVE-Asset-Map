"""Small planning tools over the same publicly scoped asset inventory."""

import csv
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import SuspiciousOperation
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.api.query import filter_public_assets
from apps.assets.manufacturing import compare_manufacturing
from apps.assets.models import Asset
from apps.assets.operator_review import get_public_operator_details
from apps.assets.public_details import public_contact_details
from apps.assets.testing import evidence_usable


def comparison_rows(assets):
    manufacturing = {a.pk: compare_manufacturing(a, {}) for a in assets}
    operators = {a.pk: get_public_operator_details(a) for a in assets}
    contacts = {a.pk: public_contact_details(a, operators[a.pk]) for a in assets}

    def manufacturing_summary(asset):
        row = manufacturing[asset.pk]
        return "\n".join("; ".join(row[key]) for key in (
            "process_labels", "material_labels", "service_mode_labels", "access_labels"
        ) if row[key]) or "Not documented"

    def testing(asset):
        if evidence_usable(asset, asset.test_source_url, asset.test_last_verified_at):
            return "\n".join(filter(None, [asset.test_aircraft, asset.test_dimensions,
                                           asset.test_access])) or "Not documented"
        return "Not documented; confirm with operator"

    fields = (
        ("Location", lambda a: ", ".join(filter(None, [a.address_line, a.city, a.state]))
         or "Not documented"),
        ("Location represents", lambda a: a.get_location_role_display()
         or a.public_location_label),
        ("What it offers", lambda a: a.short_description),
        ("Uses and relevance", lambda a: a.unmanned_systems_relevance),
        ("Capabilities", lambda a: "; ".join(c.name for c in a.capabilities.all())),
        ("Manufacturing", manufacturing_summary),
        ("Testing and access", testing),
        ("Operator-provided uses", lambda a: operators[a.pk].get("use_cases", "")),
        ("Operator-provided access", lambda a: operators[a.pk].get("access_notes", "")),
        ("Collaboration", lambda a: a.partnership_opportunities if evidence_usable(
            a, a.activity_source_url, a.activity_last_verified_at) else "Not documented"),
        ("Public contact", lambda a: "\n".join(filter(None, [
            contacts[a.pk][key] for key in ("text", "email", "phone", "url")]))),
        ("Website", lambda a: a.website_url),
    )
    rows = [{"label": label, "values": [str(getter(a) or "Not documented") for a in assets]}
            for label, getter in fields]
    optional = {"Manufacturing", "Operator-provided uses", "Operator-provided access"}
    return [row for row in rows if row["label"] not in optional
            or any(value != "Not documented" for value in row["values"])]


def _comparison_slugs(request):
    selected = list(dict.fromkeys(request.GET.getlist("asset")))
    if len(selected) > 5 or any(len(value) > 240 for value in selected):
        raise SuspiciousOperation("Select no more than five assets.")
    return selected


def _selection_label(asset):
    return {"slug": asset.slug, "name": asset.public_name, "url": asset.get_absolute_url()}


@require_http_methods(["GET"])
def comparison_selection(request):
    selected = _comparison_slugs(request)
    found = {asset.slug: asset for asset in Asset.public.filter(slug__in=selected).only(
        "name", "display_name", "slug"
    )}
    response = JsonResponse({"assets": [_selection_label(found[slug]) for slug in selected
                                        if slug in found]})
    response["Cache-Control"] = "private, no-store"
    return response


class AssetPickerForm(forms.Form):
    q = forms.CharField(required=False, max_length=200)
    record_type = forms.ChoiceField(required=False, choices=[("", "All asset types"),
                                                            *Asset.RecordType.choices])
    region = forms.SlugField(required=False, max_length=80)


@require_http_methods(["GET"])
def comparison_options(request):
    form = AssetPickerForm(request.GET)
    if not form.is_valid():
        response = JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    else:
        params = QueryDict(mutable=True)
        for key, value in form.cleaned_data.items():
            if value:
                params[key] = value
        page = Paginator(filter_public_assets(params, include_related=False), 24).get_page(
            request.GET.get("page")
        )
        response = JsonResponse({
            "assets": [{**_selection_label(asset), "record_type": asset.record_type,
                        "record_type_label": asset.get_record_type_display(),
                        "location": ", ".join(filter(None, (asset.city, asset.state)))
                        if asset.city else asset.region.name if asset.region else "Virginia"}
                       for asset in page],
            "count": page.paginator.count, "page": page.number,
            "pages": page.paginator.num_pages,
        })
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["GET"])
def compare_assets(request):
    selected = _comparison_slugs(request)
    found = {a.slug: a for a in Asset.public.filter(slug__in=selected).prefetch_related(
        "sources", "capabilities")}
    assets = [found[slug] for slug in selected if slug in found]
    selected = [asset.slug for asset in assets]
    rows = comparison_rows(assets)
    if request.GET.get("download") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="cosolve-asset-comparison.csv"'
        writer = csv.writer(response)

        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

        writer.writerow(["Field", *[safe(a.public_name) for a in assets]])
        for row in rows:
            writer.writerow([row["label"], *[safe(v) for v in row["values"]]])
        writer.writerow(["Profile", *[request.build_absolute_uri(a.get_absolute_url())
                                     for a in assets]])
        return response
    query = request.GET.get("q", "").strip()[:200]
    candidates = []
    if query and len(assets) < 5:
        params = QueryDict(urlencode({"q": query}))
        for asset in filter_public_assets(params).exclude(slug__in=selected)[:12]:
            candidates.append({"asset": asset, "query": urlencode(
                [("asset", slug) for slug in [*selected, asset.slug]])})
    return render(request, "assets/compare.html", {
        "assets": assets, "rows": rows, "query": query, "candidates": candidates,
        "selection": [(a, urlencode([("asset", s) for s in selected if s != a.slug]
                                    or [("clear", "1")]))
                      for a in assets],
        "browser_selection": {
            "slugs": selected,
            "assets": [_selection_label(asset) for asset in assets],
            "explicit": "asset" in request.GET or request.GET.get("clear") == "1",
        },
        "picker_record_types": Asset.RecordType.choices,
        "picker_regions": [{"slug": region["region__slug"], "name": region["region__name"]}
                           for region in Asset.public.exclude(region__isnull=True).values(
                               "region__slug", "region__name"
                           ).order_by("region__name").distinct()],
        "download_query": urlencode([("asset", s) for s in selected] + [("download", "csv")]),
    })


class InquiryForm(forms.Form):
    purpose = forms.CharField(label="Project or intended use", max_length=2000,
                              widget=forms.Textarea(attrs={"rows": 3}))
    requirements = forms.CharField(label="Aircraft, part or technical requirements",
                                   required=False, max_length=3000,
                                   widget=forms.Textarea(attrs={"rows": 4}))
    timing = forms.CharField(label="Timing and quantities", required=False, max_length=400)
    organization = forms.CharField(label="Your organization", required=False, max_length=200)


@require_http_methods(["GET", "POST"])
def prepare_inquiry(request, slug):
    asset = get_object_or_404(Asset.public, slug=slug)
    form = InquiryForm(request.POST if request.method == "POST" else None)
    draft = ""
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        draft = "\n\n".join(filter(None, [
            f"Subject: Project inquiry - {asset.public_name}",
            f"Hello {asset.public_name} team,",
            f"I am contacting you about: {data['purpose']}",
            f"Technical requirements:\n{data['requirements']}" if data['requirements'] else "",
            f"Timing and quantities: {data['timing']}" if data['timing'] else "",
            "Could you confirm whether this is within your scope, what access or sponsorship "
            "is required, availability, applicable safety/approval steps, "
            "and the best project contact?",
            "Please also advise which specifications or supporting documents you need from us.",
            f"Organization: {data['organization']}" if data['organization'] else "",
            f"Asset profile: {request.build_absolute_uri(asset.get_absolute_url())}",
        ]))
        if request.POST.get("download") == "text":
            response = HttpResponse(draft, content_type="text/plain; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="cosolve-inquiry.txt"'
            response["Cache-Control"] = "no-store"
            return response
    response = render(request, "assets/inquiry.html", {
        "asset": asset, "form": form, "draft": draft,
        "public_contact": public_contact_details(asset),
    })
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "same-origin"
    return response
