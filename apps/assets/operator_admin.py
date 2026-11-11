"""Parent registers OperatorReviewAdmin and optionally attaches the Asset action."""

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.html import format_html

from .models import Asset
from .operator_review import (
    OperatorReview,
    can_manage_operator_reviews,
    require_operator_review_staff,
    validate_public_url,
)


def _private_response(response):
    add_never_cache_headers(response)
    response["Referrer-Policy"] = "strict-origin"
    return response


class OperatorInvitationForm(forms.ModelForm):
    class Meta:
        model = OperatorReview
        fields = ("asset", "expires_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "asset" in self.fields:
            self.fields["asset"].queryset = Asset.public.all()

    def clean_expires_at(self):
        expires_at = self.cleaned_data["expires_at"]
        if expires_at <= timezone.now():
            raise forms.ValidationError("The invitation expiry must be in the future.")
        return expires_at


class OperatorReviewAdmin(admin.ModelAdmin):
    form = OperatorInvitationForm
    list_display = (
        "asset", "created_at", "expires_at", "submitted_at", "approved_at", "revoked_at",
    )
    list_filter = ("publication_consent", "submitted_at", "approved_at", "revoked_at")
    list_select_related = ("asset", "created_by", "approved_by")
    search_fields = ("asset__name", "submitter_name", "submitter_email")
    actions = ("approve_proposals", "revoke_invitations")

    def has_module_permission(self, request):
        return can_manage_operator_reviews(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_operator_reviews(request.user)

    def has_add_permission(self, request):
        return can_manage_operator_reviews(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_operator_reviews(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                "asset", "invitation_url", "expires_at", "proposal", "submitter_name",
                "submitter_email", "publication_consent", "submitted_at", "approved_at",
                "approved_by", "revoked_at", "baseline", "created_by", "created_at",
            )
        return ()

    def get_fields(self, request, obj=None):
        return self.get_readonly_fields(request, obj) if obj else ("asset", "expires_at")

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field=from_field)
        if obj is not None:
            obj._request_invitation_url = request.build_absolute_uri(obj.get_absolute_url())
        return obj

    @admin.display(description="Invitation URL (share privately; no email is sent)")
    def invitation_url(self, obj):
        if not obj.is_available or not Asset.public.filter(pk=obj.asset_id).exists():
            return "Invitation unavailable"
        url = getattr(obj, "_request_invitation_url", None)
        if url is None:
            url = f"{settings.PUBLIC_SITE_URL.rstrip('/')}{obj.get_absolute_url()}"
        try:
            validate_public_url(url)
        except ValidationError:
            return "Configure a valid PUBLIC_SITE_URL to display the invitation URL."
        return format_html('<a href="{}" rel="noreferrer noopener">{}</a>', url, url)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        require_operator_review_staff(request.user)
        if object_id and request.method == "POST":
            raise PermissionDenied("Use the approve or revoke actions; proposals are immutable.")
        extra_context = dict(extra_context or {})
        if object_id:
            extra_context.update(show_save=False, show_save_and_continue=False,
                                 show_save_and_add_another=False, show_delete=False)
        return _private_response(super().changeform_view(
            request, object_id, form_url, extra_context=extra_context,
        ))

    def changelist_view(self, request, extra_context=None):
        require_operator_review_staff(request.user)
        return _private_response(super().changelist_view(request, extra_context=extra_context))

    def save_model(self, request, obj, form, change):
        require_operator_review_staff(request.user)
        if change:
            raise PermissionDenied
        issued = OperatorReview.issue(
            asset=obj.asset, created_by=request.user, expires_at=obj.expires_at,
        )
        obj.__dict__.update(issued.__dict__)

    def response_add(self, request, obj, post_url_continue=None):
        # Always show the new URL instead of returning to the list after creation.
        return _private_response(HttpResponseRedirect(reverse(
            f"{self.admin_site.name}:assets_operatorreview_change", args=(obj.pk,),
        )))

    @admin.action(permissions=["change"], description="Approve selected operator proposals")
    def approve_proposals(self, request, queryset):
        self._transition(request, queryset, "approve")

    @admin.action(permissions=["change"], description="Revoke selected operator invitations")
    def revoke_invitations(self, request, queryset):
        self._transition(request, queryset, "revoke")

    def _transition(self, request, queryset, transition):
        require_operator_review_staff(request.user)
        if request.method != "POST":
            raise PermissionDenied
        count = 0
        for review in queryset.order_by("pk"):
            try:
                getattr(review, transition)(user=request.user)
            except ValidationError as error:
                self.message_user(
                    request, f"{review.asset}: {' '.join(error.messages)}", level=messages.WARNING,
                )
            else:
                self.log_change(request, review, f"Operator proposal {transition} action.")
                count += 1
        self.message_user(
            request, f"Updated {count} operator invitation(s).", level=messages.SUCCESS,
        )


@admin.action(permissions=["operator_review"], description="Create operator review invitation")
def create_operator_review_invitation(modeladmin, request, queryset):
    require_operator_review_staff(request.user)
    if request.method != "POST":
        raise PermissionDenied
    if queryset.count() != 1:
        modeladmin.message_user(
            request, "Select one public asset to invite.", level=messages.WARNING,
        )
        return None
    try:
        review = OperatorReview.issue(asset=queryset.get(), created_by=request.user)
    except ValidationError as error:
        modeladmin.message_user(request, " ".join(error.messages), level=messages.WARNING)
        return None
    modeladmin.log_change(request, review.asset, "Created an operator review invitation.")
    return _private_response(HttpResponseRedirect(reverse(
        f"{modeladmin.admin_site.name}:assets_operatorreview_change", args=(review.pk,),
    )))
