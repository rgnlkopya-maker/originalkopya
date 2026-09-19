from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from core.customer_models import CustomerDetail
from .models import ShowroomDraft
from .price_list_views import _can_manage
from .showroom_views import _serialize_draft, _draft_summary



LANGUAGES = {
    "tr": "Türkçe", "en": "English", "de": "Deutsch", "fr": "Français",
    "ar": "العربية", "fa": "فارسی", "it": "Italiano", "nl": "Nederlands",
}

TRANSLATIONS = {
"tr":{"title":"SİPARİŞ FÖYÜ","subtitle":"Sipariş / Üretim Föyü","folio_no":"Föy No","customer":"Müşteri","no_customer":"Müşteri seçilmedi","taken_by":"Siparişi Alan","status":"Durum","date":"Tarih","customer_info":"Müşteri Bilgileri","contact":"Moli Tekstil İletişim","authorized":"Yetkili","phone":"Telefon","country":"Ülke","delivery":"Teslimat","address":"Adres","invoice_address":"Fatura Adresi","foreign_trade":"Dış Ticaret","unit_price":"Birim Fiyat","product_total":"Ürün Toplamı","color":"Renk","size":"Beden","qty":"Adet","description":"Açıklama","line_total":"Satır Toplamı","no_items":"Bu föyde ürün bulunmuyor.","payment_plan":"TAHSİLAT / ÖDEME PLANI","type":"Tür","method":"Şekil","amount":"Tutar","payment":"Tahsilat","due":"Söz / Vade","note":"Not","subtotal":"Ara Toplam","discount":"İndirim","vat":"KDV","folio_total":"Föy Toplamı","previous_balance":"Eski Bakiye","grand_total":"GENEL TOPLAM","collected":"Tahsil Edilen","remaining":"KALAN","back":"Geri","print":"Yazdır","language":"Çıktı dili","draft":"Taslak","approved":"Onaylanan","transferred":"Siparişe Aktarıldı"},
"en":{"title":"ORDER FORM","subtitle":"Order / Production Form","folio_no":"Form No","customer":"Customer","no_customer":"No customer selected","taken_by":"Order Taken By","status":"Status","date":"Date","customer_info":"Customer Information","contact":"Moli Textile Contact","authorized":"Contact Person","phone":"Phone","country":"Country","delivery":"Delivery","address":"Address","invoice_address":"Billing Address","foreign_trade":"Foreign Trade","unit_price":"Unit Price","product_total":"Product Total","color":"Color","size":"Size","qty":"Qty","description":"Description","line_total":"Line Total","no_items":"No products in this form.","payment_plan":"PAYMENT PLAN","type":"Type","method":"Method","amount":"Amount","payment":"Payment","due":"Promise / Due","note":"Note","subtotal":"Subtotal","discount":"Discount","vat":"VAT","folio_total":"Form Total","previous_balance":"Previous Balance","grand_total":"GRAND TOTAL","collected":"Collected","remaining":"REMAINING","back":"Back","print":"Print","language":"Output language","draft":"Draft","approved":"Approved","transferred":"Transferred to Order"},
"de":{"title":"BESTELLFORMULAR","subtitle":"Bestell- / Produktionsformular","folio_no":"Formular Nr.","customer":"Kunde","no_customer":"Kein Kunde ausgewählt","taken_by":"Auftrag aufgenommen von","status":"Status","date":"Datum","customer_info":"Kundeninformationen","contact":"Moli Tekstil Kontakt","authorized":"Ansprechpartner","phone":"Telefon","country":"Land","delivery":"Lieferung","address":"Adresse","invoice_address":"Rechnungsadresse","foreign_trade":"Außenhandel","unit_price":"Stückpreis","product_total":"Produktsumme","color":"Farbe","size":"Größe","qty":"Menge","description":"Beschreibung","line_total":"Zeilensumme","no_items":"Keine Produkte in diesem Formular.","payment_plan":"ZAHLUNGSPLAN","type":"Typ","method":"Art","amount":"Betrag","payment":"Zahlung","due":"Zusage / Fälligkeit","note":"Notiz","subtotal":"Zwischensumme","discount":"Rabatt","vat":"MwSt.","folio_total":"Formularsumme","previous_balance":"Alter Saldo","grand_total":"GESAMTSUMME","collected":"Bezahlt","remaining":"RESTBETRAG","back":"Zurück","print":"Drucken","language":"Ausgabesprache","draft":"Entwurf","approved":"Genehmigt","transferred":"In Bestellung übertragen"},
"fr":{"title":"BON DE COMMANDE","subtitle":"Bon de commande / production","folio_no":"N° de fiche","customer":"Client","no_customer":"Aucun client sélectionné","taken_by":"Commande prise par","status":"Statut","date":"Date","customer_info":"Informations client","contact":"Contact Moli Tekstil","authorized":"Contact","phone":"Téléphone","country":"Pays","delivery":"Livraison","address":"Adresse","invoice_address":"Adresse de facturation","foreign_trade":"Commerce extérieur","unit_price":"Prix unitaire","product_total":"Total produit","color":"Couleur","size":"Taille","qty":"Qté","description":"Description","line_total":"Total ligne","no_items":"Aucun produit dans cette fiche.","payment_plan":"PLAN DE PAIEMENT","type":"Type","method":"Mode","amount":"Montant","payment":"Paiement","due":"Promesse / Échéance","note":"Note","subtotal":"Sous-total","discount":"Remise","vat":"TVA","folio_total":"Total fiche","previous_balance":"Solde précédent","grand_total":"TOTAL GÉNÉRAL","collected":"Encaissé","remaining":"RESTE","back":"Retour","print":"Imprimer","language":"Langue de sortie","draft":"Brouillon","approved":"Approuvé","transferred":"Transféré en commande"},
"ar":{"title":"نموذج الطلب","subtitle":"نموذج الطلب / الإنتاج","folio_no":"رقم النموذج","customer":"العميل","no_customer":"لم يتم اختيار عميل","taken_by":"مستلم الطلب","status":"الحالة","date":"التاريخ","customer_info":"معلومات العميل","contact":"معلومات اتصال Moli Tekstil","authorized":"جهة الاتصال","phone":"الهاتف","country":"الدولة","delivery":"التسليم","address":"العنوان","invoice_address":"عنوان الفاتورة","foreign_trade":"التجارة الخارجية","unit_price":"سعر الوحدة","product_total":"إجمالي المنتج","color":"اللون","size":"المقاس","qty":"الكمية","description":"الوصف","line_total":"إجمالي السطر","no_items":"لا توجد منتجات في هذا النموذج.","payment_plan":"خطة الدفع","type":"النوع","method":"الطريقة","amount":"المبلغ","payment":"الدفع","due":"الوعد / الاستحقاق","note":"ملاحظة","subtotal":"المجموع الفرعي","discount":"الخصم","vat":"ضريبة القيمة المضافة","folio_total":"إجمالي النموذج","previous_balance":"الرصيد السابق","grand_total":"المجموع الكلي","collected":"المبلغ المحصل","remaining":"المتبقي","back":"رجوع","print":"طباعة","language":"لغة الإخراج","draft":"مسودة","approved":"معتمد","transferred":"تم التحويل إلى طلب"},
"fa":{"title":"فرم سفارش","subtitle":"فرم سفارش / تولید","folio_no":"شماره فرم","customer":"مشتری","no_customer":"مشتری انتخاب نشده","taken_by":"ثبت‌کننده سفارش","status":"وضعیت","date":"تاریخ","customer_info":"اطلاعات مشتری","contact":"اطلاعات تماس Moli Tekstil","authorized":"شخص تماس","phone":"تلفن","country":"کشور","delivery":"تحویل","address":"آدرس","invoice_address":"آدرس صورتحساب","foreign_trade":"تجارت خارجی","unit_price":"قیمت واحد","product_total":"جمع محصول","color":"رنگ","size":"سایز","qty":"تعداد","description":"توضیحات","line_total":"جمع ردیف","no_items":"محصولی در این فرم وجود ندارد.","payment_plan":"برنامه پرداخت","type":"نوع","method":"روش","amount":"مبلغ","payment":"پرداخت","due":"تعهد / سررسید","note":"یادداشت","subtotal":"جمع جزء","discount":"تخفیف","vat":"مالیات","folio_total":"جمع فرم","previous_balance":"مانده قبلی","grand_total":"جمع کل","collected":"دریافت‌شده","remaining":"مانده","back":"بازگشت","print":"چاپ","language":"زبان خروجی","draft":"پیش‌نویس","approved":"تأییدشده","transferred":"به سفارش منتقل شد"},
"it":{"title":"MODULO D'ORDINE","subtitle":"Modulo ordine / produzione","folio_no":"N. modulo","customer":"Cliente","no_customer":"Nessun cliente selezionato","taken_by":"Ordine acquisito da","status":"Stato","date":"Data","customer_info":"Informazioni cliente","contact":"Contatti Moli Tekstil","authorized":"Referente","phone":"Telefono","country":"Paese","delivery":"Consegna","address":"Indirizzo","invoice_address":"Indirizzo di fatturazione","foreign_trade":"Commercio estero","unit_price":"Prezzo unitario","product_total":"Totale prodotto","color":"Colore","size":"Taglia","qty":"Qtà","description":"Descrizione","line_total":"Totale riga","no_items":"Nessun prodotto in questo modulo.","payment_plan":"PIANO DI PAGAMENTO","type":"Tipo","method":"Metodo","amount":"Importo","payment":"Pagamento","due":"Promessa / Scadenza","note":"Nota","subtotal":"Subtotale","discount":"Sconto","vat":"IVA","folio_total":"Totale modulo","previous_balance":"Saldo precedente","grand_total":"TOTALE GENERALE","collected":"Incassato","remaining":"RESIDUO","back":"Indietro","print":"Stampa","language":"Lingua di output","draft":"Bozza","approved":"Approvato","transferred":"Trasferito all'ordine"},
"nl":{"title":"BESTELFORMULIER","subtitle":"Bestel- / productieformulier","folio_no":"Formuliernr.","customer":"Klant","no_customer":"Geen klant geselecteerd","taken_by":"Bestelling opgenomen door","status":"Status","date":"Datum","customer_info":"Klantgegevens","contact":"Contact Moli Tekstil","authorized":"Contactpersoon","phone":"Telefoon","country":"Land","delivery":"Levering","address":"Adres","invoice_address":"Factuuradres","foreign_trade":"Buitenlandse handel","unit_price":"Eenheidsprijs","product_total":"Producttotaal","color":"Kleur","size":"Maat","qty":"Aantal","description":"Beschrijving","line_total":"Regeltotaal","no_items":"Geen producten in dit formulier.","payment_plan":"BETALINGSPLAN","type":"Type","method":"Methode","amount":"Bedrag","payment":"Betaling","due":"Toezegging / Vervaldatum","note":"Notitie","subtotal":"Subtotaal","discount":"Korting","vat":"Btw","folio_total":"Formuliertotaal","previous_balance":"Vorig saldo","grand_total":"EINDTOTAAL","collected":"Ontvangen","remaining":"RESTEREND","back":"Terug","print":"Afdrukken","language":"Uitvoertaal","draft":"Concept","approved":"Goedgekeurd","transferred":"Overgezet naar bestelling"}
}


