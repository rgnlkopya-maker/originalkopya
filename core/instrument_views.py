from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Musteri
from .instrument_models import NegotiableInstrument, InstrumentEndorser, InstrumentMovement
from product_cards.invoice_models import BizimHesapCustomerMapping


def _manager(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists())


class InstrumentForm(forms.ModelForm):
    class Meta:
        model = NegotiableInstrument
        fields = ["kind", "direction", "customer", "issuer_name", "given_to", "bank", "branch", "document_number", "amount", "currency", "issue_date", "transaction_date", "given_date", "due_date", "status", "note"]
        labels = {
            "kind": "Belge Türü", "direction": "Alınan / Verilen", "customer": "Müşteri",
            "issuer_name": "Çek Sahibi / Senet Borçlusu",
            "given_to": "Kime Verildi", "bank": "Banka", "branch": "Şube",
            "document_number": "Çek / Senet Numarası", "amount": "Tutar",
            "currency": "Para Birimi", "issue_date": "Düzenleme Tarihi", "transaction_date": "İşlem Tarihi", "given_date": "Verilen Tarih",
            "due_date": "Vade Tarihi", "status": "Durum", "note": "Açıklama",
        }
        widgets = {"issue_date":forms.DateInput(attrs={"type":"date"}), "transaction_date":forms.DateInput(attrs={"type":"date"}), "given_date":forms.DateInput(attrs={"type":"date"}), "due_date":forms.DateInput(attrs={"type":"date"}), "note":forms.Textarea(attrs={"rows":3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Musteri.objects.all().order_by("ad")
        self.fields["customer"].required = False
        self.fields["customer"].empty_label = "Cari seçilmedi"


@login_required
def instrument_list(request):
    if not _manager(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    from django.db.models import Exists, OuterRef
    from .instrument_models import InstrumentPhoto
    records = NegotiableInstrument.objects.select_related("customer", "customer__bizimhesap_mapping").annotate(
        has_front_photo=Exists(InstrumentPhoto.objects.filter(instrument_id=OuterRef("pk"), side="FRONT")),
        has_back_photo=Exists(InstrumentPhoto.objects.filter(instrument_id=OuterRef("pk"), side="BACK")),
    )
    direction = request.GET.get("direction")
    kind = request.GET.get("kind")
    status = request.GET.get("status")
    if direction in ("IN", "OUT"): records = records.filter(direction=direction)
    if kind in ("CHECK", "NOTE"): records = records.filter(kind=kind)
    if status in dict(NegotiableInstrument.STATUS): records = records.filter(status=status)
    term = request.GET.get("q", "").strip()
    if term:
        from django.db.models import Q
        records = records.filter(Q(issuer_name__icontains=term)|Q(given_to__icontains=term)|Q(document_number__icontains=term)|Q(customer__ad__icontains=term))
    return render(request, "core/instrument_list.html", {"records": records[:300], "kinds":NegotiableInstrument.KIND, "statuses":NegotiableInstrument.STATUS, "customers":Musteri.objects.all().order_by("ad"), "currencies":NegotiableInstrument._meta.get_field("currency").choices})


@login_required
@require_POST
def instrument_inline_add(request):
    if not _manager(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    data = request.POST.copy()
    # The inline table uses the same validated model fields as the detail form.
    if data.get("direction") not in ("IN", "OUT"):
        data["direction"] = "IN"
    if not data.get("status"):
        data["status"] = "PORTFOLIO" if data.get("direction") == "IN" else "ISSUED"
    customer_id = data.get("customer", "")
    customer = Musteri.objects.filter(pk=customer_id, aktif=True).first() if customer_id.isdigit() else None
    if customer:
        data["issuer_name"] = customer.ad
    form = InstrumentForm(data)
    if not customer:
        form.add_error("customer", "Müşteri seçilmelidir.")
    if not form.is_valid():
        messages.error(request, "Satır kaydedilemedi: " + "; ".join(
            f"{field}: {', '.join(str(e) for e in errors)}"
            for field, errors in form.errors.items()
        ))
        return redirect("instrument_list")
    with transaction.atomic():
        record = form.save(commit=False)
        record.created_by = request.user
        if record.customer_id:
            record.received_from = record.customer.ad
            record.issuer_name = record.customer.ad
        record.save()
        InstrumentMovement.objects.create(
            instrument=record, actor=request.user, action="CREATED",
            description="Çek/senet liste üzerinden kaydedildi."
        )
    messages.success(request, "Yeni çek/senet satırı kaydedildi.")
    return redirect("instrument_list")


@login_required
@require_POST
def instrument_inline_status_update(request, pk):
    if not _manager(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    data = request.POST.copy()
    with transaction.atomic():
        record = get_object_or_404(NegotiableInstrument.objects.select_for_update(), pk=pk)
        customer_id = data.get("customer")
        customer = Musteri.objects.filter(pk=customer_id).first() if customer_id and customer_id.isdigit() else None
        if not customer:
            messages.error(request, "Müşteri listeden seçilmelidir; kayıtlı olmayan müşteri kaydedilemez.")
            return redirect("instrument_list")
        if not customer.aktif and record.customer_id != customer.pk:
            messages.error(request, "Pasif müşteri yeni kayıt olarak seçilemez.")
            return redirect("instrument_list")
        data["issuer_name"] = customer.ad
        data["received_from"] = customer.ad
        # Keep detail-only fields unchanged when saving a table row.
        for key in ("bank", "branch", "document_number", "issue_date", "note"):
            if key not in data:
                val = getattr(record, key)
                data[key] = val.isoformat() if hasattr(val, "isoformat") else (val or "")
        form = InstrumentForm(data, instance=record)
        if not form.is_valid():
            messages.error(request, "Satır kaydedilemedi: " + "; ".join(
                f"{field}: {', '.join(str(e) for e in errors)}"
                for field, errors in form.errors.items()
            ))
            return redirect("instrument_list")
        updated = form.save(commit=False)
        changed = list(form.changed_data)
        updated.received_from = customer.ad
        if changed or record.received_from != updated.received_from:
            updated.save()
            InstrumentMovement.objects.create(
                instrument=updated, actor=request.user, action="UPDATED",
                description="Liste üzerinden güncellendi: " + ", ".join(changed or ["müşteri"])
            )
    messages.success(request, "Çek/senet satırı kaydedildi.")
    return redirect("instrument_list")


@login_required
def instrument_edit(request, pk=None):
    if not _manager(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    instrument = get_object_or_404(NegotiableInstrument, pk=pk) if pk else None
    if request.method == "POST":
        form = InstrumentForm(request.POST, instance=instrument)
        if form.is_valid():
            with transaction.atomic():
                record = form.save(commit=False)
                if not record.pk: record.created_by = request.user
                was_new = not bool(record.pk)
                if record.direction == "IN":
                    if not record.customer_id:
                        form.add_error("customer", "Alınan çek/senet için müşteri seçilmelidir.")
                if form.errors:
                    return render(request, "core/instrument_form.html", {"form": form, "instrument": instrument})
                record.received_from = record.customer.ad if record.customer_id else ""
                record.save()
                InstrumentMovement.objects.create(instrument=record, actor=request.user, action="CREATED" if was_new else "UPDATED", description="Çek/senet kaydı oluşturuldu." if was_new else "Çek/senet bilgileri güncellendi.")
            messages.success(request, "Çek/senet kaydedildi.")
            return redirect("instrument_detail", pk=record.pk)
    else:
        form = InstrumentForm(instance=instrument)
    return render(request, "core/instrument_form.html", {"form":form, "instrument":instrument})


@login_required
def instrument_detail(request, pk):
    if not _manager(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    record = get_object_or_404(NegotiableInstrument.objects.select_related("customer"), pk=pk)
    mapping = BizimHesapCustomerMapping.objects.filter(customer=record.customer).first() if record.customer_id else None
    return render(request, "core/instrument_detail.html", {"record":record,"mapping":mapping})


@login_required
@require_POST
def instrument_endorser_add(request, pk):
    if not _manager(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    record = get_object_or_404(NegotiableInstrument, pk=pk)
    name = request.POST.get("name", "").strip()
    if not name or len(name)>250:
        messages.error(request, "Geçerli ciranta adı girin.")
    else:
        with transaction.atomic():
            from django.db.models import Max
            seq = (InstrumentEndorser.objects.filter(instrument=record).aggregate(n=Max("sequence"))["n"] or 0)+1
            InstrumentEndorser.objects.create(instrument=record, sequence=seq, name=name, note=request.POST.get("note","")[:300])
            InstrumentMovement.objects.create(instrument=record,actor=request.user,action="ENDORSEMENT_ADDED",description=f"{seq}. ciranta: {name}")
        messages.success(request, "Ciranta kaydedildi.")
    return redirect("instrument_detail", pk=pk)


@login_required
@require_POST
def instrument_mapping_save(request, pk):
    if not _manager(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    record = get_object_or_404(NegotiableInstrument, pk=pk)
    if not record.customer_id:
        messages.error(request, "Önce cari hesabına işlenecek müşteriyi seçin.")
        return redirect("instrument_detail", pk=pk)
    code = request.POST.get("external_customer_id", "").strip()
    if not code or len(code)>100 or any(ord(ch)<32 for ch in code):
        messages.error(request, "Geçerli BizimHesap cari kodu girin.")
        return redirect("instrument_detail", pk=pk)
    try:
        with transaction.atomic():
            if BizimHesapCustomerMapping.objects.filter(external_customer_id=code).exclude(customer_id=record.customer_id).exists():
                messages.error(request, "Bu BizimHesap cari kodu başka bir müşteriye eşleştirilmiş.")
                return redirect("instrument_detail", pk=pk)
            BizimHesapCustomerMapping.objects.update_or_create(customer_id=record.customer_id,defaults={"external_customer_id":code,"confirmed_by":request.user})
    except IntegrityError:
        messages.error(request, "Cari eşleştirmesi çakıştı.")
    else:
        messages.success(request, "Ortak cari eşleştirmesi kaydedildi. Faturalar da aynı kaydı kullanacak.")
    return redirect("instrument_detail", pk=pk)
