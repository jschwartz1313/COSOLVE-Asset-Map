import csv
from datetime import timedelta

from allauth.account.forms import ResetPasswordForm
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.utils import timezone
from simple_history.admin import SimpleHistoryAdmin

from apps.imports.services import CSV_COLUMNS, asset_csv_row
from apps.sources.models import Source

from .models import (
    Asset,
    AssetReviewComment,
    DuplicateCandidate,
    Relationship,
    UpdateSubmission,
)


class SourceInline(admin.TabularInline):
    model = Source
    extra = 0
    fields = (
        "title",
        "url",
        "source_date",
        "verification_status",
        "last_verified_at",
        "is_public",
        "link_review_status",
        "link_review_notes",
        "notes",
    )


class OutgoingRelationshipInline(admin.TabularInline):
    model = Relationship
    fk_name = "from_asset"
    extra = 0


class AssetReviewCommentInline(admin.TabularInline):
    model = AssetReviewComment
    extra = 1
    fields = ("body", "author", "created_at")
    readonly_fields = ("author", "created_at")
    verbose_name = "Internal review comment"
    verbose_name_plural = "Internal review comments"


@admin.action(permissions=["change"], description="Send selected records to source review")
def send_for_review(modeladmin, request, queryset):
    updated = 0
    for asset in queryset.exclude(status=Asset.Status.ARCHIVED):
        asset.status = Asset.Status.NEEDS_REVIEW
        asset.last_verified_at = None
        asset.reviewed_at = None
        asset.reviewed_by = None
        asset.published_at = None
        asset._history_user = request.user
        asset._change_reason = "Sent to source review from the admin action."
        asset.save()
        updated += 1
    messages.success(request, f"Sent {updated} record(s) to source review.")


@admin.action(permissions=["change"], description="Assign selected records to me")
def assign_to_me(modeladmin, request, queryset):
    updated = 0
    for asset in queryset.exclude(status=Asset.Status.ARCHIVED):
        asset.review_assignee = request.user
        asset._history_user = request.user
        asset._change_reason = "Review assigned from the admin action."
        asset.save()
        updated += 1
    messages.success(request, f"Assigned {updated} record(s) to {request.user.get_username()}.")


@admin.action(permissions=["change"], description="Set review due in 14 days")
def set_review_due(modeladmin, request, queryset):
    due_at = timezone.localdate() + timedelta(days=14)
    updated = 0
    for asset in queryset.exclude(status=Asset.Status.ARCHIVED):
        asset.review_due_at = due_at
        if asset.review_assignee_id is None:
            asset.review_assignee = request.user
        asset._history_user = request.user
        asset._change_reason = "Review due date set from the admin action."
        asset.save()
        updated += 1
    messages.success(request, f"Set {updated} review(s) due by {due_at:%b %-d, %Y}.")


@admin.action(permissions=["change"], description="Clear selected review assignments")
def clear_review_assignment(modeladmin, request, queryset):
    updated = 0
    for asset in queryset:
        asset.review_assignee = None
        asset.review_due_at = None
        asset._history_user = request.user
        asset._change_reason = "Review assignment cleared from the admin action."
        asset.save()
        updated += 1
    messages.success(request, f"Cleared {updated} review assignment(s).")


@admin.action(permissions=["verify"], description="Mark eligible records verified")
def mark_verified(modeladmin, request, queryset):
    eligible = queryset.filter(
        sources__is_public=True,
        sources__verification_status="verified",
        sources__last_verified_at__isnull=False,
    ).distinct()
    eligible = eligible.exclude(sources__url="")
    updated = 0
    for asset in eligible:
        asset.status = Asset.Status.VERIFIED
        asset.last_verified_at = timezone.localdate()
        asset.reviewed_at = timezone.now()
        asset.reviewed_by = request.user
        asset.review_assignee = None
        asset.review_due_at = None
        asset.published_at = None
        asset._history_user = request.user
        asset._change_reason = "Editorial verification completed from the admin action."
        asset.save()
        updated += 1
    skipped = queryset.count() - updated
    messages.success(request, f"Verified {updated} record(s).")
    if skipped:
        messages.warning(request, f"Skipped {skipped} record(s) without a verified public source.")


