from django import forms
from django.core.exceptions import ValidationError

from apps.assets.models import UpdateSubmission


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
            self.fields["subject"].initial = asset.name
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
