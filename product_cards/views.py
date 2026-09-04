from decimal import Decimal, InvalidOperation
import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from supabase import create_client

from core.models import UrunKod
from .models import Material, ProductCard, ProductMaterial


def _can_manage(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _upload_image(uploaded_file, folder, code):
    if not uploaded_file:
        return ""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase ayarları eksik.")

    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".jpg"
    safe_code = "".join(ch for ch in code if ch.isalnum() or ch in ("-", "_")) or "kart"
    path = f"{folder}/{safe_code}/{uuid.uuid4().hex}{ext}"

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    bucket = client.storage.from_(settings.SUPABASE_BUCKET_NAME)
    bucket.upload(
        path,
        uploaded_file.read(),
        file_options={
            "content-type": uploaded_file.content_type or "application/octet-stream",
            "upsert": "false",
        },
    )
    return bucket.get_public_url(path)


@login_required
def product_card_list(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    cards = ProductCard.objects.select_related("urun").prefetch_related("materials").order_by("urun__kod")
    q = (request.GET.get("q") or "").strip()
    if q:
        cards = cards.filter(urun__kod__icontains=q)
    return render(request, "product_cards/list.html", {"cards": cards, "q": q})


@login_required
def product_card_detail(request, card_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    card = get_object_or_404(ProductCard.objects.select_related("urun"), pk=card_id)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save_card":
            card.aciklama = (request.POST.get("aciklama") or "").strip()
            urun_tipi = (request.POST.get("urun_tipi") or "").strip()
            if urun_tipi:
                card.urun.urun_tipi = urun_tipi
                card.urun.save(update_fields=["urun_tipi"])

            uploaded_image = request.FILES.get("product_image")
            if uploaded_image:
                try:
                    card.image_url = _upload_image(uploaded_image, "product-cards", card.urun.kod)
                except Exception as exc:
                    messages.error(request, f"Ürün resmi yüklenemedi: {exc}")
                    return redirect("product_card_detail", card_id=card.id)

            if request.POST.get("remove_image") == "1":
                card.image_url = ""

            card.save()
            messages.success(request, "Ürün kartı güncellendi.")

        elif action == "add_material":
            material_id = request.POST.get("material_id")
            miktar_text = (request.POST.get("miktar") or "").replace(",", ".")
            try:
                miktar = Decimal(miktar_text)
                if miktar <= 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                messages.error(request, "Geçerli bir sarfiyat miktarı girin.")
                return redirect("product_card_detail", card_id=card.id)

            material = get_object_or_404(Material, pk=material_id, aktif=True)
            ProductMaterial.objects.update_or_create(
                product_card=card,
                material=material,
                defaults={
                    "miktar": miktar,
                    "notlar": (request.POST.get("notlar") or "").strip(),
                },
            )
            messages.success(request, "Malzeme reçeteye eklendi/güncellendi.")

        elif action == "remove_material":
            usage = get_object_or_404(ProductMaterial, pk=request.POST.get("usage_id"), product_card=card)
            usage.delete()
            messages.success(request, "Malzeme reçeteden kaldırıldı.")

        return redirect("product_card_detail", card_id=card.id)

    materials = Material.objects.filter(aktif=True).order_by("ad")
    usages = card.materials.select_related("material").all()
    return render(request, "product_cards/detail.html", {
        "card": card,
        "materials": materials,
        "usages": usages,
        "urun_tipi_choices": UrunKod._meta.get_field("urun_tipi").choices,
    })


@login_required
def material_list(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            kod = (request.POST.get("kod") or "").strip().upper()
            ad = (request.POST.get("ad") or "").strip()
            birim = (request.POST.get("birim") or "M").strip()
            stok_text = (request.POST.get("stok_miktari") or "0").replace(",", ".")
            try:
                stok = Decimal(stok_text)
            except (InvalidOperation, ValueError):
                stok = Decimal("0")

            if kod and ad:
                material, _ = Material.objects.update_or_create(
                    kod=kod,
                    defaults={"ad": ad, "birim": birim, "stok_miktari": stok, "aktif": True},
                )
                uploaded_image = request.FILES.get("material_image")
                if uploaded_image:
                    try:
                        material.image_url = _upload_image(uploaded_image, "material-cards", material.kod)
                        material.save(update_fields=["image_url"])
                    except Exception as exc:
                        messages.error(request, f"Malzeme resmi yüklenemedi: {exc}")
                        return redirect("material_list")
                messages.success(request, "Malzeme kartı kaydedildi.")

        elif action == "update_image":
            material = get_object_or_404(Material, pk=request.POST.get("id"), aktif=True)
            uploaded_image = request.FILES.get("material_image")
            if uploaded_image:
                try:
                    material.image_url = _upload_image(uploaded_image, "material-cards", material.kod)
                    material.save(update_fields=["image_url"])
                    messages.success(request, "Malzeme görseli güncellendi.")
                except Exception as exc:
                    messages.error(request, f"Malzeme resmi yüklenemedi: {exc}")
            elif request.POST.get("remove_image") == "1":
                material.image_url = ""
                material.save(update_fields=["image_url"])
                messages.success(request, "Malzeme görseli kaldırıldı.")

        elif action == "deactivate":
            material = get_object_or_404(Material, pk=request.POST.get("id"))
            material.aktif = False
            material.save(update_fields=["aktif"])
            messages.success(request, "Malzeme pasife alındı.")
        return redirect("material_list")

    materials = Material.objects.filter(aktif=True).order_by("ad")
    return render(request, "product_cards/material_list.html", {"materials": materials})
