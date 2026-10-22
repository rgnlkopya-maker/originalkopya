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
from .invoice_models import InvoiceDraft, InvoiceLine, InvoiceStatusHistory, BizimHesapCustomerMapping, BizimHesapInvoiceTransfer, ParasutInvoiceTransfer
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
    invoices = list(InvoiceDraft.objects.select_related("customer").prefetch_related("lines", "bizimhesap_transfer", "parasut_transfer").order_by("-invoice_date", "-id"))
    pending = _pending_shipments_by_invoice()
    for invoice in invoices:
        invoice.has_pending_shipment = pending.get(invoice.id, False)
        transfer = getattr(invoice, "bizimhesap_transfer", None)
        invoice.bh_transfer_status = transfer.status if transfer else ""
        invoice.bh_is_recorded = invoice.bizimhesap_manual_recorded or bool(transfer and transfer.status == "SENT")
        parasut_transfer = getattr(invoice, "parasut_transfer", None)
        invoice.parasut_transfer_status = parasut_transfer.status if parasut_transfer else ""
    return render(request, "product_cards/invoice_list.html", {"invoices": invoices})


@login_required
@require_POST
def invoice_platform_status_update(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    platform = request.POST.get("platform", "")
    recorded = request.POST.get("recorded", "")
    if platform not in ("bizimhesap", "parasut") or recorded not in ("yes", "no"):
        messages.error(request, "Geçersiz aktarım durumu.")
        return redirect("invoice_list")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if platform == "bizimhesap":
            transfer = BizimHesapInvoiceTransfer.objects.filter(invoice=invoice).first()
            if transfer and transfer.status in ("SENDING", "UNKNOWN", "SENT"):
                messages.warning(request, "Bu faturanın API aktarım kaydı var; manuel durum değiştirilemez.")
                return redirect("invoice_list")
            invoice.bizimhesap_manual_recorded = recorded == "yes"
            invoice.save(update_fields=["bizimhesap_manual_recorded", "updated_at"])
        else:
            parasut_transfer = ParasutInvoiceTransfer.objects.filter(invoice=invoice).first()
            if parasut_transfer and parasut_transfer.status in ("SENDING", "SENT", "UNKNOWN"):
                messages.warning(request, "Paraşüt API aktarım kaydı var; manuel durum değiştirilemez.")
                return redirect("invoice_list")
            invoice.parasut_manual_recorded = recorded == "yes"
            invoice.save(update_fields=["parasut_manual_recorded", "updated_at"])
    messages.success(request, "Manuel kayıt durumu güncellendi; dış sisteme fatura gönderilmedi.")
    return redirect("invoice_list")


@login_required
def invoice_customer_mapping_list(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    customers = list(Musteri.objects.filter(aktif=True).order_by("ad").prefetch_related("bizimhesap_mapping"))
    mappings = {m.customer_id: m for m in BizimHesapCustomerMapping.objects.filter(customer_id__in=[c.id for c in customers])}
    for customer in customers:
        customer.bh_code = mappings[customer.id].external_customer_id if customer.id in mappings else ""
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
        if (_transfer_locked(invoice) or invoice.bizimhesap_manual_recorded or
                invoice.parasut_manual_recorded):
            messages.error(request, "Muhasebe sistemine aktarılmış veya işlenmiş fatura silinemez.")
            return redirect("invoice_list")
        # Protect even NOT_SENT transfer rows if they hold evidence of an external record.
        if (BizimHesapInvoiceTransfer.objects.filter(invoice=invoice).exclude(
                external_invoice_id="").exists() or
                ParasutInvoiceTransfer.objects.filter(invoice=invoice).exclude(
                external_invoice_id="").exists()):
            messages.error(request, "Dış sistem belge bağlantısı bulunan fatura silinemez.")
            return redirect("invoice_list")
        # Empty, untransferred local drafts may have a reversal audit row
        # (InvoiceStatusHistory.invoice uses PROTECT). Clear only these local rows.
        invoice.status_history.all().delete()
        BizimHesapInvoiceTransfer.objects.filter(invoice=invoice, status="NOT_SENT").delete()
        ParasutInvoiceTransfer.objects.filter(invoice=invoice, status="NOT_SENT").delete()
        invoice.delete()
    logging.getLogger(__name__).info("empty_invoice_deleted invoice_id=%s user_id=%s", invoice_id, request.user.pk)
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
    return render(request, "product_cards/invoice_detail.html", {"invoice": invoice, "lines": lines, "subtotal": subtotal, "tax": tax, "total": subtotal + tax, "status_history": invoice.status_history.select_related("changed_by").order_by("-changed_at")[:10]})


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
        if _transfer_locked(invoice):
            messages.error(request, "Aktarım kaydı bulunan faturanın vadesi değiştirilemez.")
            return redirect("invoice_detail", invoice_id=invoice_id)
        invoice.due_date = due
        invoice.save(update_fields=["due_date", "updated_at"])
    messages.success(request, "Fatura vade tarihi kaydedildi.")
    return redirect("invoice_detail", invoice_id=invoice_id)


@login_required
@require_POST
def invoice_bizimhesap_send(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .bizimhesap_export_service import prepare_transfer, deliver_prepared_invoice, TransferBlocked
    if os.environ.get("BIZIMHESAP_INVOICE_EXPORT_ENABLED") != "true":
        messages.error(request, "BizimHesap aktarımı kapalı.")
        return redirect("invoice_bizimhesap_preview", invoice_id=invoice_id)
    test_id = os.environ.get("BIZIMHESAP_FIRST_TEST_INVOICE_ID", "")
    if test_id and test_id != str(invoice_id):
        messages.error(request, "İlk test yalnızca belirlenen fatura için açık.")
        return redirect("invoice_bizimhesap_preview", invoice_id=invoice_id)
    try:
        # FT-9: allow a single retry after manual verification of no external record.
        if invoice_id == 9:
            with transaction.atomic():
                old_transfer = BizimHesapInvoiceTransfer.objects.select_for_update().filter(invoice_id=9).first()
                if (old_transfer and old_transfer.status == "UNKNOWN"
                        and not old_transfer.external_invoice_id
                        and old_transfer.last_error == "BizimHesap reddetti: Adres bilgisi gönderilmemiş"):
                    old_transfer.status = "NOT_SENT"
                    old_transfer.last_error = "Önceki deneme BizimHesap'ta bulunamadı."
                    old_transfer.save(update_fields=["status", "last_error", "updated_at"])
        transfer_id, payload = prepare_transfer(invoice_id)
        status = deliver_prepared_invoice(transfer_id, payload)
    except TransferBlocked as exc:
        messages.error(request, str(exc))
    except Exception:
        logging.getLogger(__name__).exception("BizimHesap export failed for invoice id=%s", invoice_id)
        messages.error(request, "Aktarım kesildi; dış sistem kontrol edilmeden tekrar denenmemeli.")
    else:
        if status == "SENT":
            messages.success(request, "Fatura BizimHesap'a aktarıldı.")
        else:
            messages.warning(request, "Aktarım sonucu belirsiz; tekrar gönderim kapalı.")
    return redirect("invoice_bizimhesap_preview", invoice_id=invoice_id)


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
    if transfer and transfer.status == "SENDING":
        warnings.append("Aktarım işlemi sürüyor.")
    elif transfer and transfer.status == "UNKNOWN":
        warnings.append("Aktarım sonucu doğrulanmalı; tekrar gönderim koruması aktif.")
    if invoice.status not in ("DRAFT", "FINAL"):
        warnings.append("Fatura durumu aktarıma uygun değil.")
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
        ("Satış kaydı", True, "AddInvoice satış kaydı oluşturur; e-belge davranışı ilk testte doğrulanacak"),
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
    retry_ft9 = (invoice_id == 9 and transfer is not None and transfer.status == "UNKNOWN"
                 and not transfer.external_invoice_id
                 and transfer.last_error == "BizimHesap reddetti: Adres bilgisi gönderilmemiş")
    if transfer and transfer.status in ("SENT", "SENDING", "UNKNOWN") and not retry_ft9 and transfer.status != "SENT":
        payload_blockers.append("Bu fatura için aktarım kaydı var.")
        prepared_payload = None
    if invoice.bizimhesap_manual_recorded:
        payload_blockers.append("Bu fatura BizimHesap için elle işlendi olarak işaretlenmiş.")
        prepared_payload = None
    export_enabled = os.environ.get("BIZIMHESAP_INVOICE_EXPORT_ENABLED") == "true" and (not os.environ.get("BIZIMHESAP_FIRST_TEST_INVOICE_ID") or os.environ.get("BIZIMHESAP_FIRST_TEST_INVOICE_ID") == str(invoice_id))
    can_send = export_enabled and prepared_payload is not None and not payload_blockers and not (transfer and transfer.status in ("SENDING", "SENT", "UNKNOWN") and not retry_ft9)
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
    if can_send:
        warnings.append("İlk kontrollü test: Gönderim cari borç oluşturabilir. BizimHesap'taki sonucu ve e-belge durumunu doğrulayın.")
    elif not export_enabled:
        warnings.append("BizimHesap gönderimi bu fatura için kapalı.")

    return render(request, "product_cards/invoice_bizimhesap_preview.html", {
        "invoice": invoice, "details": details, "currency": currency or invoice.currency,
        "net_total": net_total, "tax_total": tax_total, "grand_total": net_total + tax_total,
        "warnings": warnings, "mapping": mapping, "transfer": transfer, "api_checks": api_checks, "payload_summary": payload_summary, "payload_blockers": payload_blockers, "can_send": can_send,
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


def _transfer_locked(invoice):
    return (BizimHesapInvoiceTransfer.objects.filter(invoice=invoice, status__in=("SENDING", "SENT", "UNKNOWN")).exists() or
            ParasutInvoiceTransfer.objects.filter(invoice=invoice, status__in=("SENDING", "SENT", "UNKNOWN")).exists())


@login_required
@require_POST
def invoice_remove(request, invoice_id, line_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if _transfer_locked(invoice):
            return HttpResponseForbidden("Aktarım sürecindeki fatura değiştirilemez.")
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
        if _transfer_locked(invoice):
            return HttpResponseForbidden("Aktarım sürecindeki fatura değiştirilemez.")
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
def invoice_open_account(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id, status="DRAFT")
        if _transfer_locked(invoice):
            return HttpResponseForbidden("Aktarım sürecindeki kayıt açık hesaba alınamaz.")
        if not invoice.lines.exists():
            messages.error(request, "Açık hesaba almak için en az bir ürün gerekli.")
        else:
            invoice.status = "OPEN"
            invoice.official_number = ""
            invoice.save(update_fields=["status", "official_number", "updated_at"])
            messages.success(request, "Kayıt açık hesap olarak işaretlendi. Resmî fatura oluşturulmadı.")
    return redirect("invoice_detail", invoice_id=invoice_id)


@login_required
@require_POST
def invoice_unfinalize(request, invoice_id):
    """Undo accidental MoliApp finalization without modifying an external invoice."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if invoice.status != "FINAL":
            messages.error(request, "Yalnızca faturalandırılmış kayıt geri alınabilir.")
        elif _transfer_locked(invoice) or invoice.bizimhesap_manual_recorded or invoice.parasut_manual_recorded:
            messages.error(request, "Dış muhasebe sistemine aktarılmış veya işlenmiş kayıt geri alınamaz.")
        elif request.POST.get("confirm") != "yes":
            messages.error(request, "Geri alma onayı gerekli.")
        elif InvoiceDraft.objects.filter(customer=invoice.customer, invoice_date=invoice.invoice_date,
                                         currency=invoice.currency, status="DRAFT").exclude(pk=invoice.pk).exists():
            messages.error(request, "Aynı müşteri, tarih ve para birimi için zaten taslak mevcut.")
        else:
            previous_number = invoice.official_number
            invoice.status = "DRAFT"
            invoice.official_number = ""
            try:
                with transaction.atomic():
                    invoice.save(update_fields=["status", "official_number", "updated_at"])
                    InvoiceStatusHistory.objects.create(
                        invoice=invoice, changed_by=request.user, previous_status="FINAL",
                        new_status="DRAFT", previous_official_number=previous_number)
            except IntegrityError:
                messages.error(request, "Mevcut taslakla çakıştığı için işlem yapılamadı.")
            else:
                messages.success(request, "Faturalandırma geri alındı; kayıt taslak olarak açıldı.")
    return redirect("invoice_detail", invoice_id=invoice_id)


@login_required
@require_POST
def invoice_finalize(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id, status__in=("DRAFT", "OPEN"))
        if _transfer_locked(invoice):
            return HttpResponseForbidden("Aktarım sürecindeki fatura tamamlanamaz.")
        number = request.POST.get("official_number", "").strip()
        if not number or len(number) > 80 or not invoice.lines.exists():
            messages.error(request, "Geçerli fatura numarası (en fazla 80 karakter) ve en az bir ürün gerekli.")
        else:
            invoice.official_number = number
            invoice.status = "FINAL"
            invoice.save(update_fields=["official_number", "status", "updated_at"])
            messages.success(request, "Resmî fatura numarası kaydedildi. MoliApp resmî fatura düzenlemedi.")
    return redirect("invoice_detail", invoice_id=invoice_id)

@login_required
def invoice_order_status(request, order_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    line = InvoiceLine.objects.filter(order_id=order_id).select_related("invoice").first()
    planned = ShipmentPlan.objects.filter(order_id=order_id).exists()
    return JsonResponse({"added": bool(line) or planned, "invoice_id": line.invoice_id if line else None})


@login_required
def invoice_parasut_preview(request, invoice_id):
    """Read-only Paraşüt transfer preview; never creates an external invoice."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_payload import build_parasut_sales_invoice
    invoice = get_object_or_404(InvoiceDraft.objects.select_related("customer"), pk=invoice_id)
    payload, problems = build_parasut_sales_invoice(invoice)
    transfer = ParasutInvoiceTransfer.objects.filter(invoice=invoice).first()
    from .invoice_models import ParasutCustomerMapping
    mapping = ParasutCustomerMapping.objects.filter(customer=invoice.customer).first()
    export_enabled = (os.environ.get("PARASUT_INVOICE_EXPORT_ENABLED") == "true"
                      and (not os.environ.get("PARASUT_FIRST_TEST_INVOICE_ID")
                           or os.environ.get("PARASUT_FIRST_TEST_INVOICE_ID") == str(invoice_id)))
    if transfer and transfer.status in ("SENT", "SENDING", "UNKNOWN"):
        problems.append("Önceki aktarım mevcut veya sonucu belirsiz; yeniden gönderilmemeli.")
    if invoice.status != "DRAFT":
        problems.append("MoliApp faturası taslak durumunda değil.")
    return render(request, "product_cards/invoice_parasut_preview.html", {
        "invoice": invoice, "problems": problems,
        "prepared": payload is not None,
        "transfer": transfer,
        "line_count": invoice.lines.count(),
        "mapping": mapping, "export_enabled": export_enabled,
    })



@login_required
@require_POST
def invoice_parasut_customer_map(request, invoice_id):
    """Map a pre-existing Paraşüt contact; never create external records."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .invoice_models import ParasutCustomerMapping
    invoice = get_object_or_404(InvoiceDraft, pk=invoice_id)
    code = request.POST.get("external_contact_id", "").strip()
    if not code.isdecimal() or len(code) > 100:
        messages.error(request, "Geçerli bir Paraşüt cari ID girin.")
        return redirect("invoice_parasut_preview", invoice_id=invoice_id)
    if ParasutCustomerMapping.objects.filter(external_contact_id=code).exclude(customer=invoice.customer).exists():
        messages.error(request, "Bu Paraşüt carisi başka müşteriye eşleştirilmiş.")
        return redirect("invoice_parasut_preview", invoice_id=invoice_id)
    try:
        ParasutCustomerMapping.objects.update_or_create(customer=invoice.customer, defaults={"external_contact_id": code})
    except IntegrityError:
        messages.error(request, "Cari eşleştirmesi çakıştı.")
    else:
        messages.success(request, "Paraşüt carisi eşleştirildi; fatura oluşturulmadı.")
    return redirect("invoice_parasut_preview", invoice_id=invoice_id)


@login_required
@require_POST
def invoice_parasut_send(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_export_service import send_sales_record, ParasutExportError
    try:
        remote_id = send_sales_record(invoice_id)
    except ParasutExportError as exc:
        messages.error(request, str(exc))
    except Exception:
        logging.getLogger(__name__).exception("Paraşüt export failed, invoice=%s", invoice_id)
        messages.error(request, "Aktarımın sonucu belirsiz; Paraşüt kontrol edilmeden tekrar denemeyin.")
    else:
        messages.success(request, "Paraşüt satış kaydı oluşturuldu (ID: " + remote_id + "). E-belge gönderilmedi.")
    return redirect("invoice_parasut_preview", invoice_id=invoice_id)

@login_required
def invoice_parasut_connection_status(request):
    """Read-only API probe; credentials and raw responses are never displayed."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_connection import check_connection, ParasutConnectionError
    try:
        check_connection()
    except ParasutConnectionError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=503)
    return JsonResponse({"ok": True, "message": "Paraşüt okuma bağlantısı doğrulandı; fatura gönderilmedi."})


@login_required
def invoice_parasut_catalog(request):
    """Existing Paraşüt contacts/products, read-only, authorized staff only."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_catalog import list_contacts, list_products, ParasutCatalogError
    resource = request.GET.get("resource", "")
    if resource not in ("contacts", "products"):
        return JsonResponse({"ok": False, "message": "Geçersiz kaynak."}, status=400)
    try:
        page = int(request.GET.get("page", "1"))
        data = (list_contacts if resource == "contacts" else list_products)(page)
    except (ValueError, ParasutCatalogError) as exc:
        message = str(exc) if isinstance(exc, ParasutCatalogError) else "Geçersiz sayfa."
        return JsonResponse({"ok": False, "message": message}, status=400)
    return JsonResponse({"ok": True, **data})


@login_required
def invoice_parasut_oauth_setup(request):
    """Manual OOB OAuth authorization; no data sent to Paraşüt from this GET."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_oauth import authorization_url, ParasutOAuthError
    try:
        auth_url = authorization_url()
    except ParasutOAuthError:
        auth_url = ""
    from .invoice_models import ParasutOAuthCredential
    company_id = os.environ.get("PARASUT_COMPANY_ID", "").strip()
    settings_state = {
        "client_id": bool(os.environ.get("PARASUT_CLIENT_ID", "").strip()),
        "client_secret": bool(os.environ.get("PARASUT_CLIENT_SECRET", "").strip()),
        "company_id": company_id.isdecimal(),
        "encryption_key": bool(os.environ.get("PARASUT_TOKEN_ENCRYPTION_KEY", "").strip()),
        "connected": bool(company_id.isdecimal() and ParasutOAuthCredential.objects.filter(company_id=company_id).exists()),
    }
    return render(request, "product_cards/parasut_oauth_setup.html", {"auth_url": auth_url if all(settings_state[k] for k in ("client_id", "client_secret", "company_id", "encryption_key")) else "", "settings_state": settings_state})


@login_required
@require_POST
def invoice_parasut_oauth_connect(request):
    """Exchange a manually supplied authorization code and encrypt both tokens."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_oauth import exchange_authorization_code, ParasutOAuthError
    from .parasut_credentials import save_tokens, ParasutCredentialError
    company_id = os.environ.get("PARASUT_COMPANY_ID", "").strip()
    code = request.POST.get("authorization_code", "").strip()
    if not company_id.isdecimal():
        messages.error(request, "Önce Render'da PARASUT_COMPANY_ID tanımlanmalı.")
    else:
        stage = "TOKEN"
        try:
            tokens = exchange_authorization_code(code)
            stage = "COMPANY"
            from .parasut_verify import verify_company_access
            verify_company_access(company_id, tokens["access_token"])
            stage = "SAVE"
            save_tokens(company_id, tokens)
        except (ParasutOAuthError, ParasutCredentialError) as exc:
            # Only a fixed, non-sensitive reason category enters server logs.
            reason = "credential_error"
            if stage == "TOKEN" and isinstance(exc, ParasutOAuthError):
                detail = str(exc)
                reason = next((key for key in ("invalid_grant", "invalid_client", "invalid_request", "unauthorized_client", "unsupported_grant_type") if key in detail), "token_exchange_error")
            elif stage == "COMPANY":
                reason = next((key for key in ("401", "403", "404") if key in str(exc)), "company_request_error")
            logging.getLogger(__name__).warning("parasut_oauth_failure stage=%s reason=%s", stage, reason)
            if stage == "TOKEN" and isinstance(exc, ParasutOAuthError):
                messages.error(request, "Paraşüt OAuth hatası: " + str(exc))
            else:
                safe_reasons = {
                    "COMPANY": "OAuth tokenı alındı; firma doğrulaması başarısız: " + str(exc),
                    "SAVE": "Paraşüt tokenı alındı fakat şifreli veritabanı kaydı yapılamadı.",
                }
                messages.error(request, "Paraşüt bağlantısı başarısız: " + safe_reasons.get(stage, "Yetkilendirme başarısız."))
        else:
            logging.getLogger(__name__).info("parasut_oauth_success stage=SAVE")
            messages.success(request, "Paraşüt OAuth tokenları şifreli olarak kaydedildi. Fatura gönderilmedi.")
    return redirect("invoice_parasut_oauth_setup")