@admin.action(
    permissions=["change"],
    description="Mark selected records unverified (keep source-backed listing)",
)
def mark_unverified(modeladmin, request, queryset):
    eligible = queryset.filter(status__in=(Asset.Status.VERIFIED, Asset.Status.PUBLISHED))
    updated = 0
    for asset in eligible:
        asset.status = Asset.Status.SOURCE_BACKED
        asset.last_verified_at = None
        asset.reviewed_at = None
        asset.reviewed_by = None
        asset.published_at = None
        asset._history_user = request.user
        asset._change_reason = "Editorial verification reversed from the admin action."
        asset.save()
        updated += 1
    skipped = queryset.count() - updated
    messages.success(request, f"Marked {updated} record(s) unverified and review pending.")
    if skipped:
        messages.warning(request, f"Skipped {skipped} record(s) that were not verified.")


@admin.action(permissions=["publish"], description="Publish eligible verified records")
def publish_eligible(modeladmin, request, queryset):
    eligible = queryset.filter(
        status=Asset.Status.VERIFIED,
        sources__is_public=True,
        sources__verification_status="verified",
        sources__last_verified_at__isnull=False,
    ).distinct()
    eligible = eligible.exclude(sources__url="")
    updated = 0
    for asset in eligible:
        asset.status = Asset.Status.PUBLISHED
        asset.visibility = Asset.Visibility.PUBLIC
        asset.published_at = timezone.now()
        asset._history_user = request.user
        asset._change_reason = "Published after editorial verification."
        asset.save()
        updated += 1
    skipped = queryset.count() - updated
    if skipped:
        messages.warning(
            request,
            f"Skipped {skipped} record(s) that were not verified or lacked "
            "a verified public source.",
        )


@admin.action(permissions=["publish"], description="Archive selected records")
def archive_records(modeladmin, request, queryset):
    updated = 0
    for asset in queryset:
        asset.status = Asset.Status.ARCHIVED
        asset.published_at = None
        asset._history_user = request.user
        asset._change_reason = "Archived from the admin action."
        asset.save()
        updated += 1
    messages.success(request, f"Archived {updated} record(s).")


