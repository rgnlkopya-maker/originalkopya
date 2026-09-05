from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from core.models import Order, OrderEvent, ProductCost, UrunKod


CURRENCY_CHOICES = [("TRY", "TL"), ("USD", "USD")]


class ExchangeRate(models.Model):
    rate_date = models.DateField(unique=True)
    usd_try = models.DecimalField(max_digits=12, decimal_places=6)
    source_date = models.CharField(max_length=20, blank=True, default="")
    fetched_at = models.DateTimeField(auto_now=True)
    class Meta: ordering = ["-rate_date"]
    @classmethod
    def latest_usd_try(cls):
        obj = cls.objects.order_by("-rate_date", "-fetched_at").first()
        return obj.usd_try if obj else Decimal("1")
    def __str__(self): return f"{self.rate_date} USD/TRY {self.usd_try}"


def to_try(amount, currency):
    amount = amount or Decimal("0")
    return amount * ExchangeRate.latest_usd_try() if currency == "USD" else amount


def amount_to_try(amount, currency, usd_try):
    if amount is None: return None
    amount = Decimal(amount)
    return amount * usd_try if currency == "USD" and usd_try else (None if currency == "USD" else amount)


class OrderFinancialSnapshot(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="financial_snapshot")
    usd_try = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    satis_fiyati = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    satis_para_birimi = models.CharField(max_length=3, default="TRY")
    satis_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    maliyet_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    beklenen_kar_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    beklenen_kar_orani = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.order.siparis_numarasi} - siparis gunu finans"


class ShipmentFinancialSnapshot(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipment_financial_snapshot")
    usd_try = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    satis_fiyati = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    satis_para_birimi = models.CharField(max_length=3, default="TRY")
    satis_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    urun_maliyeti_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    sevkiyat_ekstra_maliyet_tl = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    toplam_maliyet_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    gerceklesen_kar_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    gerceklesen_kar_orani = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notlar = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.order.siparis_numarasi} - sevkiyat gunu finans"


@receiver(post_save, sender=Order)
def create_order_financial_snapshot(sender, instance, created, **kwargs):
    if not created: return
    rate_obj = ExchangeRate.objects.order_by("-rate_date", "-fetched_at").first(); usd_try = rate_obj.usd_try if rate_obj else None
    satis = instance.satis_fiyati; curr = instance.para_birimi or "TRY"; satis_tl = amount_to_try(satis, curr, usd_try) if satis is not None else None
    cost_available = instance.maliyet_override is not None
    effective = Decimal(instance.maliyet_override) if instance.maliyet_override is not None else None
    if effective is None and instance.maliyet_uygulanan is not None:
        exists = ProductCost.objects.filter(urun_kodu__iexact=instance.urun_kodu or "", is_active=True).exists()
        if exists or Decimal(instance.maliyet_uygulanan or 0) != 0: effective = Decimal(instance.maliyet_uygulanan or 0); cost_available = True
    maliyet_tl = None
    if cost_available and effective is not None:
        maliyet_tl = amount_to_try(effective + Decimal(instance.ekstra_maliyet or 0), instance.maliyet_para_birimi or "TRY", usd_try)
    kar = satis_tl - maliyet_tl if satis_tl is not None and maliyet_tl is not None else None
    oran = kar / satis_tl * 100 if kar is not None and satis_tl else None
    OrderFinancialSnapshot.objects.get_or_create(order=instance, defaults={"usd_try":usd_try,"satis_fiyati":satis,"satis_para_birimi":curr,"satis_tl":satis_tl.quantize(Decimal('.01')) if satis_tl is not None else None,"maliyet_tl":maliyet_tl.quantize(Decimal('.01')) if maliyet_tl is not None else None,"beklenen_kar_tl":kar.quantize(Decimal('.01')) if kar is not None else None,"beklenen_kar_orani":oran.quantize(Decimal('.01')) if oran is not None else None})


