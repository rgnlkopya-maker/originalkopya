from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import (
    Beden,
    DepoStok,
    Fasoncu,
    MesaiKayit,
    Musteri,
    Nakisci,
    Order,
    OrderEvent,
    ProductCost,
    Renk,
    UrunKod,
)


class Command(BaseCommand):
    help = "MoliApp demo kurulumu için güvenli ve tekrar çalıştırılabilir sahte veri oluşturur."

    def handle(self, *args, **options):
        if not getattr(settings, "DEMO_MODE", False):
            raise CommandError(
                "Güvenlik nedeniyle yalnızca DEMO_MODE=True olan ayrı demo ortamında çalışır."
            )

        User = get_user_model()
        now = timezone.now()
        today = timezone.localdate()

        demo_password = getattr(settings, "DEMO_PASSWORD", "MoliDemo2026!")
        demo_user, _ = User.objects.update_or_create(
            username="demo",
            defaults={
                "first_name": "Demo",
                "last_name": "Yönetici",
                "email": "demo@moliapp.example",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        demo_user.set_password(demo_password)
        demo_user.save()
        demo_user.userprofile.gorev = "yok"
        demo_user.userprofile.save(update_fields=["gorev"])

        staff_specs = [
            ("demo_kesim", "Elif", "Kaya", "kesim"),
            ("demo_dikim", "Zeynep", "Arslan", "dikim"),
            ("demo_susleme", "Merve", "Aydın", "susleme"),
            ("demo_hazir", "Can", "Demir", "hazir"),
            ("demo_sevkiyat", "Ece", "Şahin", "sevkiyat"),
        ]
        staff = {}
        for username, first_name, last_name, role in staff_specs:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{username}@moliapp.example",
                    "is_active": True,
                    "is_staff": False,
                    "is_superuser": False,
                },
            )
            user.set_unusable_password()
            user.save()
            user.userprofile.gorev = role
            user.userprofile.save(update_fields=["gorev"])
            staff[role] = user

        customers = {}
        for name in [
            "Luna Bridal Studio",
            "Maison Étoile",
            "Blanche İzmir",
            "Atelier Verona",
            "Nordic Bride Copenhagen",
        ]:
            customers[name], _ = Musteri.objects.update_or_create(
                ad=name, defaults={"aktif": True}
            )

        for name in ["Kırık Beyaz", "Şampanya", "Fildişi", "Pudra", "Beyaz"]:
            Renk.objects.update_or_create(ad=name, defaults={"aktif": True})
        for name in ["34", "36", "38", "40", "42", "44"]:
            Beden.objects.update_or_create(ad=name, defaults={"aktif": True})

        products = [
            ("ML-DREAM-01", "BALIK", Decimal("11800.00")),
            ("ML-LUNA-02", "HELEN", Decimal("9400.00")),
            ("ML-PEARL-03", "ETEKLI_BALIK", Decimal("12750.00")),
            ("ML-NOVA-04", "TESETTUR_HELEN", Decimal("13600.00")),
            ("ML-IVY-05", "DIGER", Decimal("8800.00")),
        ]
        for code, product_type, cost in products:
            UrunKod.objects.update_or_create(
                kod=code, defaults={"urun_tipi": product_type, "aktif": True}
            )
            ProductCost.objects.update_or_create(
                urun_kodu=code,
                defaults={"maliyet": cost, "para_birimi": "TRY", "is_active": True},
            )

        fason, _ = Fasoncu.objects.update_or_create(
            ad="Demo İnci İşleme",
            defaults={"telefon": "0500 000 00 01", "notlar": "Yalnızca demo verisidir."},
        )
        nakisci, _ = Nakisci.objects.update_or_create(
            ad="Demo Nakış Atölyesi",
            defaults={"telefon": "0500 000 00 02", "notlar": "Yalnızca demo verisidir."},
        )

        specs = [
            {
                "number": "DEMO0001", "customer": "Luna Bridal Studio", "code": "ML-DREAM-01",
                "type": "BALIK", "color": "Kırık Beyaz", "size": "36", "qty": 1,
                "order_days": -48, "delivery_days": -5, "price": "32800",
                "states": ("bitti", "bitti", "bitti", "bitti", "gonderildi"),
            },
            {
                "number": "DEMO0002", "customer": "Maison Étoile", "code": "ML-LUNA-02",
                "type": "HELEN", "color": "Şampanya", "size": "38", "qty": 2,
                "order_days": -32, "delivery_days": 7, "price": "29500",
                "states": ("bitti", "bitti", "basladi", "bekliyor", "bekliyor"),
            },
            {
                "number": "DEMO0003", "customer": "Blanche İzmir", "code": "ML-PEARL-03",
                "type": "ETEKLI_BALIK", "color": "Fildişi", "size": "40", "qty": 1,
                "order_days": -20, "delivery_days": 14, "price": "36200",
                "states": ("bitti", "basladi", "bekliyor", "bekliyor", "bekliyor"),
            },
            {
                "number": "DEMO0004", "customer": "Atelier Verona", "code": "ML-NOVA-04",
                "type": "TESETTUR_HELEN", "color": "Beyaz", "size": "42", "qty": 3,
                "order_days": -12, "delivery_days": 28, "price": "38900",
                "states": ("basladi", "bekliyor", "bekliyor", "bekliyor", "bekliyor"),
            },
            {
                "number": "DEMO0005", "customer": "Nordic Bride Copenhagen", "code": "ML-IVY-05",
                "type": "DIGER", "color": "Pudra", "size": "34", "qty": 1,
                "order_days": -6, "delivery_days": 45, "price": "27400",
                "states": ("bekliyor", "bekliyor", "bekliyor", "bekliyor", "bekliyor"),
            },
            {
                "number": "DEMO0006", "customer": "Luna Bridal Studio", "code": "ML-DREAM-01",
                "type": "BALIK", "color": "Fildişi", "size": "38", "qty": 2,
                "order_days": -25, "delivery_days": -2, "price": "33200",
                "states": ("bitti", "bitti", "basladi", "bekliyor", "bekliyor"),
            },
        ]

        created_orders = []
        for index, spec in enumerate(specs, start=1):
            kesim, dikim, susleme, hazir, sevkiyat = spec["states"]
            order, _ = Order.objects.update_or_create(
                siparis_numarasi=spec["number"],
                defaults={
                    "siparis_tipi": "OZEL" if index % 2 else "SERI",
                    "musteri": customers[spec["customer"]],
                    "musteri_referans": f"DEMO-REF-{100 + index}",
                    "siparis_tarihi": today + timedelta(days=spec["order_days"]),
                    "urun_kodu": spec["code"],
                    "urun_tipi": spec["type"],
                    "adet": spec["qty"],
                    "renk": spec["color"],
                    "beden": spec["size"],
                    "teslim_tarihi": today + timedelta(days=spec["delivery_days"]),
                    "aciklama": "Tanıtım için oluşturulmuş tamamen sahte sipariş.",
                    "kesim_durum": kesim,
                    "dikim_durum": dikim,
                    "susleme_durum": susleme,
                    "hazir_durum": hazir,
                    "sevkiyat_durum": sevkiyat,
                    "nakisci": nakisci if index in (2, 4) else None,
                    "nakis_durumu": "verildi" if index == 4 else ("alindi" if index == 2 else "yok"),
                    "susleme_fason": index == 3,
                    "susleme_fasoncu": fason if index == 3 else None,
                    "susleme_fason_durumu": "verildi" if index == 3 else None,
                    "satis_fiyati": Decimal(spec["price"]),
                    "para_birimi": "TRY",
                    "maliyet_uygulanan": dict((p[0], p[2]) for p in products)[spec["code"]],
                    "maliyet_para_birimi": "TRY",
                    "ekstra_maliyet": Decimal("1250.00") if index in (2, 3) else Decimal("0"),
                    "is_active": True,
                },
            )
            created_orders.append(order)

            OrderEvent.objects.filter(order=order, user__startswith="Demo ").delete()
            event_specs = []
            if kesim in ("basladi", "bitti"):
                event_specs.append(("kesim", "Kesim tamamlandı" if kesim == "bitti" else "Kesime başlandı", "Demo Elif"))
            if dikim in ("basladi", "bitti"):
                event_specs.append(("dikim", "Dikim tamamlandı" if dikim == "bitti" else "Dikime başlandı", "Demo Zeynep"))
            if susleme in ("basladi", "bitti"):
                event_specs.append(("susleme", "Süsleme tamamlandı" if susleme == "bitti" else "Süslemeye başlandı", "Demo Merve"))
            if hazir == "bitti":
                event_specs.append(("hazir", "Ürün kalite kontrolden geçti", "Demo Can"))
            if sevkiyat == "gonderildi":
                event_specs.append(("sevkiyat", "Müşteriye gönderildi", "Demo Ece"))
            for offset, (stage, value, actor) in enumerate(event_specs):
                OrderEvent.objects.create(
                    order=order,
                    user=actor,
                    gorev=stage,
                    stage=stage,
                    value=value,
                    adet=spec["qty"],
                    aciklama="Demo üretim hareketi",
                    timestamp=now - timedelta(days=max(1, 12 - offset * 2)),
                )

        DepoStok.objects.update_or_create(
            urun_kodu="ML-IVY-05",
            renk="Kırık Beyaz",
            beden="38",
            depo="SHOWROOM",
            defaults={"adet": 2, "aciklama": "Demo showroom stoğu"},
        )
        DepoStok.objects.update_or_create(
            urun_kodu="ML-LUNA-02",
            renk="Şampanya",
            beden="40",
            depo="KORIDOR",
            defaults={"adet": 4, "aciklama": "Demo hazır stok"},
        )

        for role, user in staff.items():
            MesaiKayit.objects.filter(user=user, giris_zamani__date__gte=today - timedelta(days=5)).delete()
            for day_offset in range(5):
                work_day = today - timedelta(days=day_offset)
                start = timezone.make_aware(
                    timezone.datetime.combine(work_day, timezone.datetime.min.time()).replace(hour=8, minute=30)
                )
                MesaiKayit.objects.create(
                    user=user,
                    giris_zamani=start,
                    cikis_zamani=start + timedelta(hours=8, minutes=45),
                )

        self.stdout.write(self.style.SUCCESS(
            f"Demo hazır: {len(created_orders)} sipariş, {len(customers)} müşteri, "
            f"{len(staff)} personel. Kullanıcı adı: demo"
        ))