@admin.action(permissions=["export"], description="Export selected records as CSV")
def export_selected(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="cosolve-selected-assets.csv"'
    writer = csv.DictWriter(response, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    assets = queryset.select_related("region").prefetch_related(
        "strategic_categories",
        "platform_domains",
        "capabilities",
        "missions",
        "sources",
    )
    for asset in assets.order_by("name"):
        writer.writerow(asset_csv_row(asset, include_internal=True))
    return response


@admin.register(Asset)
class AssetAdmin(SimpleHistoryAdmin):
    list_display = (
        "name",
        "record_type",
        "region",
        "status",
        "visibility",
        "review_priority",
        "review_assignee",
        "review_due_at",
        "last_verified_at",
        "updated_at",
    )
    list_filter = (
        "record_type",
        "region",
        "status",
        "visibility",
        "review_priority",
        "review_assignee",
        "review_due_at",
        "last_verified_at",
    )
    search_fields = ("name", "short_description", "unmanned_systems_relevance", "city")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("strategic_categories", "platform_domains", "capabilities", "missions")
    readonly_fields = (
        "status",
        "visibility",
        "last_verified_at",
        "reviewed_at",
        "reviewed_by",
        "published_at",
        "created_at",
        "updated_at",
    )
    inlines = (AssetReviewCommentInline, SourceInline, OutgoingRelationshipInline)
    actions = (
        assign_to_me,
        set_review_due,
        clear_review_assignment,
        send_for_review,
        mark_verified,
        mark_unverified,
        publish_eligible,
        archive_records,
        export_selected,
    )
    fieldsets = (
        ("Identity", {"fields": ("name", "slug", "record_type", "short_description")}),
        ("Unmanned systems relevance", {"fields": ("unmanned_systems_relevance",)}),
        (
            "Taxonomy",
            {"fields": ("strategic_categories", "platform_domains", "capabilities", "missions")},
        ),
        (
            "Location",
            {
                "fields": (
                    "address_line",
                    "city",
                    "state",
                    "postal_code",
                    "latitude",
                    "longitude",
                    "location_precision",
                    "region",
                )
            },
        ),
        (
            "Review workflow",
            {
                "fields": (
                    "review_assignee",
                    "review_priority",
                    "review_due_at",
                )
            },
        ),
        (
            "Publication",
            {
                "fields": (
                    "status",
                    "visibility",
                    "last_verified_at",
                    "reviewed_at",
                    "reviewed_by",
                    "review_notes",
                    "published_at",
                )
            },
        ),
        ("Public contact", {"fields": ("website_url", "contact_text")}),
        ("Internal", {"fields": ("internal_notes",), "classes": ("collapse",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def has_verify_permission(self, request):
        return request.user.has_perm("assets.can_verify_asset")

    def has_publish_permission(self, request):
        return request.user.has_perm("assets.can_publish_asset")

    def has_export_permission(self, request):
        return request.user.has_perm("assets.can_export_asset")

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, AssetReviewComment) and instance.author_id is None:
                instance.author = request.user
                instance._history_user = request.user
            instance.save()
        for deleted in formset.deleted_objects:
            if isinstance(deleted, AssetReviewComment):
                deleted._history_user = request.user
            deleted.delete()
        formset.save_m2m()


@admin.register(Relationship)
class RelationshipAdmin(SimpleHistoryAdmin):
    list_display = ("from_asset", "relationship_type", "to_asset", "is_public")
    list_filter = ("relationship_type", "is_public")
    search_fields = ("from_asset__name", "to_asset__name", "description")
    autocomplete_fields = ("from_asset", "to_asset")


@admin.register(AssetReviewComment)
class AssetReviewCommentAdmin(SimpleHistoryAdmin):
    list_display = ("asset", "author", "created_at", "comment_preview")
    list_filter = ("created_at", "author")
    search_fields = ("asset__name", "body", "author__username", "author__email")
    autocomplete_fields = ("asset", "author")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Comment")
    def comment_preview(self, obj):
        return obj.body[:120]

    def save_model(self, request, obj, form, change):
        if obj.author_id is None:
            obj.author = request.user
        obj._history_user = request.user
        super().save_model(request, obj, form, change)


@admin.register(DuplicateCandidate)
class DuplicateCandidateAdmin(SimpleHistoryAdmin):
    list_display = (
        "left_asset",
        "right_asset",
        "score",
        "status",
        "reviewed_by",
        "updated_at",
    )
    list_filter = ("status", "score", "reviewed_by", "updated_at")
    search_fields = ("left_asset__name", "right_asset__name", "notes")
    autocomplete_fields = ("left_asset", "right_asset", "reviewed_by")
    readonly_fields = ("score", "match_reasons", "detected_at", "updated_at")
    actions = ("mark_distinct", "reopen_candidates", "mark_merged")

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            if obj.status == DuplicateCandidate.Status.OPEN:
                obj.reviewed_by = None
                obj.reviewed_at = None
            else:
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()
        obj._history_user = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Confirm selected pairs are distinct")
    def mark_distinct(self, request, queryset):
        self._resolve(request, queryset, DuplicateCandidate.Status.NOT_DUPLICATE)

    @admin.action(description="Mark selected pairs merged or archived")
    def mark_merged(self, request, queryset):
        self._resolve(request, queryset, DuplicateCandidate.Status.MERGED)

    @admin.action(description="Reopen selected duplicate candidates")
    def reopen_candidates(self, request, queryset):
        self._resolve(request, queryset, DuplicateCandidate.Status.OPEN)

    @staticmethod
    def _resolve(request, queryset, status):
        for candidate in queryset:
            candidate.status = status
            candidate.reviewed_by = (
                None if status == DuplicateCandidate.Status.OPEN else request.user
            )
            candidate.reviewed_at = (
                None if status == DuplicateCandidate.Status.OPEN else timezone.now()
            )
            candidate._history_user = request.user
            candidate._change_reason = f"Duplicate candidate marked {status}."
            candidate.save()
        messages.success(request, f"Updated {queryset.count()} duplicate candidate(s).")


@admin.register(UpdateSubmission)
class UpdateSubmissionAdmin(SimpleHistoryAdmin):
    list_display = (
        "created_at",
        "subject",
        "asset",
        "kind",
        "status",
        "submitter_organization",
    )
    list_filter = ("status", "kind", "created_at")
    search_fields = (
        "subject",
        "details",
        "submitter_name",
        "submitter_organization",
        "submitter_email",
    )
    autocomplete_fields = ("asset",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("asset",)
    date_hierarchy = "created_at"
    actions = ("mark_in_review", "mark_resolved")
    fieldsets = (
        ("Request", {"fields": ("status", "kind", "asset", "subject", "details", "source_url")}),
        (
            "Submitter",
            {
                "fields": (
                    "submitter_name",
                    "submitter_organization",
                    "submitter_email",
                )
            },
        ),
        ("Internal review", {"fields": ("internal_notes",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.action(description="Mark selected submissions in review")
    def mark_in_review(self, request, queryset):
        updated = self._set_status(
            request, queryset, UpdateSubmission.Status.IN_REVIEW, "Marked in review."
        )
        messages.success(request, f"Marked {updated} submission(s) in review.")

    @admin.action(description="Mark selected submissions resolved")
    def mark_resolved(self, request, queryset):
        updated = self._set_status(
            request, queryset, UpdateSubmission.Status.RESOLVED, "Marked resolved."
        )
        messages.success(request, f"Marked {updated} submission(s) resolved.")

    @staticmethod
    def _set_status(request, queryset, status, reason):
        updated = 0
        for submission in queryset:
            submission.status = status
            submission._history_user = request.user
            submission._change_reason = reason
            submission.save()
            updated += 1
        return updated


admin.site.site_header = "COSOLVE Asset Map Administration"
admin.site.site_title = "COSOLVE Admin"
admin.site.index_title = "Ecosystem data maintenance"


User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class RestrictedUserAdmin(DjangoUserAdmin):
    restricted_fields = {"is_superuser", "user_permissions"}
    actions = ("send_account_setup_email",)

    @admin.action(description="Send password setup or reset email")
    def send_account_setup_email(self, request, queryset):
        sent = 0
        skipped = 0
        for user in queryset.filter(is_active=True):
            if not user.email:
                skipped += 1
                continue
            form = ResetPasswordForm({"email": user.email})
            if form.is_valid():
                form.save(request)
                sent += 1
            else:
                skipped += 1
        messages.success(request, f"Sent {sent} account setup email(s).")
        if skipped:
            messages.warning(request, f"Skipped {skipped} account(s) without a usable email.")

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser or obj is None:
            return fieldsets
        restricted_fieldsets = []
        for name, options in fieldsets:
            fields = tuple(
                field for field in options.get("fields", ()) if field not in self.restricted_fields
            )
            restricted_fieldsets.append((name, {**options, "fields": fields}))
        return tuple(restricted_fieldsets)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(is_superuser=False)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if (
            not request.user.is_superuser
            and User._default_manager.filter(pk=object_id, is_superuser=True).exists()
        ):
            raise PermissionDenied
        return super().change_view(request, object_id, form_url, extra_context)
