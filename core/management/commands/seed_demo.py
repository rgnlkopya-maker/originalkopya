import os
import random
from datetime import timedelta, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from attendance.models import AttendanceRecord
from core.models import Musteri, Order, OrderEvent, UrunKod, Renk, Beden, ProductCost


class Command(BaseCommand):
    help = "Demo ortamini gercekci sahte verilerle doldurur. Sadece DEMO_MODE=1 ortaminda calisir."

    def handle(self, *args, **options):
        if os.getenv("DEMO_MODE") != "1" or os.getenv("DEMO_SEED_CONFIRM") != "YES":
            raise CommandError("Guvenlik nedeniyle yalnizca DEMO_MODE=1 ve DEMO_SEED_CONFIRM=YES ile calisir.")

        random.seed(20261003)
        User = get_user_model()

        today = timezone.localdate()
        tz = timezone.get_current_timezone()

        customer_names = [
            "Luna Bridal", "Maison Elise", "Novia Milano", "Atelier Rosa", "Belle Amour",
            "White Story", "Maison Lumiere", "Aurelia Bridal", "Noble Dress", "Velvet Bride",
            "Casa Noiva", "Elara Couture", "Milano Sposa", "La Perla Moda", "Amore Atelier",
            "Narin Bridal", "Serena Moda", "Vera Sposa", "Mira Couture", "Elysian Bridal",
        ]
        customers = [Musteri.objects.get_or_create(ad=name, defaults={"aktif": True})[0] for name in customer_names]

        product_types = ["BALIK", "HELEN", "ETEKLI_BALIK", "TESETTUR_BALIK", "TESETTUR_ETEKLI_BALIK", "TESETTUR_HELEN"]
        products = []
        for i in range(1, 31):
            code = f"DM-{2400 + i}"
            product, _ = UrunKod.objects.get_or_create(kod=code, defaults={"urun_tipi": product_types[(i - 1) % len(product_types)], "aktif": True})
            products.append(product)
            ProductCost.objects.get_or_create(
                urun_kodu=code,
                defaults={"maliyet": Decimal(str(random.randrange(4500, 11500))), "para_birimi": "TRY", "is_active": True},
            )

        for color in ["Ekru", "Beyaz", "Siyah", "Pudra", "Lacivert", "Zeytin", "Gul Kurusu", "Bordo"]:
            Renk.objects.get_or_create(ad=color, defaults={"aktif": True})
        for size in ["34", "36", "38", "40", "42", "44", "46", "48"]:
            Beden.objects.get_or_create(ad=size, defaults={"aktif": True})

        staff = [
            ("demo", "Demo", "Patron", "yok"),
            ("selin", "Selin", "Aras", "kesim"),
            ("mert", "Mert", "Akin", "kesim"),
            ("aylin", "Aylin", "Kara", "dikim"),
            ("derya", "Derya", "Sen", "dikim"),
            ("esra", "Esra", "Yildiz", "dikim"),
            ("nisa", "Nisa", "Eren", "susleme"),
            ("melis", "Melis", "Kaya", "susleme"),
            ("ece", "Ece", "Demir", "susleme"),
            ("burak", "Burak", "Tas", "hazir"),
            ("deniz", "Deniz", "Acar", "sevkiyat"),
            ("arda", "Arda", "Gunes", "nakis"),
        ]
        staff_users = []
        for username, first, last, role in staff:
            user, created = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last})
            if created:
                user.set_password("MoliDemo2026!")
                user.save()
            profile = user.userprofile
            profile.gorev = role
            profile.save(update_fields=["gorev"])
            staff_users.append(user)

        if not Order.objects.filter(siparis_numarasi__startswith="DMO").exists():
            stages = ["kesim", "dikim", "susleme", "hazir", "sevkiyat"]
            colors = ["Ekru", "Beyaz", "Siyah", "Pudra", "Lacivert", "Zeytin", "Gul Kurusu", "Bordo"]
            sizes = ["34", "36", "38", "40", "42", "44", "46", "48"]

            for i in range(1, 181):
                product = random.choice(products)
                customer = random.choice(customers)
                order_date = today - timedelta(days=random.randint(3, 150))
                due_date = order_date + timedelta(days=random.randint(18, 55))
                progress = random.choices([0, 1, 2, 3, 4, 5], weights=[7, 14, 22, 24, 18, 15], k=1)[0]
                qty = random.randint(1, 12)
                sale_price = Decimal(str(random.randrange(9500, 24500)))

                order = Order.objects.create(
                    siparis_tipi=random.choice(["OZEL", "SERI", "TEKLI", "STOK", "KONSINYE"]),
                    siparis_numarasi=f"DMO{i:05d}",
                    musteri=customer,
                    musteri_referans=f"{customer.ad[:3].upper()}-{random.randint(1000,9999)}",
                    siparis_tarihi=order_date,
                    urun_kodu=product.kod,
                    urun_tipi=product.urun_tipi,
                    adet=qty,
                    renk=random.choice(colors),
                    beden=random.choice(sizes),
                    teslim_tarihi=due_date,
                    aciklama=random.choice([
                        "Standart uretim", "Omuz detayi kontrol", "Musteri provalı",
                        "Acil sevkiyat", "Tas dagilimi kontrol edilecek", "Yedek aksesuar eklenecek", ""
                    ]),
                    satis_fiyati=sale_price,
                    para_birimi="TRY",
                    maliyet_uygulanan=ProductCost.objects.get(urun_kodu=product.kod).maliyet,
                    maliyet_para_birimi="TRY",
                )

                event_base = timezone.make_aware(
                    timezone.datetime.combine(order_date, time(hour=9, minute=random.randint(0, 40))),
                    tz,
                )

                if progress >= 1:
                    order.kesim_durum = "bitti"
                    order.kesim_yapan = random.choice(["Selin Aras", "Mert Akin"])
                    order.kesim_tarihi = event_base
                    OrderEvent.objects.create(order=order, user=order.kesim_yapan, gorev="kesim", stage="kesim_durum", value="bitti", adet=qty, timestamp=event_base)
                if progress >= 2:
                    t = event_base + timedelta(days=random.randint(1, 4))
                    order.dikim_durum = "bitti"
                    order.dikim_yapan = random.choice(["Aylin Kara", "Derya Sen", "Esra Yildiz"])
                    order.dikim_tarihi = t
                    OrderEvent.objects.create(order=order, user=order.dikim_yapan, gorev="dikim", stage="dikim_durum", value="bitti", adet=qty, timestamp=t)
                if progress >= 3:
                    t = event_base + timedelta(days=random.randint(4, 9))
                    order.susleme_durum = "bitti"
                    order.susleme_yapan = random.choice(["Nisa Eren", "Melis Kaya", "Ece Demir"])
                    order.susleme_tarihi = t
                    OrderEvent.objects.create(order=order, user=order.susleme_yapan, gorev="susleme", stage="susleme_durum", value="bitti", adet=qty, timestamp=t)
                if progress >= 4:
                    t = event_base + timedelta(days=random.randint(8, 13))
                    order.hazir_durum = "bitti"
                    order.hazir_yapan = "Burak Tas"
                    order.hazir_tarihi = t
                    OrderEvent.objects.create(order=order, user="Burak Tas", gorev="hazir", stage="hazir_durum", value="bitti", adet=qty, timestamp=t)
                if progress >= 5:
                    t = event_base + timedelta(days=random.randint(11, 18))
                    order.sevkiyat_durum = "gonderildi"
                    order.sevkiyat_yapan = "Deniz Acar"
                    order.sevkiyat_tarihi = t
                    OrderEvent.objects.create(order=order, user="Deniz Acar", gorev="sevkiyat", stage="sevkiyat_durum", value="gonderildi", adet=qty, timestamp=t)
                order.save()

        work_users = [u for u in staff_users if u.username != "demo"]
        for days_ago in range(1, 61):
            day = today - timedelta(days=days_ago)
            if day.weekday() >= 5:
                continue
            for user in work_users:
                if AttendanceRecord.objects.filter(user=user, work_date=day).exists():
                    continue
                if random.random() < 0.04:
                    AttendanceRecord.objects.create(user=user, work_date=day, status="leave", note="Demo izin kaydi")
                    continue
                late = random.choice([0, 0, 0, 0, 2, 4, 7, 11])
                overtime = random.choice([0, 0, 0, 15, 30, 45])
                check_in_naive = timezone.datetime.combine(day, time(8, 30)) + timedelta(minutes=late)
                check_out_naive = timezone.datetime.combine(day, time(19, 0)) + timedelta(minutes=overtime)
                AttendanceRecord.objects.create(
                    user=user,
                    work_date=day,
                    status="worked",
                    check_in=timezone.make_aware(check_in_naive, tz),
                    check_out=timezone.make_aware(check_out_naive, tz),
                    late_minutes=late,
                    overtime_minutes=overtime,
                )

        self.stdout.write(self.style.SUCCESS(
            f"Demo veri hazir: {Musteri.objects.count()} musteri, {Order.objects.count()} siparis, {User.objects.count()} kullanici."
        ))
