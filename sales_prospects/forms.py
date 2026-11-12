from django import forms
from .models import Prospect
from .research import canonical_url, draft_for


class ProspectForm(forms.ModelForm):
    class Meta:
        model = Prospect
        fields = [
            "name", "country", "city", "website_url", "instagram_url",
            "status", "note", "message_draft", "next_followup_on",
            "email", "contact_class", "email_basis", "email_source_note", "email_checked",
        ]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "sales@magaza.com"}),
            "contact_class": forms.Select(attrs={"class": "form-select"}),
            "email_basis": forms.Select(attrs={"class": "form-select"}),
            "email_source_note": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "İletişim izni veya B2B değerlendirme kaynağı / tarih"}),
            "email_checked": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.Select(attrs={"class": "form-select"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "website_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://instagram.com/..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "message_draft": forms.Textarea(attrs={"class": "form-control", "rows": 7}),
            "next_followup_on": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def clean(self):
        data = super().clean()
        if data.get("email"):
            data["email"] = data["email"].strip().casefold()
        url = data.get("instagram_url") or data.get("website_url")
        if not url:
            raise forms.ValidationError("Mağazanın web sitesi veya Instagram bağlantısı gerekli.")
        key = canonical_url(url)
        if not key:
            raise forms.ValidationError("Geçerli mağaza veya Instagram profil bağlantısı girin.")
        existing = Prospect.objects.filter(canonical_url=key)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("Bu mağaza zaten müşteri adayları arasında kayıtlı.")
        data["canonical_url"] = key
        return data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.canonical_url = self.cleaned_data["canonical_url"]
        if not instance.message_draft:
            instance.message_draft = draft_for(instance.name, instance.country)
        if commit:
            instance.save()
        return instance
