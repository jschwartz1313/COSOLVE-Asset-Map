from django import forms

from apps.assets.manufacturing import (
    ACCESS_CHOICES,
    MATERIAL_CHOICES,
    PROCESS_CHOICES,
    SERVICE_MODE_CHOICES,
)


class ManufacturingSearchForm(forms.Form):
    process = forms.ChoiceField(
        label="Process", required=False, choices=[("", "Any process"), *PROCESS_CHOICES]
    )
    material = forms.ChoiceField(
        label="Material", required=False, choices=[("", "Any material"), *MATERIAL_CHOICES]
    )
    mode = forms.ChoiceField(
        label="Service mode", required=False,
        choices=[("", "Any service mode"), *SERVICE_MODE_CHOICES],
    )
    access = forms.ChoiceField(
        label="Documented access", required=False,
        choices=[("", "Any access condition"), *ACCESS_CHOICES],
    )
    outcome = forms.ChoiceField(
        label="Results", required=False,
        choices=[
            ("", "All outcomes"),
            ("match", "Documented criteria match"),
            ("unknown", "Needs confirmation"),
        ],
    )
