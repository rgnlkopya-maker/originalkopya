from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal, ROUND_CEILING


User = get_user_model()


# 👤 Kullanıcı Profili (Görev)
class UserProfile(models.Model):
    GOREV_SECENEKLERI = [
        ("yok", "Yok"),
        ("kesim", "Kesim"),
        ("dikim", "Dikim"),
        ("susleme", "Süsleme"),
        ("hazir", "Hazır"),
        ("sevkiyat", "Sevkiyat"),
        ("nakis", "Nakış"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="userprofile")
    gorev = models.CharField(max_length=20, choices=GOREV_SECENEKLERI, default="yok")

    # 👇 Bunu ekliyoruz!
    last_seen_orders = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} ({self.gorev})"


# 🔔 Kullanıcı oluşturulunca profilini aç
@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_profile_for_user(sender, instance, **kwargs):
    UserProfile.objects.get_or_create(user=instance)


# 💰 Para birimi seçenekleri
CURRENCY_CHOICES = (
    ("TRY", "TRY"),
    ("USD", "USD"),
    ("EUR", "EUR"),
)

URUN_TIPI_CHOICES = (
    ("BALIK", "Balık"),
    ("HELEN", "Helen"),
    ("ETEKLI_BALIK", "Etekli Balık"),
    ("TESETTUR_BALIK", "Tesettür Balık"),
    ("TESETTUR_ETEKLI_BALIK", "Tesettür Etekli Balık"),
    ("TESETTUR_HELEN", "Tesettür Helen"),
    ("DIGER", "Diğer"),
)


# 💵 Ürün Maliyeti Modeli
class ProductCost(models.Model):
    urun_kodu = models.CharField(max_length=100, unique=True)
    maliyet = models.DecimalField(max_digits=12, decimal_places=2)
    para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return f"{self.urun_kodu} - {self.maliyet} {self.para_birimi}"


class Musteri(models.Model):
    ad = models.CharField(max_length=200, db_index=True)
    aktif = models.BooleanField(default=True)   # 👈 EKLENDİ!

    def __str__(self):
        return self.ad