@receiver(post_save, sender=OrderEvent)
def create_shipment_financial_snapshot(sender, instance, created, **kwargs):
    if not created or instance.stage != "sevkiyat_durum" or instance.value != "gonderildi": return
    order=instance.order
    if ShipmentFinancialSnapshot.objects.filter(order=order).exists(): return
    rate=ExchangeRate.objects.order_by("-rate_date","-fetched_at").first(); usd=rate.usd_try if rate else None
    satis=Decimal(order.satis_fiyati) if order.satis_fiyati is not None else None; curr=order.para_birimi or "TRY"; satis_tl=amount_to_try(satis,curr,usd)
    pc=ProductCost.objects.filter(urun_kodu__iexact=order.urun_kodu or "",is_active=True).first()
    if order.maliyet_override is not None: cost=Decimal(order.maliyet_override); cc=order.maliyet_para_birimi or "TRY"
    elif pc: cost=Decimal(pc.maliyet); cc=pc.para_birimi or "TRY"
    elif order.maliyet_uygulanan is not None: cost=Decimal(order.maliyet_uygulanan); cc=order.maliyet_para_birimi or "TRY"
    else: cost=None; cc="TRY"
    ct=amount_to_try(cost,cc,usd); extra=amount_to_try(Decimal(order.ekstra_maliyet or 0),cc,usd) or Decimal("0"); total=ct+extra if ct is not None else None
    kar=satis_tl-total if satis_tl is not None and total is not None else None; oran=kar/satis_tl*100 if kar is not None and satis_tl else None
    ShipmentFinancialSnapshot.objects.create(order=order,usd_try=usd,satis_fiyati=satis,satis_para_birimi=curr,satis_tl=satis_tl.quantize(Decimal('.01')) if satis_tl is not None else None,urun_maliyeti_tl=ct.quantize(Decimal('.01')) if ct is not None else None,sevkiyat_ekstra_maliyet_tl=extra.quantize(Decimal('.01')),toplam_maliyet_tl=total.quantize(Decimal('.01')) if total is not None else None,gerceklesen_kar_tl=kar.quantize(Decimal('.01')) if kar is not None else None,gerceklesen_kar_orani=oran.quantize(Decimal('.01')) if oran is not None else None)


class ProductCard(models.Model):
    urun=models.OneToOneField(UrunKod,on_delete=models.CASCADE,related_name="product_card"); aciklama=models.TextField(blank=True,default=""); image_url=models.URLField(blank=True,default="")
    finansman_maliyeti=models.DecimalField(max_digits=14,decimal_places=2,default=0); finansman_para_birimi=models.CharField(max_length=3,choices=CURRENCY_CHOICES,default="TRY")
    nakis_maliyeti=models.DecimalField(max_digits=14,decimal_places=2,default=0); nakis_para_birimi=models.CharField(max_length=3,choices=CURRENCY_CHOICES,default="TRY")
    genel_gider=models.DecimalField(max_digits=14,decimal_places=2,default=0); genel_gider_para_birimi=models.CharField(max_length=3,choices=CURRENCY_CHOICES,default="TRY")
    iscilik_maliyeti=models.DecimalField(max_digits=14,decimal_places=2,default=0); iscilik_para_birimi=models.CharField(max_length=3,choices=CURRENCY_CHOICES,default="TRY")
    paketleme_maliyeti=models.DecimalField(max_digits=14,decimal_places=2,default=0); paketleme_para_birimi=models.CharField(max_length=3,choices=CURRENCY_CHOICES,default="TRY")
    diger_maliyet=models.DecimalField(max_digits=14,decimal_places=2,default=0); diger_maliyet_para_birimi=models.CharField(max_length=3,choices=CURRENCY_CHOICES,default="TRY")
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    @property
    def malzeme_maliyeti(self): return sum((u.satir_maliyeti for u in self.materials.select_related("material").all()),Decimal("0"))
    @property
    def finansman_maliyeti_tl(self): return to_try(self.finansman_maliyeti,self.finansman_para_birimi)
    @property
    def nakis_maliyeti_tl(self): return to_try(self.nakis_maliyeti,self.nakis_para_birimi)
    @property
    def genel_gider_tl(self): return to_try(self.genel_gider,self.genel_gider_para_birimi)
    @property
    def iscilik_maliyeti_tl(self): return to_try(self.iscilik_maliyeti,self.iscilik_para_birimi)
    @property
    def paketleme_maliyeti_tl(self): return to_try(self.paketleme_maliyeti,self.paketleme_para_birimi)
    @property
    def toplam_maliyet(self): return self.malzeme_maliyeti+self.finansman_maliyeti_tl+self.nakis_maliyeti_tl+self.genel_gider_tl+self.iscilik_maliyeti_tl+self.paketleme_maliyeti_tl
    def __str__(self): return f"Ürün Kartı - {self.urun.kod}"


