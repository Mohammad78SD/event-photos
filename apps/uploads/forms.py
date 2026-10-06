from django import forms
from django.core.exceptions import ValidationError

from .phone import normalize_iranian_mobile


class GuestForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        label="اسم و فامیل",
        widget=forms.TextInput(attrs={"class": "field-input"}),
    )
    phone = forms.CharField(
        max_length=20,
        label="شماره موبایل",
        widget=forms.TextInput(attrs={"class": "field-input", "inputmode": "numeric", "dir": "ltr"}),
    )
    message = forms.CharField(
        max_length=2000,
        label="یادداشت",
        required=False,
        widget=forms.Textarea(attrs={"class": "field-input h-24 py-3"}),
    )

    def clean_phone(self):
        try:
            return normalize_iranian_mobile(self.cleaned_data["phone"])
        except ValidationError as exc:
            raise forms.ValidationError(exc.message) from exc