class CustomerPricingRule(models.Model):
    customer = models.OneToOneField(
        Musteri,
        on_delete=models.CASCADE,
        related_name="pricing_rule",
    )
    active = models.BooleanField(default=True)
    base_size = models.PositiveSmallIntegerField(default=38)
    base_hip_max = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("102"))
    hip_step = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("4"))
    size_step = models.PositiveSmallIntegerField(default=2)
    price_group_size = models.PositiveSmallIntegerField(default=3)
    price_step = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("250"))

    def size_for_hip(self, hip_measurement):
        hip = Decimal(str(hip_measurement))
        if hip <= self.base_hip_max:
            return self.base_size
        steps = ((hip - self.base_hip_max) / self.hip_step).to_integral_value(rounding=ROUND_CEILING)
        return self.base_size + int(steps) * self.size_step

    def price_adjustment_for_size(self, size):
        size_position = max(0, (int(size) - self.base_size) // self.size_step)
        group_number = size_position // self.price_group_size + 1
        return self.price_step * group_number

    def calculate(self, hip_measurement, base_price):
        size = self.size_for_hip(hip_measurement)
        adjustment = self.price_adjustment_for_size(size)
        return size, adjustment, Decimal(str(base_price)) + adjustment

    def __str__(self):
        return f"{self.customer.ad} özel fiyat kuralı"


def _normalized_customer_name(value):
    return "".join(character for character in (value or "").upper() if character.isalnum())


@receiver(post_save, sender=Musteri)
def create_modazehra_pricing_rule(sender, instance, **kwargs):
    if _normalized_customer_name(instance.ad) in {"MODAZEHRA", "MODAZEHRADA"}:
        CustomerPricingRule.objects.get_or_create(customer=instance)


class Nakisci(models.Model):
    ad = models.CharField(max_length=100)
    telefon = models.CharField(max_length=20, blank=True, null=True)
    notlar = models.TextField(blank=True, null=True)
    eklenme_tarihi = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ad



class Fasoncu(models.Model):
    ad = models.CharField(max_length=100)
    telefon = models.CharField(max_length=20, blank=True, null=True)
    notlar = models.TextField(blank=True, null=True)
    eklenme_tarihi = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ad

class Renk(models.Model):
    ad = models.CharField(max_length=100, unique=True)
    aktif = models.BooleanField(default=True)

    def __str__(self):
        return self.ad


class Beden(models.Model):
    ad = models.CharField(max_length=20, unique=True)
    aktif = models.BooleanField(default=True)

    def __str__(self):
        return self.ad


class UrunKod(models.Model):
    kod = models.CharField(max_length=100, unique=True)
    urun_tipi = models.CharField(
        max_length=30, choices=URUN_TIPI_CHOICES, blank=True, default=""
    )
    aktif = models.BooleanField(default=True)

    def __str__(self):
        return self.kod



class Order(models.Model):
    SIPARIS_TIPLERI = [
        ('OZEL', 'Özel'),
        ('SERI', 'Seri'),
        ('TEKLI', 'Tekli Sipariş'),
        ('STOK', 'Stoğa Üretim'),
        ('KONSINYE', 'Konsinye')
    ]

    siparis_tipi = models.CharField(max_length=20, choices=SIPARIS_TIPLERI, null=True, blank=True, db_index=True)
    siparis_numarasi = models.CharField(max_length=20, unique=True, blank=True, db_index=True)
    musteri = models.ForeignKey('Musteri', on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    musteri_referans = models.CharField(max_length=150, blank=True, null=True, verbose_name="Müşteri Sipariş Referansı")

    siparis_tarihi = models.DateField(default=timezone.now, null=True, blank=True, db_index=True)
    urun_kodu = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    urun_tipi = models.CharField(
        max_length=30, choices=URUN_TIPI_CHOICES, blank=True, default="", db_index=True
    )
    adet = models.PositiveIntegerField(null=True, blank=True)
    renk = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    beden = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    teslim_tarihi = models.DateField(null=True, blank=True, db_index=True)
    aciklama = models.TextField(blank=True, null=True)
    resim = models.ImageField(upload_to='siparis_resimleri/', blank=True, null=True)

    qr_code_url = models.URLField(blank=True, null=True)

    kesim_yapan = models.CharField(max_length=100, blank=True, null=True)
    kesim_tarihi = models.DateTimeField(blank=True, null=True)
    dikim_yapan = models.CharField(max_length=100, blank=True, null=True)
    dikim_tarihi = models.DateTimeField(blank=True, null=True)
    susleme_yapan = models.CharField(max_length=100, blank=True, null=True)
    susleme_tarihi = models.DateTimeField(blank=True, null=True)
    hazir_yapan = models.CharField(max_length=100, blank=True, null=True)
    hazir_tarihi = models.DateTimeField(blank=True, null=True)
    sevkiyat_yapan = models.CharField(max_length=100, blank=True, null=True)
    sevkiyat_tarihi = models.DateTimeField(blank=True, null=True)
    cikti_alindi = models.BooleanField(default=False)

    DURUM_SECENEKLERI = [
        ('bekliyor', 'Bekliyor'),
        ('basladi', 'Başladı'),
        ('bitti', 'Bitti'),
    ]

    kesim_durum = models.CharField(max_length=20, choices=DURUM_SECENEKLERI, default='bekliyor')
    dikim_durum = models.CharField(max_length=20, choices=DURUM_SECENEKLERI, default='bekliyor')
    susleme_durum = models.CharField(max_length=20, choices=DURUM_SECENEKLERI, default='bekliyor')
    hazir_durum = models.CharField(max_length=20, choices=DURUM_SECENEKLERI, default='bekliyor')
    sevkiyat_durum = models.CharField(
        max_length=20,
        choices=[
            ('bekliyor', 'Bekliyor'),
            ('hazirlaniyor', 'Hazırlanıyor'),
            ('gonderildi', 'Gönderildi')
        ],
        default='bekliyor'
    )

    dikim_fason = models.BooleanField(default=False)
    dikim_fasoncu = models.ForeignKey(Fasoncu, on_delete=models.SET_NULL, null=True, blank=True, related_name='dikim_fasonlari')
    dikim_fason_durumu = models.CharField(max_length=20, choices=[('verildi', 'Verildi'), ('alindi', 'Alındı')], blank=True, null=True)

    susleme_fason = models.BooleanField(default=False)
    susleme_fasoncu = models.ForeignKey(Fasoncu, on_delete=models.SET_NULL, null=True, blank=True, related_name='susleme_fasonlari')
    susleme_fason_durumu = models.CharField(max_length=20, choices=[('verildi', 'Verildi'), ('alindi', 'Alındı')], blank=True, null=True)

    nakisci = models.ForeignKey(Nakisci, on_delete=models.SET_NULL, null=True, blank=True, related_name='nakis_siparisleri')
    nakis_durumu = models.CharField(max_length=20, choices=[('yok', 'Yok'), ('verildi', 'Nakışa Verildi'), ('alindi', 'Nakıştan Alındı')], default='yok')

    satis_fiyati = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vat_rate = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name="KDV Oranı (%)",
    )
    customer_base_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    customer_price_adjustment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    hip_measurement = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    customer_pricing_rule = models.CharField(max_length=150, blank=True, default="")
    para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    maliyet_uygulanan = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    maliyet_para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    maliyet_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    ekstra_maliyet = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)




    @property
    def is_stok_siparis(self) -> bool:
        return self.siparis_tipi == 'STOK'

    @property
    def is_ozel_siparis(self) -> bool:
        return self.siparis_tipi == 'OZEL'

    @property
    def is_seri_siparis(self) -> bool:
        return self.siparis_tipi == 'SERI'

    @property
    def is_tekli_siparis(self) -> bool:
        return self.siparis_tipi == 'TEKLI'

    @property
    def is_konsinye_siparis(self) -> bool:
        return self.siparis_tipi == 'KONSINYE'


    

    @property
    def efektif_maliyet(self):
        """Override varsa override; yoksa maliyet_uygulanan; yoksa 0."""
        if self.maliyet_override is not None:
            return Decimal(self.maliyet_override)

        if self.maliyet_uygulanan is not None:
            return Decimal(self.maliyet_uygulanan)

        return Decimal(0)

    @property
    def toplam_maliyet(self):
        """Etkin maliyet + ekstra maliyet"""
        ekstra = Decimal(self.ekstra_maliyet or 0)
        return self.efektif_maliyet + ekstra

    @property
    def kar_backend(self):
        """Satış fiyatı yoksa None"""
        if not self.satis_fiyati:
            return None

        return Decimal(self.satis_fiyati) - self.toplam_maliyet

    @property
    def kar(self):
        """
        Net kâr:
        satış fiyatı - toplam_maliyet (efektif + ekstra)
        """
        return self.kar_backend

    @property
    def son_durum(self):
        """Siparişin genel durumunu (özetini) döner."""
        if self.sevkiyat_durum == "gonderildi":
            return "Sevkiyat Tamamlandı ✅"
        elif self.hazir_durum == "bitti":
            return "Hazırlık Tamamlandı"
        elif self.susleme_durum == "bitti":
            return "Süsleme Tamamlandı"
        elif self.dikim_durum == "bitti":
            return "Dikim Tamamlandı"
        elif self.kesim_durum == "bitti":
            return "Kesim Tamamlandı"
        else:
            return "Bekliyor ⏳"






    def save(self, *args, **kwargs):
        creating = self._state.adding

        # Ürün tipi elle seçilmediyse ürün kodunun varsayılan tipini kullan.
        if self.urun_kodu and not self.urun_tipi:
            urun = UrunKod.objects.filter(kod__iexact=self.urun_kodu).first()
            if urun:
                self.urun_tipi = urun.urun_tipi

        if creating and not self.siparis_numarasi:

            # ⭐ ÖZEL siparişler düzeltme
            siparis_tipi = (self.siparis_tipi or "").upper()
            if siparis_tipi == "OZEL":
                prefix = "OZEL"
                real_type_list = ["OZEL"]
            else:
                prefix = siparis_tipi or "SP"
                real_type_list = [self.siparis_tipi] if self.siparis_tipi else []

            # ⭐ En son numarayı doğru bul
            last_order = Order.objects.filter(
                siparis_tipi__in=real_type_list
            ).order_by("id").last()

            if last_order and last_order.siparis_numarasi:
                try:
                    num = int(''.join(filter(str.isdigit, last_order.siparis_numarasi))) + 1
                except ValueError:
                    num = 1
            else:
                num = 1

            # ⭐ Yeni numara oluştur
            self.siparis_numarasi = f"{prefix}{num:04d}"

        super().save(*args, **kwargs)

        