class Material(models.Model):
    UNIT_CHOICES=[("M","Metre"),("ADET","Adet"),("KG","Kilogram"),("GR","Gram")]
    CATEGORY_CHOICES=[("KUMAS","Kumaş"),("TUL","Tül"),("DANTEL","Dantel"),("ASTAR","Astar"),("TAS","Taş / Boncuk"),("FERMUAR","Fermuar / Aksesuar"),("DIGER","Diğer")]
    kod=models.CharField(max_length=80,unique=True); ad=models.CharField(max_length=160); kategori=models.CharField(max_length=20,choices=CATEGORY_CHOICES,default="DIGER"); birim=models.CharField(max_length=10,choices=UNIT_CHOICES,default="M")
    stok_miktari=models.DecimalField(max_digits=14,decimal_places=3,default=0); kritik_stok=models.DecimalField(max_digits=14,decimal_places=3,default=0); tedarikci=models.CharField(max_length=160,blank=True,default=""); aciklama=models.TextField(blank=True,default="")
    birim_maliyet=models.DecimalField(max_digits=14,decimal_places=4,default=0); birim_maliyet_para_birimi=models.CharField(max_length=3,choices=CURRENCY_CHOICES,default="TRY"); son_alis_tarihi=models.DateField(null=True,blank=True); image_url=models.URLField(blank=True,default=""); aktif=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    @property
    def birim_maliyet_tl(self): return to_try(self.birim_maliyet,self.birim_maliyet_para_birimi)
    @property
    def kritik_mi(self): return self.kritik_stok>0 and self.stok_miktari<=self.kritik_stok
    def __str__(self): return f"{self.kod} - {self.ad}"


class MaterialStockMovement(models.Model):
    MOVEMENT_CHOICES=[("GIRIS","Stok Girişi"),("CIKIS","Stok Çıkışı"),("IADE","İade Girişi"),("FIRE","Fire / Zayi"),("DUZELTME_ARTI","Sayım Düzeltmesi +"),("DUZELTME_EKSI","Sayım Düzeltmesi -"),("BASLANGIC","Başlangıç Stoğu"),("URETIM","Üretim Tüketimi"),("URETIM_IADE","Üretim İadesi")]
    material=models.ForeignKey(Material,on_delete=models.PROTECT,related_name="stock_movements"); movement_type=models.CharField(max_length=20,choices=MOVEMENT_CHOICES); miktar=models.DecimalField(max_digits=14,decimal_places=3); onceki_stok=models.DecimalField(max_digits=14,decimal_places=3); sonraki_stok=models.DecimalField(max_digits=14,decimal_places=3); aciklama=models.CharField(max_length=255,blank=True,default=""); islem_yapan=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="material_stock_movements"); order=models.ForeignKey(Order,on_delete=models.SET_NULL,null=True,blank=True,related_name="material_stock_movements"); source_event=models.ForeignKey(OrderEvent,on_delete=models.SET_NULL,null=True,blank=True,related_name="material_stock_movements"); reversed=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at","-id"]
    @property
    def signed_amount(self): return -self.miktar if self.movement_type in {"CIKIS","FIRE","DUZELTME_EKSI","URETIM"} else self.miktar
    def __str__(self): return f"{self.material.kod} - {self.get_movement_type_display()} - {self.miktar}"


