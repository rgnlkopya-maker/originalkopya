from django import forms
from .models import Prospect
from .research import canonical_url, draft_for


class ProspectForm(forms.ModelForm):
    class Meta:
        model = Prospect
        fields = [
            "name", "country", "city", "website_url", "instagram_url",
            "status", "note", "message_draft", "next_followup_on",
        ]
        widgets = {
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