class MesaiKayit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    giris_zamani = models.DateTimeField(null=True, blank=True)
    cikis_zamani = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.giris_zamani}"


class OrderImage(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='extra_images')
    image = models.ImageField(upload_to='temp_uploads/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    image_url = models.URLField(blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


# 📜 ÜRETİM GEÇMİŞİ
class OrderEvent(models.Model):
    GOREV_SECENEKLERI = UserProfile.GOREV_SECENEKLERI

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    user = models.CharField(max_length=100)
    gorev = models.CharField(max_length=20, choices=GOREV_SECENEKLERI, default="yok")
    stage = models.CharField(max_length=100)
    value = models.CharField(max_length=200)
    adet = models.PositiveIntegerField(default=1)
    parca = models.CharField(max_length=100, blank=True, null=True)
    aciklama = models.TextField(blank=True, null=True)
    ortak_calisanlar = models.CharField(max_length=255, blank=True, null=True)
    fasoncu = models.ForeignKey(Fasoncu, on_delete=models.SET_NULL, null=True, blank=True)
    nakisci = models.ForeignKey(Nakisci, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    # 🆕 Sipariş düzenleme logları için
    event_type = models.CharField(
        max_length=20,
        choices=[
            ("stage", "Aşama Güncellemesi"),
            ("order_update", "Sipariş Güncellemesi"),
        ],
        default="stage"
    )

    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.order} | {self.stage} → {self.value} ({self.user})"

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["user"]),
            models.Index(fields=["stage"]),
            models.Index(fields=["event_type"]),
        ]



