import os
import logging
from decimal import Decimal, InvalidOperation
from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.models import Order, Musteri
from .invoice_models import InvoiceDraft, InvoiceLine, BizimHesapCustomerMapping, BizimHesapInvoiceTransfer
from planning.models import ShipmentPlan
from core.services.order_status import latest_status_event, status_label, FINANCIAL_STAGES


def _allowed(user):
    from app_settings.access import has_full_access
    return has_full_access(user)


def _pending_shipments_by_invoice():
    """Batch-check latest production statuses without one query per invoice row."""
    from core.models import OrderEvent
    invoice_orders = list(InvoiceLine.objects.values_list("invoice_id", "order_id"))
    if not invoice_orders:
        return {}
    order_ids = {order_id for _, order_id in invoice_orders}
    # PostgreSQL DISTINCT ON returns just the latest relevant event per order.
    latest = OrderEvent.objects.filter(order_id__in=order_ids).exclude(
        event_type="order_update"
    ).exclude(stage__in=FINANCIAL_STAGES).order_by(
        "order_id", "-timestamp", "-id"
    ).distinct("order_id").values_list("order_id", "stage", "value")
    shipped = {order_id for order_id, stage, value in latest
               if stage == "sevkiyat_durum" and value in ("gonderildi", "tekrar_gonderildi")}
    pending = {}
    for invoice_id, order_id in invoice_orders:
        if order_id not in shipped:
            pending[invoice_id] = True
    return pending


