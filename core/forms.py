from app_settings.access import has_feature_access
from django import forms
from .models import Order, Musteri


# 🧾 SİPARİŞ FORMU
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            "siparis_tipi",
            "musteri",
            "musteri_referans",
            "siparis_tarihi",
            "urun_kodu",
            "urun_tipi",
            "renk",
            "beden",
            "adet",
            "teslim_tarihi",
            "aciklama",
            "resim",
            # 💰 Fiyat & Maliyet alanları
            "satis_fiyati",
            "vat_rate",
            "para_birimi",
            "maliyet_uygulanan",
            "maliyet_para_birimi",
            "maliyet_override",
            "ekstra_maliyet",
        ]
        widgets = {
            "siparis_tarihi": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d"
            ),
            "teslim_tarihi": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d"
            ),
            "aciklama": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "urun_kodu": forms.TextInput(attrs={"class": "form-control"}),
            "urun_tipi": forms.Select(attrs={"class": "form-control"}),
            "renk": forms.TextInput(attrs={"class": "form-control"}),
            "beden": forms.TextInput(attrs={"class": "form-control"}),
            "adet": forms.NumberInput(attrs={"class": "form-control"}),
            "siparis_tipi": forms.Select(attrs={"class": "form-control"}),
            "musteri": forms.Select(attrs={"class": "form-control"}),
            "satis_fiyati": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "vat_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "para_birimi": forms.Select(attrs={"class": "form-control"}),
            "maliyet_uygulanan": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "maliyet_para_birimi": forms.Select(attrs={"class": "form-control"}),
            "maliyet_override": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "ekstra_maliyet": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # 🧾 Yalnızca aktif müşterileri listede göster
        self.fields["musteri"].queryset = Musteri.objects.filter(aktif=True).order_by("ad")

        # 📌 Düzenleme modunda tarihlerin inputlarda görünmesi
        if self.instance and self.instance.pk:
            if self.instance.siparis_tarihi:
                self.fields["siparis_tarihi"].initial = self.instance.siparis_tarihi.strftime("%Y-%m-%d")
            if self.instance.teslim_tarihi:
                self.fields["teslim_tarihi"].initial = self.instance.teslim_tarihi.strftime("%Y-%m-%d")

        # 🧍 Kullanıcıyı sakla
        self.user = user

        if user and "siparis_tipi" in self.fields and not has_feature_access(user, "consignment.create_production"):
            self.fields["siparis_tipi"].choices = [
                choice for choice in self.fields["siparis_tipi"].choices
                if choice[0] != "KONSINYE"
            ]

        if user:
            if not has_feature_access(user, "orders.view_sale_price"):
                for field in ["satis_fiyati", "vat_rate", "para_birimi"]:
                    if field in self.fields:
                        self.fields[field].widget = forms.HiddenInput()
            elif not has_feature_access(user, "orders.edit_sale_price"):
                if "satis_fiyati" in self.fields:
                    self.fields["satis_fiyati"].disabled = True

            if not has_feature_access(user, "orders.view_cost"):
                for field in ["maliyet_uygulanan", "maliyet_para_birimi", "maliyet_override", "ekstra_maliyet"]:
                    if field in self.fields:
                        self.fields[field].widget = forms.HiddenInput()
            elif not has_feature_access(user, "orders.edit_cost"):
                for field in ["maliyet_uygulanan", "maliyet_para_birimi", "maliyet_override", "ekstra_maliyet"]:
                    if field in self.fields:
                        self.fields[field].disabled = True

            if "vat_rate" in self.fields and not has_feature_access(user, "orders.edit_vat"):
                self.fields["vat_rate"].disabled = True
            if "para_birimi" in self.fields and not has_feature_access(user, "orders.edit_vat"):
                self.fields["para_birimi"].disabled = True

            if self.instance and self.instance.pk:
                field_rules = {
                    "teslim_tarihi": "orders.edit_delivery_date",
                    "aciklama": "orders.edit_description",
                    "musteri_referans": "orders.edit_customer_ref",
                    "adet": "orders.edit_quantity",
                }
                for field_name, feature_key in field_rules.items():
                    if field_name in self.fields and not has_feature_access(user, feature_key):
                        self.fields[field_name].disabled = True

    def save(self, commit=True):
        instance = super().save(commit=False)

        user = getattr(self, 'user', None)

        if user and self.instance and self.instance.pk:
            preserve = []
            if not has_feature_access(user, "orders.edit_sale_price"):
                preserve.append("satis_fiyati")
            if not has_feature_access(user, "orders.edit_vat"):
                preserve.extend(["vat_rate", "para_birimi"])
            if not has_feature_access(user, "orders.edit_cost"):
                preserve.extend(["maliyet_uygulanan", "maliyet_para_birimi", "maliyet_override", "ekstra_maliyet"])
            field_rules = {
                "teslim_tarihi": "orders.edit_delivery_date",
                "aciklama": "orders.edit_description",
                "musteri_referans": "orders.edit_customer_ref",
                "adet": "orders.edit_quantity",
            }
            preserve.extend(field for field, feature in field_rules.items() if not has_feature_access(user, feature))
            for field in set(preserve):
                setattr(instance, field, getattr(self.instance, field, None))

        if commit:
            instance.save()
            if hasattr(self, "save_m2m"):
                self.save_m2m()

        return instance


# 👤 MÜŞTERİ FORMU
class MusteriForm(forms.ModelForm):
    class Meta:
        model = Musteri
        fields = ["ad"]
        widgets = {
            "ad": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Müşteri adı giriniz"
            }),
        }