# 🏬 DEPO STOK MODELİ
class DepoStok(models.Model):
    DEPO_SECENEKLERI = [
        ('KORIDOR', 'Koridor'),
        ('SHOWROOM', 'Showroom'),
        ('SHOWROOM_MUTF', 'Showroom Mutfak'),
        ('DANTEL_YANI', 'Dantel Odası Yanı'),
        ('ELISI', 'Elişi Deposu'),
    ]

    urun_kodu = models.CharField(max_length=100, db_index=True)
    renk = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    beden = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    adet = models.PositiveIntegerField(default=0)
    depo = models.CharField(max_length=20, choices=DEPO_SECENEKLERI, default='KORIDOR')
    aciklama = models.TextField(blank=True, null=True)
    eklenme_tarihi = models.DateTimeField(auto_now_add=True)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='stok_kaydi')

    def __str__(self):
        return f"{self.urun_kodu} - {self.renk}/{self.beden} ({self.depo}) [{self.adet} adet]"


class ConsignmentStock(models.Model):
    customer = models.ForeignKey(Musteri, on_delete=models.PROTECT, related_name="consignment_stocks")
    source_order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="consignment_source_stocks")
    urun_kodu = models.CharField(max_length=100, db_index=True)
    renk = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    beden = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    quantity_sent = models.PositiveIntegerField(default=1)
    quantity_remaining = models.PositiveIntegerField(default=1)
    cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cost_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)
    note = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="consignment_stocks_created")

    class Meta:
        ordering = ["sent_at", "id"]
        indexes = [models.Index(fields=["customer", "urun_kodu", "renk", "beden"])]

    def __str__(self):
        return f"{self.customer} - {self.urun_kodu} {self.renk or ''}/{self.beden or ''} ({self.quantity_remaining})"