@login_required
def invoice_list(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    invoices = list(InvoiceDraft.objects.select_related("customer").prefetch_related("lines").order_by("-invoice_date", "-id"))
    pending = _pending_shipments_by_invoice()
    for invoice in invoices:
        invoice.has_pending_shipment = pending.get(invoice.id, False)
    return render(request, "product_cards/invoice_list.html", {"invoices": invoices})


@login_required
def invoice_customer_mapping_list(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    customers = list(Musteri.objects.filter(aktif=True).order_by("ad").prefetch_related("bizimhesap_mapping"))
    mappings = {m.customer_id: m.external_customer_id for m in BizimHesapCustomerMapping.objects.filter(customer_id__in=[c.id for c in customers])}
    for customer in customers:
        customer.bh_code = mappings.get(customer.id, "")
    return render(request, "product_cards/invoice_customer_mapping.html", {
        "customers": customers,
        "mapped_count": len(mappings),
        "customer_count": len(customers),
    })


@login_required
def invoice_bizimhesap_customers(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .bizimhesap_client import list_customers, BizimHesapError
    try:
        customers = list_customers()
    except BizimHesapError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=503)
    return JsonResponse({"ok": True, "customers": customers})


@login_required
@require_POST
def invoice_customer_mapping_save(request, customer_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    customer = get_object_or_404(Musteri, pk=customer_id)
    code = request.POST.get("external_customer_id", "").strip()
    if not code or len(code) > 100 or any(ord(ch) < 32 for ch in code):
        messages.error(request, "Geçerli bir BizimHesap cari kodu girin.")
        return redirect("invoice_customer_mapping_list")
    try:
        with transaction.atomic():
            if BizimHesapCustomerMapping.objects.filter(external_customer_id=code).exclude(customer=customer).exists():
                messages.error(request, "Bu cari kodu başka bir müşteriye eşleştirilmiş.")
                return redirect("invoice_customer_mapping_list")
            BizimHesapCustomerMapping.objects.update_or_create(
                customer=customer,
                defaults={"external_customer_id": code, "confirmed_by": request.user},
            )
    except IntegrityError:
        messages.error(request, "Bu cari kodu zaten başka bir müşteride kullanılıyor.")
        return redirect("invoice_customer_mapping_list")
    messages.success(request, f"{customer.ad}: Cari eşleştirmesi kaydedildi.")
    return redirect("invoice_customer_mapping_list")


@login_required
def invoice_list_shipment_status(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    pending = _pending_shipments_by_invoice()
    return JsonResponse({"pending_invoice_ids": list(pending)})


@login_required
@require_POST
def invoice_delete_empty(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if invoice.status != "DRAFT" or invoice.lines.exists():
            messages.error(request, "Yalnızca boş taslak faturalar silinebilir.")
            return redirect("invoice_list")
        invoice.delete()
    messages.success(request, "Boş fatura taslağı silindi.")
    return redirect("invoice_list")


@login_required
def invoice_detail(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    invoice = get_object_or_404(InvoiceDraft.objects.select_related("customer"), pk=invoice_id)
    lines = list(invoice.lines.select_related("order").order_by("id"))
    for line in lines:
        line.current_status = status_label(latest_status_event(line.order))
        line.total_with_vat = (line.price * (Decimal("1") + line.vat_rate / Decimal("100"))).quantize(Decimal("0.01"))
    subtotal = sum((line.price for line in lines), Decimal("0"))
    tax = sum((line.price * line.vat_rate / Decimal("100") for line in lines), Decimal("0"))
    return render(request, "product_cards/invoice_detail.html", {"invoice": invoice, "lines": lines, "subtotal": subtotal, "tax": tax, "total": subtotal + tax})


@login_required
@require_POST
def invoice_due_date_save(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if invoice.status != "DRAFT":
            return HttpResponseForbidden("Yalnızca taslak faturanın vadesi değiştirilebilir.")
        raw = request.POST.get("due_date", "").strip()
        try:
            due = date.fromisoformat(raw)
        except (ValueError, TypeError):
            messages.error(request, "Geçerli bir vade tarihi seçin.")
            return redirect("invoice_detail", invoice_id=invoice_id)
        if due < invoice.invoice_date:
            messages.error(request, "Vade tarihi fatura tarihinden önce olamaz.")
            return redirect("invoice_detail", invoice_id=invoice_id)
        if BizimHesapInvoiceTransfer.objects.filter(invoice=invoice, status__in=("SENT", "SENDING", "UNKNOWN")).exists():
            messages.error(request, "Aktarım kaydı bulunan faturanın vadesi değiştirilemez.")
            return redirect("invoice_detail", invoice_id=invoice_id)
        invoice.due_date = due
        invoice.save(update_fields=["due_date", "updated_at"])
    messages.success(request, "Fatura vade tarihi kaydedildi.")
    return redirect("invoice_detail", invoice_id=invoice_id)


@login_required
def invoice_bizimhesap_preview(request, invoice_id):
    """Read-only preview. Never calls BizimHesap or writes to the database."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    invoice = get_object_or_404(InvoiceDraft.objects.select_related("customer"), pk=invoice_id)
    lines = list(invoice.lines.select_related("order").order_by("id"))
    currency = {"TRY": "TL", "TL": "TL", "USD": "USD", "EUR": "EUR", "GBP": "GBP", "CHF": "CHF"}.get(invoice.currency)
    details = []
    for line in lines:
        net = line.price
        tax = (net * line.vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        details.append({
            "product": line.order.urun_kodu,
            "order_number": line.order.siparis_numarasi,
            "description": " / ".join(str(v) for v in (line.order.renk, line.order.beden) if v),
            "reference": line.order.musteri_referans or "",
            "note": line.order.aciklama or "",
            "quantity": 1,
            "unit_price": net,
            "vat_rate": line.vat_rate,
            "net": net,
            "tax": tax,
            "total": net + tax,
        })
    net_total = sum((item["net"] for item in details), Decimal("0"))
    tax_total = sum((item["tax"] for item in details), Decimal("0"))
    warnings = []
    if not details:
        warnings.append("Faturada ürün satırı bulunmuyor.")
    if not currency:
        warnings.append("Para birimi BizimHesap formatı için tanımlı değil.")
    mapping = BizimHesapCustomerMapping.objects.filter(customer=invoice.customer).first()
    if mapping is None:
        warnings.append("BizimHesap cari kodu henüz eşleştirilmedi; aktarım kapalı.")
    transfer = BizimHesapInvoiceTransfer.objects.filter(invoice=invoice).first()
    if transfer and transfer.status in ("SENT", "SENDING", "UNKNOWN"):
        warnings.append("Bu fatura için önceden aktarım işlemi var; mükerrer gönderim engellenecek.")
    if invoice.status != "DRAFT":
        warnings.append("Bu kayıt MoliApp üzerinde tamamlanmış; yeni aktarım öncesi kontrol gerekli.")
    if any(item["vat_rate"] < 0 or item["vat_rate"] > 100 for item in details):
        warnings.append("Geçersiz KDV oranı tespit edildi.")
    # AddInvoice creates an invoice; the documentation does not define a draft mode.
    # Show blockers before enabling any external write.
    api_checks = [
        ("Cari eşleştirmesi", bool(mapping), "Kayıtlı cari kodu" if mapping else "Cari kodu eşleştirilmeli"),
        ("Fatura satırları", bool(details), str(len(details)) + " ürün satırı"),
        ("Para birimi", bool(currency), currency or "Desteklenmeyen para birimi"),
        ("KDV", bool(details) and all(Decimal("0") <= item["vat_rate"] <= Decimal("100") for item in details), "Oranlar kontrol edildi"),
        ("FirmId", bool((os.environ.get("BIZIMHESAP_FIRM_ID") or os.environ.get("BIZIMHESAP_API_TOKEN") or "").strip()), "API Key (FirmID) mevcut" if (os.environ.get("BIZIMHESAP_FIRM_ID") or os.environ.get("BIZIMHESAP_API_TOKEN") or "").strip() else "BizimHesap API anahtarı tanımlanmalı"),
        ("Vade tarihi", True, (invoice.due_date or invoice.invoice_date).strftime("%d.%m.%Y") + (" (otomatik)" if not invoice.due_date else "")),
        ("Ürün aktarımı", True, "MoliApp ürün kodları kullanılır; BizimHesap eksik ürünleri oluşturabilir"),
        ("Taslak durumu", False, "AddInvoice için taslak parametresi belgelenmemiş"),
    ]
    from .bizimhesap_payload import build_invoice_payload
    try:
        prepared_payload, payload_blockers = build_invoice_payload(
            invoice, lines, mapping, (os.environ.get("BIZIMHESAP_FIRM_ID") or os.environ.get("BIZIMHESAP_API_TOKEN") or "").strip()
        )
    except Exception as exc:
        logging.getLogger(__name__).exception("BizimHesap invoice preview preparation failed for invoice id=%s", invoice.pk)
        prepared_payload = None
        payload_blockers = ["Aktarım hazırlığı sırasında teknik hata oluştu. Fatura gönderilmedi."]
    if transfer and transfer.status in ("SENT", "SENDING", "UNKNOWN"):
        payload_blockers.append("Bu fatura için aktarım kaydı var.")
        prepared_payload = None
    payload_summary = None
    if prepared_payload:
        payload_summary = {
            "customer": prepared_payload["customer"]["title"],
            "customer_id": prepared_payload["customer"]["customerId"],
            "item_count": len(prepared_payload["details"]),
            "currency": prepared_payload["amounts"]["currency"],
            "total": prepared_payload["amounts"]["total"],
            "due_date": invoice.due_date or invoice.invoice_date,
        }
    warnings.append("BizimHesap'ta taslak ve cari bakiye davranışı henüz doğrulanmadı; gönderim kapalı.")
    return render(request, "product_cards/invoice_bizimhesap_preview.html", {
        "invoice": invoice, "details": details, "currency": currency or invoice.currency,
        "net_total": net_total, "tax_total": tax_total, "grand_total": net_total + tax_total,
        "warnings": warnings, "mapping": mapping, "transfer": transfer, "api_checks": api_checks, "payload_summary": payload_summary, "payload_blockers": payload_blockers,
    })


@login_required
@require_POST
def invoice_bizimhesap_customer_map(request, invoice_id):
    """Manually map an existing BizimHesap cari code. No external API writes."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    invoice = get_object_or_404(InvoiceDraft, pk=invoice_id)
    customer_code = request.POST.get("external_customer_id", "").strip()
    if not customer_code or len(customer_code) > 100 or any(ord(c) < 32 for c in customer_code):
        messages.error(request, "Geçerli bir BizimHesap cari kodu girin.")
        return redirect("invoice_bizimhesap_preview", invoice_id=invoice.pk)
    existing = BizimHesapCustomerMapping.objects.filter(external_customer_id=customer_code).exclude(customer=invoice.customer).first()
    if existing:
        messages.error(request, "Bu cari kodu başka bir MoliApp müşterisine eşleştirilmiş.")
        return redirect("invoice_bizimhesap_preview", invoice_id=invoice.pk)
    try:
        BizimHesapCustomerMapping.objects.update_or_create(
            customer=invoice.customer,
            defaults={"external_customer_id": customer_code, "confirmed_by": request.user},
        )
    except IntegrityError:
        messages.error(request, "Cari kodu başka bir müşteri tarafından kullanılıyor.")
        return redirect("invoice_bizimhesap_preview", invoice_id=invoice.pk)
    messages.success(request, "Cari kodu eşleştirmesi kaydedildi. BizimHesap'a fatura gönderilmedi.")
    return redirect("invoice_bizimhesap_preview", invoice_id=invoice.pk)


@login_required
def invoice_live_status(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    invoice = get_object_or_404(InvoiceDraft, pk=invoice_id)
    order_ids = list(invoice.lines.values_list("order_id", flat=True))
    from core.models import OrderEvent
    from core.services.order_status import FINANCIAL_STAGES
    events = (OrderEvent.objects.filter(order_id__in=order_ids)
              .exclude(event_type="order_update")
              .exclude(stage__in=FINANCIAL_STAGES)
              .order_by("-timestamp", "-id"))
    latest = {}
    for event in events:
        if event.order_id not in latest:
            latest[event.order_id] = status_label(event)
    return JsonResponse({"statuses": {str(order_id): latest.get(order_id, "-") for order_id in order_ids}})


@login_required
@require_POST
def invoice_add(request, order_id):
    from app_settings.access import has_feature_access
    if not has_feature_access(request.user, "orders.invoice_transfer"):
        return HttpResponseForbidden("Yetkiniz yok.")
    try:
        planned_date = date.fromisoformat(request.POST.get("planned_date", ""))
    except (ValueError, TypeError):
        messages.error(request, "Geçerli bir sevkiyat tarihi seçin.")
        return redirect("order_detail", pk=order_id)
    if planned_date.weekday() >= 5:
        messages.error(request, "Sevkiyat planında yalnızca hafta içi günleri bulunuyor.")
        return redirect("order_detail", pk=order_id)
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
        if not order.musteri_id:
            messages.error(request, "Müşteri kaydı olmayan sipariş faturaya eklenemez.")
            return redirect("order_detail", pk=order.pk)
        if InvoiceLine.objects.filter(order=order).exists() or ShipmentPlan.objects.filter(order=order).exists():
            messages.warning(request, "Bu sipariş zaten faturaya aktarılmış.")
            return redirect("order_detail", pk=order.pk)
        currency = order.para_birimi or "TRY"
        invoice, _ = InvoiceDraft.objects.get_or_create(customer=order.musteri, invoice_date=planned_date, currency=currency, status="DRAFT", defaults={"created_by": request.user})
        InvoiceLine.objects.create(invoice=invoice, order=order, price=order.satis_fiyati or 0, vat_rate=order.vat_rate or 0)
        ShipmentPlan.objects.create(order=order, planned_date=planned_date, created_by=request.user)
    messages.success(request, "Sipariş faturaya ve sevkiyat planına eklendi.")
    return redirect("order_detail", pk=order_id)


@login_required
@require_POST
def invoice_remove(request, invoice_id, line_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if invoice.status != "DRAFT":
            return HttpResponseForbidden("Tamamlanmış faturadan sipariş çıkarılamaz.")
        line = get_object_or_404(InvoiceLine, pk=line_id, invoice=invoice)
        order_id = line.order_id
        line.delete()
        ShipmentPlan.objects.filter(order_id=order_id).delete()
    messages.success(request, "Sipariş faturadan ve sevkiyat planından çıkarıldı; tekrar aktarılabilir.")
    return redirect("invoice_detail", invoice_id=invoice.pk)


@login_required
@require_POST
def invoice_price(request, invoice_id, line_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if invoice.status != "DRAFT":
            return HttpResponseForbidden("Tamamlanmış faturada fiyat değiştirilemez.")
        line = get_object_or_404(InvoiceLine.objects.select_for_update().select_related("order"), pk=line_id, invoice=invoice)
        try:
            price = Decimal(request.POST.get("price", "").replace(",", "."))
            if not price.is_finite() or price < 0:
                raise InvalidOperation
            price = price.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            messages.error(request, "Geçersiz fiyat.")
            return redirect("invoice_detail", invoice_id=invoice.pk)
        previous = line.order.satis_fiyati
        line.price = price
        line.save(update_fields=["price"])
        order = line.order
        order.satis_fiyati = price
        order.save(update_fields=["satis_fiyati", "last_updated"])
        from core.models import OrderEvent
        OrderEvent.objects.create(order=order, user=request.user.username, gorev="yok", stage="satis_fiyati", value="fatura_duzeltme", aciklama=f"Fatura taslağı #{invoice.pk}: {previous} -> {price} {invoice.currency}", event_type="order_update")
    messages.success(request, "Fiyat siparişe ve finans özetine işlendi; orijinal föy korunuyor.")
    return redirect("invoice_detail", invoice_id=invoice.pk)


@login_required
@require_POST
def invoice_finalize(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    invoice = get_object_or_404(InvoiceDraft, pk=invoice_id, status="DRAFT")
    number = request.POST.get("official_number", "").strip()
    if not number or not invoice.lines.exists():
        messages.error(request, "Fatura numarası ve en az bir ürün gerekli.")
    else:
        invoice.official_number = number
        invoice.status = "FINAL"
        invoice.save(update_fields=["official_number", "status", "updated_at"])
        messages.success(request, "Resmi faturanın numarası kaydedildi. MoliApp resmi fatura düzenlemedi.")
    return redirect("invoice_detail", invoice_id=invoice.pk)


@login_required
def invoice_order_status(request, order_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    line = InvoiceLine.objects.filter(order_id=order_id).select_related("invoice").first()
    planned = ShipmentPlan.objects.filter(order_id=order_id).exists()
    return JsonResponse({"added": bool(line) or planned, "invoice_id": line.invoice_id if line else None})
