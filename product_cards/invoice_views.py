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
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.models import Order, Musteri
from .invoice_models import InvoiceDraft, InvoiceLine, InvoiceStatusHistory, BizimHesapCustomerMapping, BizimHesapInvoiceTransfer, ParasutInvoiceTransfer
from planning.models import ShipmentPlan
from core.services.order_status import latest_status_event, status_label, FINANCIAL_STAGES



def _assign_shared_ft_number(*, draft=None, manual=None):
    """Allocate a single FT number atomically across both invoice models."""
    from .invoice_models import SharedInvoiceNumber, InvoiceNumberSequence
    if draft is None and manual is None:
        raise ValueError("Invoice required")
    number_owner = {"draft": draft} if draft is not None else {"manual": manual}
    if SharedInvoiceNumber.objects.filter(**number_owner).exists():
        return
    seq = InvoiceNumberSequence.objects.select_for_update().get(pk=1)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    SharedInvoiceNumber.objects.create(number=seq.last_number, **number_owner)


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
    try:
        return _invoice_list_impl(request)
    except Exception:
        logging.getLogger(__name__).exception("invoice_list_runtime_failure")
        raise


def _invoice_list_impl(request):
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
        invoice.bh_display = invoice.bizimhesap_display_status or ("api" if invoice.bh_transfer_status == "SENT" else ("yes" if invoice.bizimhesap_manual_recorded else "no"))
        invoice.parasut_display = "api" if invoice.parasut_transfer_status == "SENT" else (invoice.parasut_display_status or ("yes" if invoice.parasut_manual_recorded else "no"))
        invoice.list_total = sum((line.price * (Decimal("1") + line.vat_rate / Decimal("100")) for line in invoice.lines.all()), Decimal("0"))
        invoice.visible_official_number = invoice.official_number
    from .invoice_models import StandaloneInvoice
    standalone_invoices = list(StandaloneInvoice.objects.filter(is_proforma=False).select_related("customer").prefetch_related("lines").order_by("-invoice_date", "-id")[:200])
    proforma_invoices = list(StandaloneInvoice.objects.filter(is_proforma=True).select_related("customer").prefetch_related("lines").order_by("-invoice_date", "-id")[:200])
    for draft in standalone_invoices:
        draft.has_locked_transfer = any(t.status != "NOT_SENT" or bool(t.external_invoice_id) for t in draft.transfers.all())
        statuses = {t.platform: t.status for t in draft.transfers.all()}
        draft.bh_display = draft.bizimhesap_display_status or ("api" if statuses.get("bizimhesap") == "SENT" else "no")
        draft.parasut_display = draft.parasut_display_status or ("api" if statuses.get("parasut") == "SENT" else "no")
    for draft in standalone_invoices + proforma_invoices:
        draft.list_total = sum((item.quantity * item.unit_price * (Decimal("1") + item.vat_rate / Decimal("100")) for item in draft.lines.all()), Decimal("0"))
    for draft in standalone_invoices:
        draft.is_manual = True
    combined_invoices = sorted(invoices + standalone_invoices, key=lambda inv: (inv.invoice_date, inv.shared_number.number), reverse=True)
    return render(request, "product_cards/invoice_list.html", {"combined_invoices": combined_invoices, "standalone_invoices": standalone_invoices, "proforma_invoices": proforma_invoices, "invoices": invoices, "invoice_customers": Musteri.objects.filter(pk__in=({invoice.customer_id for invoice in invoices} | {invoice.customer_id for invoice in standalone_invoices})).order_by("ad"), "accounting_status_choices": [("no", "İşlenmedi"), ("yes", "Elle İşlendi"), ("api", "API ile Aktarıldı"), ("skip", "Aktarılmayacak")]})