class ProductMaterial(models.Model):
    STAGE_CHOICES=[("KESIM","Kesim Malzemesi"),("SUSLEME","Süsleme Malzemesi")]
    product_card=models.ForeignKey(ProductCard,on_delete=models.CASCADE,related_name="materials")
    material=models.ForeignKey(Material,on_delete=models.PROTECT,related_name="product_usages")
    miktar=models.DecimalField(max_digits=12,decimal_places=3)
    kullanim_asamasi=models.CharField(max_length=12,choices=STAGE_CHOICES,default="KESIM")
    notlar=models.CharField(max_length=255,blank=True,default="")
    class Meta: constraints=[models.UniqueConstraint(fields=["product_card","material"],name="unique_product_material")]; ordering=["material__ad"]
    @property
    def satir_maliyeti(self): return self.miktar*self.material.birim_maliyet_tl
    def __str__(self): return f"{self.product_card.urun.kod} - {self.material.ad}: {self.miktar}"


def _stock_stage_for_event(instance):
    if instance.event_type != "stage" or instance.value != "bitti": return None
    if instance.stage == "kesim_durum": return "KESIM"
    if instance.stage == "susleme_durum": return "SUSLEME"
    return None


@receiver(post_save, sender=OrderEvent)
def consume_materials_on_stage_completion(sender, instance, created, **kwargs):
    stage = _stock_stage_for_event(instance)
    if not created or not stage: return
    if MaterialStockMovement.objects.filter(order=instance.order,source_event__stage=instance.stage,movement_type="URETIM",reversed=False).exists(): return
    try: card=ProductCard.objects.get(urun__kod__iexact=instance.order.urun_kodu)
    except ProductCard.DoesNotExist: return
    usages=list(card.materials.select_related("material").filter(kullanim_asamasi=stage))
    if not usages: return
    multiplier=Decimal(instance.order.adet or 1)
    with transaction.atomic():
        locked=[]
        for usage in usages:
            material=Material.objects.select_for_update().get(pk=usage.material_id)
            qty=(usage.miktar*multiplier).quantize(Decimal("0.001"))
            if material.stok_miktari < qty: return
            locked.append((material,qty))
        stage_label="kesim" if stage=="KESIM" else "süsleme"
        for material,qty in locked:
            before=material.stok_miktari; after=before-qty; material.stok_miktari=after; material.save(update_fields=["stok_miktari","updated_at"])
            MaterialStockMovement.objects.create(material=material,movement_type="URETIM",miktar=qty,onceki_stok=before,sonraki_stok=after,aciklama=f"{instance.order.siparis_numarasi} {stage_label} reçetesi tüketimi",order=instance.order,source_event=instance)


@receiver(pre_delete, sender=OrderEvent)
def restore_materials_when_stage_deleted(sender, instance, **kwargs):
    stage = _stock_stage_for_event(instance)
    if not stage: return
    movements=list(MaterialStockMovement.objects.filter(source_event=instance,movement_type="URETIM",reversed=False).select_related("material"))
    if not movements: return
    with transaction.atomic():
        stage_label="Kesildi" if stage=="KESIM" else "Süsleme Bitti"
        for movement in movements:
            material=Material.objects.select_for_update().get(pk=movement.material_id); before=material.stok_miktari; after=before+movement.miktar; material.stok_miktari=after; material.save(update_fields=["stok_miktari","updated_at"])
            MaterialStockMovement.objects.create(material=material,movement_type="URETIM_IADE",miktar=movement.miktar,onceki_stok=before,sonraki_stok=after,aciklama=f"{instance.order.siparis_numarasi} {stage_label} kaydı silindi; stok iade edildi",order=instance.order)
            movement.reversed=True; movement.save(update_fields=["reversed"])