def _to_decimal(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


@login_required
def showroom_print_page(request, draft_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    draft = get_object_or_404(
        ShowroomDraft.objects.select_related("customer").prefetch_related("items__product_card__urun", "payments"),
        id=draft_id,
        created_by=request.user,
        status__in=["PENDING", "APPROVED", "TRANSFERRED"],
    )

    customer_detail = None
    if draft.customer_id:
        customer_detail = CustomerDetail.objects.filter(customer_id=draft.customer_id).first()

    data = _serialize_draft(draft)
    summary = _draft_summary(draft)
    status_label = {
        "PENDING": "Taslak",
        "APPROVED": "Onaylanan",
        "TRANSFERRED": "Siparişe Aktarıldı",
    }[draft.status]

    print_items = []
    for item in data["items"]:
        unit_price = _to_decimal(item.get("anlasilan_fiyat"))
        lines = []
        item_total = Decimal("0")
        for row in item.get("satirlar", []):
            try:
                qty = max(1, int(row.get("adet") or 1))
            except (TypeError, ValueError):
                qty = 1
            sizes = row.get("bedenler") or [""]
            for size in sizes:
                line_total = unit_price * qty
                item_total += line_total
                lines.append({"renk": row.get("renk") or "", "beden": size or "", "adet": qty, "aciklama": row.get("aciklama") or "", "unit_price": unit_price, "line_total": line_total})
        print_items.append({"urun_kodu": item.get("urun_kodu") or "", "unit_price": unit_price, "item_total": item_total, "lines": lines})

    return render(request, "product_cards/showroom_print.html", {
        "draft": draft,
        "customer_detail": customer_detail,
        "items": print_items,
        "payments": draft.payments.all().order_by("due_date", "payment_date", "id"),
        "summary": summary,
        "status_label": status_label,
    })