class ConsignmentMovement(models.Model):
    TYPES = (("IN", "Konsinye Giriş"), ("USE", "Siparişte Kullanıldı"), ("RETURN", "İade"))
    stock = models.ForeignKey(ConsignmentStock, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=10, choices=TYPES)
    quantity = models.PositiveIntegerField(default=1)
    target_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="consignment_movements")
    source_event = models.ForeignKey(OrderEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="consignment_movements")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-id"]


class UretimGecmisi(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="uretim_kayitlari"
    )
    urun = models.CharField(max_length=100)
    asama = models.CharField(max_length=100)
    aciklama = models.TextField(blank=True, null=True)
    tarih = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.urun} - {self.asama}"



class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notification_set")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)

    title = models.CharField(max_length=255)
    message = models.TextField(blank=True, null=True)

    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} → {self.title}"




class OrderSeen(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    seen_time = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'order')

    def __str__(self):
        return f"{self.user} → {self.order}"

class AuditLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    username_snapshot = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=160)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    object_ref = models.CharField(max_length=200, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    status_code = models.PositiveSmallIntegerField(default=200)
    success = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="core_audit_user_created_idx"),
            models.Index(fields=["action", "created_at"], name="core_audit_action_created_idx"),
        ]

    def __str__(self):
        actor = self.username_snapshot or "Bilinmeyen kullanıcı"
        return f"{actor} · {self.action} · {self.created_at:%d.%m.%Y %H:%M}"


class ChatThread(models.Model):
    TYPE_CHOICES = (("direct", "Birebir"), ("group", "Grup"))

    thread_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="direct", db_index=True)
    name = models.CharField(max_length=160, blank=True, default="")
    direct_key = models.CharField(max_length=80, blank=True, null=True, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_chat_threads")
    only_admins_can_message = models.BooleanField(default=False)
    pinned_message = models.ForeignKey("ChatMessage", on_delete=models.SET_NULL, null=True, blank=True, related_name="pinned_in_threads")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.name or self.direct_key or f"Sohbet {self.pk}"


class ChatMembership(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_memberships")
    is_admin = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["thread", "user"], name="unique_chat_thread_user")
        ]

    def __str__(self):
        return f"{self.thread_id} · {self.user.username}"


class ChatMessage(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_chat_messages")
    body = models.TextField()
    importance = models.CharField(
        max_length=10,
        choices=(("normal", "Normal"), ("important", "Önemli"), ("urgent", "Acil")),
        default="normal",
    )
    linked_path = models.CharField(max_length=500, blank=True, default="")
    linked_label = models.CharField(max_length=180, blank=True, default="")
    reply_to = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies")
    forwarded_from = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="forwards")
    media_url = models.URLField(blank=True, default="")
    media_type = models.CharField(max_length=20, blank=True, default="")
    media_name = models.CharField(max_length=255, blank=True, default="")
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.thread_id} · {self.sender_id} · {self.created_at}"


class ChatReadState(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="read_states")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_read_states")
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["thread", "user"], name="unique_chat_read_state")
        ]

    def __str__(self):
        return f"{self.thread_id} · {self.user.username}"


class ChatMessageEdit(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="edit_history")
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    old_body = models.TextField(blank=True, default="")
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["edited_at", "id"]


class ChatReaction(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_reactions")
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "user", "emoji"], name="unique_chat_reaction")
        ]


class ChatStar(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="stars")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_stars")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="unique_chat_star")
        ]


class ChatHiddenMessage(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="hidden_for")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="hidden_chat_messages")
    hidden_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="unique_chat_hidden_message")
        ]


class ChatPoll(models.Model):
    message = models.OneToOneField(ChatMessage, on_delete=models.CASCADE, related_name="poll")
    question = models.CharField(max_length=300)
    multiple_choice = models.BooleanField(default=False)


class ChatPollOption(models.Model):
    poll = models.ForeignKey(ChatPoll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=200)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class ChatPollVote(models.Model):
    option = models.ForeignKey(ChatPollOption, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_poll_votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["option", "user"], name="unique_chat_poll_option_user")
        ]


class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user"], name="core_push_user_idx")]

    def __str__(self):
        return f"{self.user.username} · {self.endpoint[:60]}"
