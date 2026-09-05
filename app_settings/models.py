from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class SystemSettings(models.Model):
    company_name = models.CharField(max_length=160, default="Moli Tekstil")
    company_phone = models.CharField(max_length=40, blank=True, default="")
    company_email = models.EmailField(blank=True, default="")
    company_address = models.TextField(blank=True, default="")

    default_order_type = models.CharField(
        max_length=20,
        choices=[("SERI", "Seri"), ("TEKLI", "Tekli Sipariş"), ("STOK", "Stoğa Üretim"), ("OZEL", "Özel Sipariş")],
        default="SERI",
    )
    default_delivery_days = models.PositiveIntegerField(default=30)

    default_currency = models.CharField(
        max_length=3,
        choices=[("TRY", "TRY"), ("USD", "USD"), ("EUR", "EUR")],
        default="TRY",
    )
    tcmb_update_hour = models.PositiveSmallIntegerField(default=9)
    finance_enabled = models.BooleanField(default=True)

    # Depolar sayfasında aktif olarak gösterilecek depo kodları.
    # Virgülle ayrılmış tutulur; mevcut stok depoları ilk açılışta otomatik eklenir.
    active_depots = models.TextField(blank=True, default="")

    quality_categories = models.TextField(
        default="Dikiş hatası\nÖlçü / beden\nKumaş\nSüsleme\nLeke\nYanlış ürün\nPaketleme\nDiğer"
    )

    notify_late_orders = models.BooleanField(default=True)
    notify_upcoming_delivery = models.BooleanField(default=True)
    notify_open_quality_issue = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Moli Sistem Ayarları"


class UserAccess(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="moli_access")

    # Yeni normal kullanıcılar güvenli personel profiliyle başlar:
    # yalnız siparişleri görür ve üretim panelini kullanır.
    can_view_orders = models.BooleanField(default=True)
    can_create_orders = models.BooleanField(default=False)
    can_edit_orders = models.BooleanField(default=False)
    can_update_production = models.BooleanField(default=True)
    can_delete_orders = models.BooleanField(default=False)

    can_view_depots = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_view_costs = models.BooleanField(default=False)
    can_view_personnel = models.BooleanField(default=False)
    can_view_attendance = models.BooleanField(default=False)
    can_view_assistant = models.BooleanField(default=False)
    can_manage_quality = models.BooleanField(default=False)
    can_view_shipping_finance = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_view_settings = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} yetkileri"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_access(sender, instance, created, **kwargs):
    if created:
        UserAccess.objects.get_or_create(user=instance)
