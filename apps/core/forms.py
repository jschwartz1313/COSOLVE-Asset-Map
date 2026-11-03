from decimal import Decimal

from allauth.account.forms import ResetPasswordForm
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.assets.models import SavedView, UpdateSubmission
from apps.assets.testing import ACCESS_CHOICES, ACTIVITY_CHOICES, LAUNCH_CHOICES


class TestSiteSearchForm(forms.Form):
    weight = forms.DecimalField(label="Aircraft weight (lb)", required=False,
                                min_value=Decimal("0.01"), max_value=Decimal("1000000"),
                                max_digits=10, decimal_places=2)
    span = forms.DecimalField(label="Aircraft span / width (ft)", required=False,
                              min_value=Decimal("0.01"), max_value=Decimal("10000"),
                              max_digits=8, decimal_places=2)
    launch = forms.ChoiceField(label="Launch / recovery", required=False,
                               choices=[("", "Any launch method"), *LAUNCH_CHOICES])
    runway = forms.IntegerField(label="Required runway (ft)", required=False,
                                min_value=1, max_value=100000)
    activity = forms.ChoiceField(label="Testing activity", required=False,
                                 choices=[("", "Any testing activity"), *ACTIVITY_CHOICES])
    access = forms.ChoiceField(label="Documented access", required=False,
                               choices=[("", "All access conditions"), *ACCESS_CHOICES,
                                        ("undocumented", "Not documented")])
    outcome = forms.ChoiceField(label="Results", required=False,
                                choices=[("", "All outcomes"),
                                         ("match", "Documented criteria match"),
                                         ("unknown", "Needs confirmation"),
                                         ("conflict", "Published limit conflict")])


class SiteResetPasswordForm(ResetPasswordForm):
    @property
    def email_delivery_configured(self):
        return (
            settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend"
            or bool(settings.EMAIL_HOST.strip())
        )

    def clean(self):
        cleaned = super().clean()
        if not self.email_delivery_configured:
            raise ValidationError(
                "Password-reset email is not available yet. "
                "Contact the COSOLVE administrator for help signing in."
            )
        return cleaned


class UpdateSubmissionForm(forms.ModelForm):
    confirmation = forms.CharField(
        required=False,
        label="Leave this field blank",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    class Meta:
        model = UpdateSubmission
        fields = (
            "kind",
            "subject",
            "details",
            "source_url",
            "submitter_name",
            "submitter_organization",
            "submitter_email",
        )
        labels = {
            "kind": "Request type",
            "subject": "Record or organization",
            "details": "What should be added or changed?",
            "source_url": "Supporting source URL",
            "submitter_name": "Your name",
            "submitter_organization": "Organization",
            "submitter_email": "Email address",
        }
        help_texts = {
            "source_url": (
                "Optional. A public source helps the editorial team evaluate the request."
            ),
            "submitter_email": "Used only to follow up about this submission.",
        }
        widgets = {
            "details": forms.Textarea(attrs={"rows": 7}),
            "source_url": forms.URLInput(attrs={"placeholder": "https://"}),
        }

    def __init__(self, *args, asset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.asset = asset
        self.fields["kind"].choices = [
            ("", "Select a request type"),
            *UpdateSubmission.Kind.choices,
        ]
        if asset:
            self.fields["kind"].initial = UpdateSubmission.Kind.CORRECTION
            self.fields["kind"].disabled = True
            self.fields["subject"].initial = asset.public_name
            self.fields["subject"].disabled = True

    def clean_details(self):
        details = self.cleaned_data["details"].strip()
        if len(details) < 20:
            raise ValidationError(
                "Please provide enough detail for the editorial team to evaluate."
            )
        return details

    def clean_confirmation(self):
        if self.cleaned_data["confirmation"]:
            raise ValidationError("The submission could not be accepted.")
        return ""


class SavedViewForm(forms.ModelForm):
    class Meta:
        model = SavedView
        fields = ("name", "view_type", "query_string", "is_shared")
        widgets = {"query_string": forms.HiddenInput()}
        labels = {"is_shared": "Allow anyone with the link to open this view"}
