from django.db import models

from .models import Musteri


class CustomerDetail(models.Model):
    customer = models.OneToOneField(
        Musteri,
        on_delete=models.CASCADE,
        related_name="customer_detail",
    )
    yetkili_kisi = models.CharField(max_length=150, blank=True, default="")
    telefon = models.CharField(max_length=40, blank=True, default="")
    telefon_2 = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    ulke = models.CharField(max_length=100, blank=True, default="")
    adres = models.TextField(blank=True, default="")
    teslimat_adresi = models.TextField(blank=True, default="")
    fatura_adresi = models.TextField(blank=True, default="")
    dis_ticaret_firmasi = models.CharField(max_length=200, blank=True, default="")
    notlar = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Müşteri Detayı"
        verbose_name_plural = "Müşteri Detayları"

    def __str__(self):
        return f"{self.customer.ad} detayları"