@login_required
def invoice_list_live_totals(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from django.db.models import Sum, F, DecimalField, ExpressionWrapper
    line_amount = ExpressionWrapper(F("price") * (1 + F("vat_rate") / 100), output_field=DecimalField(max_digits=20, decimal_places=4))
    rows = InvoiceLine.objects.values("invoice_id").annotate(total=Sum(line_amount))
    return JsonResponse({"totals": {str(row["invoice_id"]): str(row["total"] or 0) for row in rows}})


@login_required
@require_POST
def invoice_open_account_label(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    selected = request.POST.get("label")
    if selected not in ("open", "empty"):
        messages.error(request, "Geçersiz seçim.")
        return redirect("invoice_list")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if invoice.official_number:
            messages.error(request, "Resmî fatura numarası olan kayıtta bu etiket değiştirilemez.")
            return redirect("invoice_list")
        invoice.show_open_account_in_list = selected == "open"
        invoice.save(update_fields=["show_open_account_in_list", "updated_at"])
    return redirect("invoice_list")


@login_required
@require_POST
def invoice_platform_status_update(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    platform = request.POST.get("platform", "")
    recorded = request.POST.get("recorded", "")
    if platform not in ("bizimhesap", "parasut") or recorded not in ("no", "yes", "api", "skip"):
        messages.error(request, "Geçersiz durum seçimi.")
        return redirect("invoice_list")
    field = "bizimhesap_display_status" if platform == "bizimhesap" else "parasut_display_status"
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        setattr(invoice, field, recorded)
        invoice_fields = [field, "updated_at"]
        if recorded == "no":
            # "İşlenmedi" is the operator's explicit reset of the LOCAL accounting
            # tracking state. Never calls or alters a remote accounting system.
            # Keep old external IDs in an archive for audit and troubleshooting.
            if platform == "parasut":
                transfer = ParasutInvoiceTransfer.objects.select_for_update().filter(invoice=invoice).first()
                if transfer:
                    if transfer.external_invoice_id:
                        transfer.deleted_external_invoice_id = transfer.external_invoice_id
                    transfer.deleted_verified_at = None
                    transfer.external_invoice_id = ""
                    transfer.external_invoice_no = ""
                    transfer.payload_fingerprint = ""
                    transfer.needs_sync = False
                    transfer.status = "NOT_SENT"
                    transfer.last_error = ""
                    transfer.save(update_fields=["deleted_external_invoice_id","deleted_verified_at","external_invoice_id","external_invoice_no","payload_fingerprint","needs_sync","status","last_error","updated_at"])
            else:
                transfer = BizimHesapInvoiceTransfer.objects.select_for_update().filter(invoice=invoice).first()
                if transfer:
                    transfer.status = "NOT_SENT"
                    transfer.external_invoice_no = ""
                    transfer.external_invoice_id = ""
                    transfer.payload_fingerprint = ""
                    transfer.last_error = ""
                    transfer.save(update_fields=["status","external_invoice_no","external_invoice_id","payload_fingerprint","last_error","updated_at"])
            invoice.official_number = ""
            invoice_fields.append("official_number")
        invoice.save(update_fields=invoice_fields)
    messages.success(request, "İşlenmedi olarak sıfırlandı. MoliApp aktarım kilidi ve resmî FT no temizlendi; dış muhasebe kayıtlarına dokunulmadı." if recorded == "no" else "Görünen takip durumu güncellendi.")
    return redirect("invoice_list")


@login_required
@require_POST
def invoice_parasut_fetch_official_number(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_export_service import fetch_official_number, ParasutExportError
    try:
        number, remote_id = fetch_official_number(invoice_id)
    except ParasutExportError as exc:
        messages.warning(request, "Paraşüt numarası kaydedilmedi: " + str(exc))
        return redirect("invoice_list")
    except Exception:
        logging.getLogger(__name__).exception("Paraşüt official number lookup failed FT-%s", invoice_id)
        messages.error(request, "Paraşüt numarası doğrulanamadı; mevcut kayıt korunuyor.")
        return redirect("invoice_list")
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        transfer = ParasutInvoiceTransfer.objects.select_for_update().filter(invoice=invoice).first()
        if not transfer or transfer.status != "SENT" or transfer.external_invoice_id != remote_id:
            messages.warning(request, "Fatura bağlantısı sorgulama sırasında değişmiş. Numara kaydedilmedi.")
            return redirect("invoice_list")
        if invoice.official_number:
            messages.info(request, "Resmî fatura numarası zaten kayıtlı; üzerine yazılmadı.")
            return redirect("invoice_list")
        invoice.official_number = number
        invoice.save(update_fields=["official_number", "updated_at"])
        transfer.external_invoice_no = number
        transfer.official_number_synced_at = timezone.now()
        transfer.save(update_fields=["external_invoice_no", "official_number_synced_at", "updated_at"])
    messages.success(request, "Paraşüt resmî FT numarası kaydedildi: " + number)
    return redirect("invoice_list")


@login_required
@require_POST
def invoice_official_number_update(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    return_to_list = request.POST.get("return_to") == "list"
    destination = redirect("invoice_list") if return_to_list else redirect("invoice_detail", invoice_id=invoice_id)
    number = request.POST.get("official_number", "").strip()
    if len(number) > 80:
        messages.error(request, "Fatura numarası en fazla 80 karakter olabilir.")
        return destination
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        invoice.official_number = number
        invoice.save(update_fields=["official_number", "updated_at"])
        InvoiceStatusHistory.objects.filter(invoice=invoice).exclude(previous_official_number="").update(previous_official_number="")
    messages.success(request, "Fatura numarası güncellendi." if number else "Fatura numarası silindi.")
    return destination


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
def invoice_parasut_mapping_list(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .invoice_models import ParasutCustomerMapping
    customers = list(Musteri.objects.filter(aktif=True).order_by("ad"))
    mappings = dict(ParasutCustomerMapping.objects.filter(customer_id__in=[c.id for c in customers]).values_list("customer_id", "external_contact_id"))
    for customer in customers:
        customer.parasut_code = mappings.get(customer.pk, "")
    return render(request, "product_cards/invoice_parasut_mapping.html", {
        "customers": customers, "customer_count": len(customers), "mapped_count": len(mappings),
    })


@login_required
@require_POST
def invoice_parasut_mapping_save(request, customer_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .invoice_models import ParasutCustomerMapping
    customer = get_object_or_404(Musteri, pk=customer_id, aktif=True)
    code = request.POST.get("external_contact_id", "").strip()
    if not code.isdecimal() or len(code) > 100:
        messages.error(request, "Geçerli bir Paraşüt cari ID girin.")
        return redirect("invoice_parasut_mapping_list")
    try:
        with transaction.atomic():
            if ParasutCustomerMapping.objects.filter(external_contact_id=code).exclude(customer=customer).exists():
                messages.error(request, "Paraşüt cari ID başka bir müşteriye eşleştirilmiş.")
                return redirect("invoice_parasut_mapping_list")
            ParasutCustomerMapping.objects.update_or_create(
                customer=customer, defaults={"external_contact_id": code},
            )
    except IntegrityError:
        messages.error(request, "Cari eşleştirmesi çakıştı.")
    else:
        messages.success(request, customer.ad + ": Paraşüt cari eşleştirmesi kaydedildi. Fatura gönderilmedi.")
    return redirect("invoice_parasut_mapping_list")


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
    invoice.show_parasut_official_number = True
    lines = list(invoice.lines.select_related("order").order_by("id"))
    for line in lines:
        line.current_status = status_label(latest_status_event(line.order))
        line.total_with_vat = (line.price * (Decimal("1") + line.vat_rate / Decimal("100"))).quantize(Decimal("0.01"))
    parasut_vat_ready = bool(lines) and all(line.vat_rate is not None and Decimal(str(line.vat_rate)) == Decimal("10") for line in lines)
    subtotal = sum((line.price for line in lines), Decimal("0"))
    tax = sum((line.price * line.vat_rate / Decimal("100") for line in lines), Decimal("0"))
    bh_transfer = BizimHesapInvoiceTransfer.objects.filter(invoice=invoice).first()
    ps_transfer = ParasutInvoiceTransfer.objects.filter(invoice=invoice).first()
    bh_status = invoice.bizimhesap_display_status or ("api" if bh_transfer and bh_transfer.status == "SENT" else ("yes" if invoice.bizimhesap_manual_recorded else "no"))
    ps_status = "api" if ps_transfer and ps_transfer.status == "SENT" else (invoice.parasut_display_status or ("yes" if invoice.parasut_manual_recorded else "no"))
    if bh_transfer and bh_transfer.status in ("SENDING", "UNKNOWN"):
        bh_status = "pending"
    if ps_transfer and ps_transfer.status in ("SENDING", "UNKNOWN"):
        ps_status = "pending"
    from .invoice_models import CompanyInvoiceProfile
    company_profile = CompanyInvoiceProfile.objects.order_by("pk").first()
    return render(request, "product_cards/invoice_detail.html", {"company_profile": company_profile, "bh_status": bh_status, "ps_status": ps_status, "invoice": invoice, "lines": lines, "subtotal": subtotal, "tax": tax, "total": subtotal + tax, "parasut_vat_ready": parasut_vat_ready, "status_history": invoice.status_history.select_related("changed_by").order_by("-changed_at")[:10]})


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
    inv = get_object_or_404(InvoiceDraft, pk=invoice_id)
    if inv.bizimhesap_manual_recorded or inv.bizimhesap_display_status in ("yes", "skip", "api"):
        messages.error(request, "BizimHesap işlemi zaten kayıtlı veya aktarım kapalı.")
        return redirect("invoice_detail", invoice_id=invoice_id)
    if os.environ.get("BIZIMHESAP_INVOICE_EXPORT_ENABLED") != "true":
        messages.error(request, "BizimHesap aktarımı kapalı.")
        return redirect("invoice_detail", invoice_id=invoice_id)
    test_id = os.environ.get("BIZIMHESAP_FIRST_TEST_INVOICE_ID", "")
    if test_id and test_id != str(invoice_id):
        messages.error(request, "İlk test yalnızca belirlenen fatura için açık.")
        return redirect("invoice_detail", invoice_id=invoice_id)
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
        _assign_shared_ft_number(draft=invoice)
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
        if BizimHesapInvoiceTransfer.objects.filter(invoice=invoice, status__in=("SENDING","SENT","UNKNOWN")).exists() or ParasutInvoiceTransfer.objects.filter(invoice=invoice, status__in=("SENDING","UNKNOWN")).exists():
            return HttpResponseForbidden("Kesinleşmiş BizimHesap kaydı veya süren aktarım nedeniyle düzenleme kapalı.")
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
def invoice_vat_update(request, invoice_id, line_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    try:
        rate = Decimal(request.POST.get("vat_rate", "").replace(",", "."))
        if not rate.is_finite() or rate < 0 or rate > 100:
            raise InvalidOperation
        rate = rate.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        messages.error(request, "KDV oranı 0 ile 100 arasında olmalıdır.")
        return redirect("invoice_detail", invoice_id=invoice_id)
    with transaction.atomic():
        invoice = get_object_or_404(InvoiceDraft.objects.select_for_update(), pk=invoice_id)
        if invoice.status != "DRAFT" or BizimHesapInvoiceTransfer.objects.filter(invoice=invoice, status__in=("SENDING","SENT","UNKNOWN")).exists() or ParasutInvoiceTransfer.objects.filter(invoice=invoice, status__in=("SENDING","UNKNOWN")).exists():
            return HttpResponseForbidden("Aktarılmış veya tamamlanmış faturanın KDV'si değiştirilemez.")
        line = get_object_or_404(InvoiceLine.objects.select_for_update().select_related("order"), pk=line_id, invoice=invoice)
        if ParasutInvoiceTransfer.objects.filter(invoice=invoice, status="SENT").exists():
            ParasutInvoiceTransfer.objects.filter(invoice=invoice).update(needs_sync=True)
        line.vat_rate = rate
        line.save(update_fields=["vat_rate"])
        order = line.order
        order.vat_rate = rate
        order.save(update_fields=["vat_rate", "last_updated"])
    messages.success(request, "KDV güncellendi; sipariş ve MoliApp fatura satırı eşitlendi. Dış sistemlerdeki kayıtlar değişmedi.")
    return redirect("invoice_detail", invoice_id=invoice_id)


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
        if ParasutInvoiceTransfer.objects.filter(invoice=invoice, status="SENT").exists():
            ParasutInvoiceTransfer.objects.filter(invoice=invoice).update(needs_sync=True)
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
    product_codes = list(invoice.lines.select_related("order").values_list("order__urun_kodu", flat=True))
    preview_ids = {str(code).strip(): "PREVIEW" for code in product_codes if str(code or "").strip()}
    payload, problems = build_parasut_sales_invoice(invoice, preview_ids)
    transfer = ParasutInvoiceTransfer.objects.filter(invoice=invoice).first()
    from .invoice_models import ParasutCustomerMapping
    mapping = ParasutCustomerMapping.objects.filter(customer=invoice.customer).first()
    export_enabled = (os.environ.get("PARASUT_INVOICE_EXPORT_ENABLED") == "true"
                      and (not os.environ.get("PARASUT_FIRST_TEST_INVOICE_ID")
                           or os.environ.get("PARASUT_FIRST_TEST_INVOICE_ID") == str(invoice_id)))
    if transfer and transfer.status == "SENDING":
        problems.append("Paraşüt aktarımı devam ediyor; yeniden gönderim kapalı.")
    elif transfer and transfer.status == "UNKNOWN":
        problems.append("Paraşüt aktarım sonucu belirsiz; dış kayıt kontrol edilmeli.")
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
def invoice_parasut_archive_deleted(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_export_service import archive_deleted_parasut_draft, ParasutExportError
    try:
        old_id = archive_deleted_parasut_draft(invoice_id)
    except ParasutExportError as exc:
        messages.error(request, "Paraşüt bağlantısı değiştirilmedi: " + str(exc))
    except Exception:
        logging.getLogger(__name__).exception("Paraşüt deleted draft verify failed: FT-%s", invoice_id)
        messages.error(request, "Paraşüt kaydı doğrulanamadı. Bağlantı korunuyor.")
    else:
        messages.success(request, "Paraşüt'te silindiği doğrulanan taslak bağlantısı arşivlendi (eski ID: " + old_id + ").")
    return redirect("invoice_detail", invoice_id=invoice_id)


@login_required
@require_POST
def invoice_parasut_update(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_export_service import update_sales_record, ParasutExportError
    try:
        remote_id = update_sales_record(invoice_id)
    except ParasutExportError as exc:
        messages.error(request, str(exc))
    except Exception:
        logging.getLogger(__name__).exception("Paraşüt update failure for FT-%s", invoice_id)
        messages.error(request, "Paraşüt güncellemesi doğrulanamadı; dış kaydı kontrol edin.")
    else:
        messages.success(request, "Paraşüt'teki mevcut taslak güncellendi (ID: "+remote_id+"). Yeni fatura oluşturulmadı.")
    return redirect("invoice_detail", invoice_id=invoice_id)


@login_required
@require_POST
def invoice_parasut_send(request, invoice_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .parasut_export_service import send_sales_record, ParasutExportError
    inv = get_object_or_404(InvoiceDraft, pk=invoice_id)
    if inv.parasut_manual_recorded or inv.parasut_display_status in ("yes", "skip", "api"):
        messages.error(request, "Paraşüt işlemi zaten kayıtlı veya aktarım kapalı.")
        return redirect("invoice_detail", invoice_id=invoice_id)
    try:
        remote_id = send_sales_record(invoice_id)
    except ParasutExportError as exc:
        messages.error(request, str(exc))
    except Exception:
        logging.getLogger(__name__).exception("Paraşüt export failed, invoice=%s", invoice_id)
        messages.error(request, "Aktarımın sonucu belirsiz; Paraşüt kontrol edilmeden tekrar denemeyin.")
    else:
        messages.success(request, "Paraşüt satış kaydı oluşturuldu (ID: " + remote_id + "). E-belge gönderilmedi.")
    return redirect("invoice_detail", invoice_id=invoice_id)

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


@login_required
def standalone_invoice_edit(request, invoice_id=None, proforma=False):
    """Edit manually created invoice without creating a production order."""
    from .invoice_models import StandaloneInvoice, StandaloneInvoiceLine
    from decimal import Decimal, InvalidOperation
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    invoice = get_object_or_404(StandaloneInvoice, pk=invoice_id, is_proforma=proforma) if invoice_id else None
    if request.method == "POST":
        from .invoice_models import StandaloneInvoiceTransfer
        if invoice and StandaloneInvoiceTransfer.objects.filter(invoice=invoice, status__in=("SENDING", "UNKNOWN")).exists():
            messages.error(request, "Aktarım sonucu belirsiz olan fatura düzenlenemez.")
            return redirect("proforma_invoice_edit" if proforma else "standalone_invoice_edit", invoice_id=invoice.pk)
        try:
            customer = Musteri.objects.get(pk=int(request.POST.get("customer", "")))
            currency = request.POST.get("currency", "")
            if currency not in ("TRY", "EUR", "USD"):
                raise ValueError("Geçersiz para birimi.")
            invoice_date = date.fromisoformat(request.POST.get("invoice_date", ""))
            due_date = date.fromisoformat(request.POST.get("due_date", "")) if request.POST.get("due_date") else None
            descriptions = request.POST.getlist("description")
            quantities = request.POST.getlist("quantity")
            units = request.POST.getlist("unit")
            prices = request.POST.getlist("unit_price")
            vats = request.POST.getlist("vat_rate")
            order_ids = request.POST.getlist("order_id")
            if not all(len(v) == len(descriptions) for v in (quantities, units, prices, vats, order_ids)):
                raise ValueError("Fatura kalemleri eksik.")
            items = []
            for desc, quantity, unit, price, vat, order_id in zip(descriptions, quantities, units, prices, vats, order_ids):
                if not desc.strip():
                    raise ValueError("Ürün / hizmet adı boş olamaz.")
                qty, amount, tax = (Decimal(v.replace(",", ".")) for v in (quantity, price, vat))
                if not all(v.is_finite() for v in (qty, amount, tax)) or qty <= 0 or amount < 0 or not 0 <= tax <= 100:
                    raise ValueError("Miktar, fiyat veya KDV geçersiz.")
                if not unit.strip():
                    raise ValueError("Birim boş olamaz.")
                items.append((desc.strip(), qty, unit.strip(), amount, tax, int(order_id) if order_id else None))
            selected_ids = [item[5] for item in items if item[5]]
            if len(selected_ids) != len(set(selected_ids)) or (proforma and selected_ids):
                raise ValueError("Sipariş tekrar ediyor veya proformaya bağlı sipariş eklenemez.")
        except (ValueError, TypeError, InvalidOperation, Musteri.DoesNotExist) as exc:
            messages.error(request, "Fatura kaydedilemedi: " + str(exc))
        else:
            try:
                with transaction.atomic():
                    if invoice is None:
                        invoice = StandaloneInvoice.objects.create(customer=customer, invoice_date=invoice_date, due_date=due_date, currency=currency, note=request.POST.get("note", "").strip(), created_by=request.user, is_proforma=proforma)
                        if not proforma:
                            _assign_shared_ft_number(manual=invoice)
                    else:
                        invoice = StandaloneInvoice.objects.select_for_update().get(pk=invoice.pk)
                        if invoice.transfers.filter(status__in=("SENDING", "SENT", "UNKNOWN")).exists():
                            raise ValueError("Muhasebeye aktarılmış fatura değiştirilemez.")
                        invoice.customer = customer
                        invoice.invoice_date = invoice_date
                        invoice.due_date = due_date
                        invoice.currency = currency
                        invoice.note = request.POST.get("note", "").strip()
                        invoice.save(update_fields=["customer", "invoice_date", "due_date", "currency", "note"])
                    existing_orders = set(invoice.lines.exclude(order_id__isnull=True).values_list("order_id", flat=True))
                    new_orders = set(selected_ids)
                    chosen = list(Order.objects.select_for_update().filter(pk__in=new_orders, musteri=customer))
                    if new_orders and invoice_date.weekday() >= 5:
                        raise ValueError("Sevkiyat planına aktarılacak siparişler için hafta içi tarih seçin.")
                    if len(chosen) != len(new_orders) or any((o.para_birimi or "TRY") != currency for o in chosen):
                        raise ValueError("Seçilen sipariş müşteri veya para birimiyle uyuşmuyor.")
                    if InvoiceLine.objects.filter(order_id__in=new_orders).exists() or ShipmentPlan.objects.filter(order_id__in=new_orders - existing_orders).exists() or StandaloneInvoiceLine.objects.filter(order_id__in=new_orders).exclude(invoice=invoice).exists():
                        raise ValueError("Sipariş başka bir faturada veya sevkiyat planında kayıtlı.")
                    removed = existing_orders - new_orders
                    invoice.lines.all().delete()
                    ShipmentPlan.objects.filter(order_id__in=removed).delete()
                    StandaloneInvoiceLine.objects.bulk_create([
                        StandaloneInvoiceLine(invoice=invoice, description=d, quantity=q, unit=u, unit_price=p, vat_rate=v, order_id=oid)
                        for d, q, u, p, v, oid in items
                    ])
                    for oid in new_orders - existing_orders:
                        ShipmentPlan.objects.create(order_id=oid, planned_date=invoice_date, created_by=request.user)
                    ShipmentPlan.objects.filter(order_id__in=new_orders).update(planned_date=invoice_date)
            except (ValueError, IntegrityError) as exc:
                messages.error(request, "Fatura kaydedilemedi: " + str(exc))
                return redirect("standalone_invoice_edit", invoice_id=invoice.pk) if invoice else redirect("standalone_invoice_create")
            messages.success(request, "Fatura taslağı kaydedildi.")
            return redirect("proforma_invoice_edit" if proforma else "standalone_invoice_edit", invoice_id=invoice.pk)
    from core.customer_models import CustomerDetail
    customer_details = {str(d.customer_id): {"address": d.fatura_adresi or d.adres, "delivery_address": d.teslimat_adresi, "export_company": d.dis_ticaret_firmasi, "phone": d.telefon, "phone2": d.telefon_2, "email": d.email, "country": d.ulke, "contact": d.yetkili_kisi, "legal_name": d.resmi_unvan, "tax_office": d.vergi_dairesi, "tax_number": d.vergi_numarasi, "mersis": d.mersis_no, "registry": d.ticaret_sicil_no, "postal": d.posta_kodu} for d in CustomerDetail.objects.all()}
    return render(request, "product_cards/standalone_invoice_edit.html", {
        "company_profile": __import__("product_cards.invoice_models", fromlist=["CompanyInvoiceProfile"]).CompanyInvoiceProfile.objects.order_by("pk").first(),
        "invoice": invoice, "is_proforma": proforma, "customer_details": customer_details, "customers": Musteri.objects.order_by("ad"),
        "today": timezone.localdate(),
        "manual_lines": list(invoice.lines.order_by("pk")) if invoice else [],
        "manual_transfers": {item.platform: item.status for item in invoice.transfers.all()} if invoice else {},
        "bh_manual_status": next((t.status for t in invoice.transfers.all() if t.platform == "bizimhesap"), "") if invoice else "",
        "ps_manual_status": next((t.status for t in invoice.transfers.all() if t.platform == "parasut"), "") if invoice else "",
        "manual_parasut_vat_ready": bool(invoice and invoice.lines.exists() and all(t.vat_rate == Decimal("10") for t in invoice.lines.all())),
    })



@login_required
@require_POST
def standalone_invoice_send(request, invoice_id, platform):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .standalone_invoice_export import send_manual_invoice, ManualTransferError
    from .invoice_models import StandaloneInvoice
    if get_object_or_404(StandaloneInvoice, pk=invoice_id).is_proforma:
        return HttpResponseForbidden("Proforma faturalar dış sistemlere aktarılamaz.")
    try:
        send_manual_invoice(invoice_id, platform)
    except ManualTransferError as exc:
        messages.error(request, str(exc))
    except Exception:
        logging.getLogger(__name__).exception("manual_invoice_transfer_failed id=%s platform=%s", invoice_id, platform)
        messages.error(request, "Aktarım tamamlanamadı. Dış muhasebe kaydını kontrol edin.")
    else:
        messages.success(request, "Fatura taslağı muhasebe sistemine aktarıldı.")
    return redirect("standalone_invoice_edit", invoice_id=invoice_id)


@login_required
def proforma_invoice_create(request):
    return standalone_invoice_edit(request, proforma=True)


@login_required
def proforma_invoice_detail(request, invoice_id):
    return standalone_invoice_edit(request, invoice_id=invoice_id, proforma=True)


@login_required
def company_invoice_profile_edit(request):
    """Patron/mudur-only local invoice sender profile; never exported to external accounting."""
    from .invoice_models import CompanyInvoiceProfile
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    fields = ("company_name", "address", "tax_office", "tax_number", "mersis_number",
              "registry_number", "phone", "email", "iban")
    profile = CompanyInvoiceProfile.objects.order_by("pk").first()
    if request.method == "POST":
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        values = {name: request.POST.get(name, "").strip() for name in fields}
        if any(len(values[name]) > limit for name, limit in (
            ("company_name", 250), ("tax_office", 120), ("tax_number", 30),
            ("mersis_number", 40), ("registry_number", 50), ("phone", 50),
            ("email", 254), ("iban", 60))) or len(values["address"]) > 2000:
            messages.error(request, "Firma bilgisi alanlarından biri çok uzun.")
        else:
            try:
                if values["email"]:
                    validate_email(values["email"])
            except ValidationError:
                messages.error(request, "E-posta adresi geçersiz.")
            else:
                with transaction.atomic():
                    profile, _ = CompanyInvoiceProfile.objects.select_for_update().get_or_create(pk=1)
                    for name, value in values.items():
                        setattr(profile, name, value)
                    profile.save()
                messages.success(request, "Firma bilgileri kaydedildi.")
                return redirect("company_invoice_profile_edit")
    return render(request, "product_cards/company_invoice_profile_edit.html", {"profile": profile})




@login_required
def standalone_available_orders(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    try:
        customer_id = int(request.GET.get("customer", ""))
    except (ValueError, TypeError):
        return JsonResponse({"orders": []})
    currency = request.GET.get("currency", "TRY")
    invoice_id = request.GET.get("invoice_id")
    existing_ids = set()
    if invoice_id:
        from .invoice_models import StandaloneInvoice, StandaloneInvoiceLine
        inv = StandaloneInvoice.objects.filter(pk=invoice_id, customer_id=customer_id, is_proforma=False).first()
        if inv:
            existing_ids = set(StandaloneInvoiceLine.objects.filter(invoice=inv, order_id__isnull=False).values_list("order_id", flat=True))
    from .invoice_models import StandaloneInvoiceLine
    available = Order.objects.filter(musteri_id=customer_id).exclude(invoice_line__isnull=False).exclude(shipment_plan__isnull=False).exclude(standalone_invoice_line__isnull=False).order_by("-id")[:800]
    orders = [
        {"id":o.pk,"number":o.siparis_numarasi or str(o.pk),
         "description":" / ".join(str(v) for v in (o.urun_kodu, o.renk, o.beden) if v),
         "customer_reference":o.musteri_referans or "", "order_note":o.aciklama or "",
         "quantity":o.adet or 1,"price":str(o.satis_fiyati or 0),
         "vat":str(o.vat_rate or 0)}
        for o in available if (o.para_birimi or "TRY") == currency
    ]
    return JsonResponse({"orders":orders})



@login_required
def uninvoiced_shipped_orders(request):
    """Live reconciliation: latest production status is shipped, no non-proforma invoice line."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from django.db.models import OuterRef, Subquery, Exists, Q
    from core.models import OrderEvent
    from .invoice_models import StandaloneInvoiceLine, InvoiceFreeDelivery
    latest = (OrderEvent.objects.filter(order_id=OuterRef("pk"))
              .exclude(event_type="order_update")
              .exclude(stage__in=FINANCIAL_STAGES)
              .order_by("-timestamp", "-id"))
    ordinary = InvoiceLine.objects.filter(order_id=OuterRef("pk"))
    manual = StandaloneInvoiceLine.objects.filter(order_id=OuterRef("pk"), invoice__is_proforma=False)
    orders = (Order.objects.select_related("musteri")
              .annotate(last_stage=Subquery(latest.values("stage")[:1]),
                        last_value=Subquery(latest.values("value")[:1]),
                        normal_ft=Exists(ordinary), manual_ft=Exists(manual))
              .filter(last_stage="sevkiyat_durum", last_value="gonderildi",
                      normal_ft=False, manual_ft=False, legacy_invoice_acknowledgement__isnull=True)
              .order_by("musteri__ad", "-id"))
    q = (request.GET.get("q") or "").strip()
    if q:
        orders = orders.filter(Q(musteri__ad__icontains=q) |
                               Q(siparis_numarasi__icontains=q) |
                               Q(urun_kodu__icontains=q) |
                               Q(renk__icontains=q) |
                               Q(beden__icontains=q) |
                               Q(musteri_referans__icontains=q) |
                               Q(aciklama__icontains=q))
    tab = "delivered" if request.GET.get("tab") == "delivered" else "pending"
    if tab == "delivered":
        orders = orders.filter(invoice_free_delivery__isnull=False).select_related("invoice_free_delivery", "invoice_free_delivery__created_by")
    else:
        orders = orders.filter(invoice_free_delivery__isnull=True)
    entries = list(orders)
    from collections import defaultdict
    totals = defaultdict(lambda: Decimal("0"))
    total_qty = 0
    for order in entries:
        total_qty += order.adet or 0
        amount = (order.satis_fiyati or Decimal("0")) * (order.adet or 1)
        totals[order.para_birimi or "TRY"] += amount
    return render(request, "product_cards/uninvoiced_shipped_orders.html", {
        "orders": entries, "order_count": len(entries), "total_qty": total_qty,
        "totals": sorted(totals.items()), "search": q, "tab": tab,
    })


@login_required
@require_POST
def invoice_free_delivery_decision(request, order_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    from .invoice_models import InvoiceFreeDelivery, StandaloneInvoiceLine
    from django.db.models import OuterRef, Subquery
    from core.models import OrderEvent
    action = request.POST.get("action")
    if action not in ("save", "undo"):
        return HttpResponseForbidden("Geçersiz işlem.")
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
        if InvoiceLine.objects.filter(order=order).exists() or StandaloneInvoiceLine.objects.filter(order=order, invoice__is_proforma=False).exists():
            messages.error(request, "Sipariş zaten faturaya alınmış; işlem yapılamaz.")
            return redirect("uninvoiced_shipped_orders")
        event = latest_status_event(order)
        if not event or (event.stage, event.value) != ("sevkiyat_durum", "gonderildi"):
            messages.error(request, "Siparişin güncel durumu Sevk Edildi değil.")
            return redirect("uninvoiced_shipped_orders")
        if action == "save":
            note = (request.POST.get("explanation") or "").strip()
            if not note:
                messages.error(request, "Açıklama zorunludur.")
                return redirect("uninvoiced_shipped_orders")
            InvoiceFreeDelivery.objects.update_or_create(order=order, defaults={"explanation": note, "created_by": request.user})
            messages.success(request, "Faturasız teslim kaydedildi.")
        else:
            InvoiceFreeDelivery.objects.filter(order=order).delete()
            messages.success(request, "Faturasız teslim kararı geri alındı.")
    return redirect("uninvoiced_shipped_orders")


@login_required
def order_invoice_finance_status(request, order_id):
    from core.views import order_scope_allows
    from .invoice_models import StandaloneInvoiceLine, InvoiceFreeDelivery
    order = get_object_or_404(Order, pk=order_id)
    if not order_scope_allows(request.user, order):
        return HttpResponseForbidden("Yetkiniz yok.")
    line = InvoiceLine.objects.filter(order_id=order_id).select_related("invoice").first()
    if line:
        return JsonResponse({"type":"invoice","label":"FT-" + str(line.invoice.shared_number.number), "url": reverse("invoice_detail", args=[line.invoice_id])})
    manual = StandaloneInvoiceLine.objects.filter(order_id=order_id, invoice__is_proforma=False).select_related("invoice").first()
    if manual:
        return JsonResponse({"type":"invoice","label":"FT-" + str(manual.invoice.shared_number.number), "url": reverse("standalone_invoice_edit", args=[manual.invoice_id])})
    from .invoice_models import LegacyInvoiceAcknowledgement
    legacy = LegacyInvoiceAcknowledgement.objects.filter(order_id=order_id).first()
    if legacy:
        return JsonResponse({"type":"legacy","explanation":legacy.note})
    free = InvoiceFreeDelivery.objects.filter(order_id=order_id).first()
    if free:
        return JsonResponse({"type":"free","explanation":free.explanation})
    return JsonResponse({"type":"none"})

@login_required
@require_POST
def standalone_invoice_delete_empty(request, invoice_id):
    """Same empty-draft deletion rules as ordinary invoices."""
    from .invoice_models import StandaloneInvoice, StandaloneInvoiceTransfer
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    with transaction.atomic():
        invoice = get_object_or_404(StandaloneInvoice.objects.select_for_update(), pk=invoice_id, is_proforma=False)
        if invoice.lines.exists():
            messages.error(request, "Yalnızca boş taslak faturalar silinebilir.")
            return redirect("invoice_list")
        if invoice.transfers.exclude(status="NOT_SENT").exists() or invoice.transfers.exclude(external_invoice_id="").exists():
            messages.error(request, "Muhasebe sistemine aktarılmış veya işlenmiş fatura silinemez.")
            return redirect("invoice_list")
        StandaloneInvoiceTransfer.objects.filter(invoice=invoice, status="NOT_SENT", external_invoice_id="").delete()
        invoice.delete()
    logging.getLogger(__name__).info("empty_standalone_invoice_deleted invoice_id=%s user_id=%s", invoice_id, request.user.pk)
    messages.success(request, "Boş fatura taslağı silindi.")
    return redirect("invoice_list")


@login_required
@require_POST
def standalone_invoice_list_control(request, invoice_id):
    from .invoice_models import StandaloneInvoice
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    action = request.POST.get("action")
    with transaction.atomic():
        inv = get_object_or_404(StandaloneInvoice.objects.select_for_update(), pk=invoice_id, is_proforma=False)
        if action == "official":
            number = request.POST.get("official_number", "").strip()
            if len(number) > 80:
                messages.error(request, "Resmî FT numarası en fazla 80 karakter olabilir.")
            else:
                inv.official_number = number
                inv.save(update_fields=["official_number"])
                messages.success(request, "Resmî FT numarası güncellendi.")
        elif action == "open_account":
            value = request.POST.get("label")
            if value not in ("open", "empty"):
                messages.error(request, "Geçersiz açık hesap seçimi.")
            elif inv.official_number:
                messages.error(request, "Resmî FT numarası olan kayıtta açık hesap seçilemez.")
            else:
                inv.show_open_account_in_list = value == "open"
                inv.save(update_fields=["show_open_account_in_list"])
        elif action == "platform":
            platform = request.POST.get("platform")
            value = request.POST.get("recorded")
            if platform not in ("bizimhesap", "parasut") or value not in ("no", "yes", "api", "skip"):
                messages.error(request, "Geçersiz durum.")
            else:
                # Manual changes affect only the MoliApp tracking label, never remote bookkeeping.
                field = "bizimhesap_display_status" if platform == "bizimhesap" else "parasut_display_status"
                setattr(inv, field, value)
                inv.save(update_fields=[field])
                messages.success(request, "Muhasebe takip durumu güncellendi (dış sistem değiştirilmedi).")
        else:
            messages.error(request, "Geçersiz işlem.")
    return redirect("invoice_list")
