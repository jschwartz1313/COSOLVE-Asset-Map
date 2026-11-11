from django import forms

from apps.assets.operator_review import PUBLIC_FIELD_LIMITS, normalize_proposal, validate_public_url


class OperatorReviewForm(forms.Form):
    use_cases = forms.CharField(
        label="Use cases", max_length=PUBLIC_FIELD_LIMITS["use_cases"], required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    access_notes = forms.CharField(
        label="Access and operating requirements", max_length=PUBLIC_FIELD_LIMITS["access_notes"],
        required=False, widget=forms.Textarea(attrs={"rows": 4}),
    )
    contact_text = forms.CharField(
        label="Public contact or team", max_length=PUBLIC_FIELD_LIMITS["contact_text"],
        required=False,
    )
    contact_phone = forms.CharField(
        label="Public phone", max_length=PUBLIC_FIELD_LIMITS["contact_phone"], required=False,
        widget=forms.TextInput(attrs={"type": "tel"}),
    )
    contact_email = forms.EmailField(
        label="Public email", max_length=PUBLIC_FIELD_LIMITS["contact_email"], required=False,
    )
    contact_url = forms.CharField(
        label="Public contact URL", max_length=PUBLIC_FIELD_LIMITS["contact_url"], required=False,
        validators=[validate_public_url], widget=forms.URLInput(attrs={"placeholder": "https://"}),
    )
    submitter_name = forms.CharField(
        label="Your name (private)", max_length=120,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    submitter_email = forms.EmailField(
        label="Your email (private)", max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    publication_consent = forms.BooleanField(
        label=(
            "I am authorized to provide these details and consent to publication of the use cases, "
            "access information and public contact details above. My private name and email "
            "will not be published."
        ),
    )
    confirmation = forms.CharField(
        required=False, label="Leave this field blank",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    def clean_confirmation(self):
        if self.cleaned_data["confirmation"]:
            raise forms.ValidationError("The proposal could not be accepted.")
        return ""

    def clean(self):
        cleaned = super().clean()
        if not self.errors:
            cleaned["proposal"] = normalize_proposal({
                key: cleaned.get(key, "") for key in PUBLIC_FIELD_LIMITS
            })
        return cleaned

    def submit(self, review):
        if not self.is_valid():
            raise ValueError("A valid operator review form is required.")
        review.submit(**{
            key: self.cleaned_data[key] for key in (
                "proposal", "submitter_name", "submitter_email", "publication_consent",
            )
        })
