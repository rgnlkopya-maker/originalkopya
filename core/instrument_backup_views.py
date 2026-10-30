"""Manual-only, idempotent backup of cheque records and private photos to Google Drive."""
import io
import json
import logging
import os
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.utils import timezone
from googleapiclient.http import MediaIoBaseUpload
from openpyxl import Workbook

from .instrument_models import NegotiableInstrument, InstrumentAttachment, InstrumentBackupRun
from .instrument_attachment_views import storage
from .instrument_drive_oauth import drive_service, connected

logger = logging.getLogger(__name__)
ROOT_ID = "1DGz7uvoeydXbuzze9HVFZbUwcaV8oW7p"


def _check_parent(drive):
    root = drive.files().get(fileId=ROOT_ID, fields="id,name,mimeType,capabilities(canAddChildren)", supportsAllDrives=True).execute()
    if root.get("mimeType") != "application/vnd.google-apps.folder" or not root.get("capabilities", {}).get("canAddChildren", False):
        raise PermissionError("Google Drive ana klasörüne dosya ekleme izni bulunmuyor.")


def _folder(drive, parent, name):
    safe = name.replace("'", "\\'")
    query = f"'{parent}' in parents and name = '{safe}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    found = drive.files().list(q=query, fields="files(id,name),nextPageToken", pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True).execute().get("files", [])
    if found:
        return found[0]["id"]
    return drive.files().create(body={"name":name,"mimeType":"application/vnd.google-apps.folder","parents":[parent]}, fields="id", supportsAllDrives=True).execute()["id"]


def _existing_file(drive, parent, name):
    safe = name.replace("'", "\\'")
    query = f"'{parent}' in parents and name = '{safe}' and trashed = false"
    found = drive.files().list(q=query, fields="files(id,name,size,md5Checksum),nextPageToken", pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True).execute().get("files", [])
    return found[0] if found else None


def _upload(drive, parent, name, data, mime):
    result = drive.files().create(
        body={"name":name,"parents":[parent],"description":"MoliApp Çek/Senet manuel yedeği"},
        media_body=MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False),
        fields="id,name,size", supportsAllDrives=True
    ).execute()
    if int(result.get("size", -1)) != len(data):
        raise RuntimeError("Drive yükleme boyutu doğrulanamadı: " + name)
    return result


def _rows(records):
    for item in records:
        yield {
            "sira_no":item.pk,"tur":item.kind,"islem":item.direction,"musteri_id":item.customer_id,
            "musteri":item.customer.ad if item.customer else "","cek_sahibi":item.issuer_name,
            "alinan_kisi":item.received_from,"verilen_firma_banka":item.given_to,
            "banka":item.bank,"sube":item.branch,"cek_no":item.document_number,
            "tutar":str(item.amount),"para_birimi":item.currency,
            "duzenleme_tarihi":str(item.issue_date or ""),"alinan_tarih":str(item.transaction_date or ""),
            "verilen_tarih":str(item.given_date or ""),"vade":str(item.due_date),
            "durum":item.status,"aciklama":item.note,
            "olusturulma":item.created_at.isoformat(),"guncelleme":item.updated_at.isoformat(),
            "cirantalar":[{"sira":e.sequence,"isim":e.name,"not":e.note} for e in item.endorsers.all()],
            "hareketler":[{"islem":e.action,"aciklama":e.description,"tarih":e.created_at.isoformat(),"kullanici_id":e.actor_id} for e in item.movements.all()],
            "fotograflar":[{"sira":p.sequence,"dosya":p.storage_path.rsplit("/",1)[-1],"storage_path":p.storage_path} for p in item.attachments.all()],
        }


@login_required
@require_POST
def instrument_backup(request):
    user=request.user
    if not (user.is_superuser or user.groups.filter(name__in=["patron","mudur"]).exists()):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    run = InstrumentBackupRun.objects.create()
    try:
        if not connected():
            run.error_code = "NOT_CONNECTED"
            run.completed_at = timezone.now()
            run.save(update_fields=["error_code", "completed_at"])
            messages.error(request, "Once Google Drive hesabini baglayin.", extra_tags="instrument_notice")
            return redirect("instrument_list")
        drive=drive_service()
        _check_parent(drive)
        root=ROOT_ID
        photos_dir=_folder(drive, root, "Fotograflar")
        excel_dir=_folder(drive, root, "Excel Yedekleri")
        data_dir=_folder(drive, root, "Veri Yedekleri")
        records=list(NegotiableInstrument.objects.select_related("customer").prefetch_related("endorsers","movements","attachments").order_by("pk"))
        photos_new=0
        for record in records:
            attachments=list(record.attachments.all())
            if not attachments:
                continue
            photo_folder=_folder(drive, photos_dir, f"Cek-{record.pk}")
            for photo in attachments:
                filename=photo.storage_path.rsplit("/",1)[-1]
                existing=_existing_file(drive, photo_folder, filename)
                if existing and int(existing.get("size") or 0)>0:
                    continue
                if existing:
                    raise RuntimeError("Drive dosyası boş görünüyor: "+filename)
                data=storage().download(photo.storage_path)
                if not data:
                    raise RuntimeError("Supabase fotoğrafı okunamadı: "+filename)
                ext=filename.lower().rsplit(".",1)[-1]
                mime={"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}.get(ext,"application/octet-stream")
                _upload(drive,photo_folder,filename,data,mime)
                photos_new+=1
        rows=list(_rows(records))
        wb=Workbook()
        ws=wb.active
        ws.title="Çek Senet Listesi"
        headings=["Sıra No","Tür","İşlem","Müşteri","Banka","Evrak No","Tutar","Para Birimi","Alınan Tarih","Vade","Durum","Verilen Tarih","Verilen Firma / Banka","Açıklama"]
        ws.append(headings)
        # Excel is human-readable; JSON retains the raw codes for recovery.
        kind_labels = dict(NegotiableInstrument.KIND)
        direction_labels = dict(NegotiableInstrument.DIRECTION)
        status_labels = dict(NegotiableInstrument.STATUS)
        for x in rows:
            ws.append([
                x["sira_no"],
                kind_labels.get(x["tur"], x["tur"]),
                direction_labels.get(x["islem"], x["islem"]),
                x["musteri"], x["banka"], x["cek_no"],
                float(x["tutar"]), "TL" if x["para_birimi"] == "TRY" else x["para_birimi"],
                x["alinan_tarih"], x["vade"],
                status_labels.get(x["durum"], x["durum"]),
                x["verilen_tarih"], x["verilen_firma_banka"], x["aciklama"],
            ])
            ws.cell(ws.max_row, 7).number_format = "#,##0.00"
        for col in ws.columns:
            letter=col[0].column_letter
            ws.column_dimensions[letter].width=min(50,max(14,max(len(str(cell.value or "")) for cell in col[:200])+2))
        binary=io.BytesIO()
        wb.save(binary)
        stamp=timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
        base=f"Cek_Listesi_{stamp}"
        _upload(drive,excel_dir,base+".xlsx",binary.getvalue(),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        payload={"backup_schema":1,"created_at":timezone.now().isoformat(),"records":rows}
        _upload(drive,data_dir,"Cek_Verileri_"+stamp+".json",json.dumps(payload,ensure_ascii=False,indent=2).encode("utf-8"),"application/json")
        run.success = True
        run.completed_at = timezone.now()
        run.record_count = len(records)
        run.new_photo_count = photos_new
        run.save(update_fields=["success","completed_at","record_count","new_photo_count"])
        messages.success(request, f"Drive yedekleme tamamlandı: {len(records)} çek/senet, {photos_new} yeni fotoğraf, Excel ve JSON kaydedildi.", extra_tags="instrument_notice")
    except Exception as exc:
        run.error_code = "BACKUP_FAILED"
        run.completed_at = timezone.now()
        run.save(update_fields=["error_code","completed_at"])
        logger.exception("Manual check backup failed")
        messages.error(request, "Google Drive yedekleme tamamlanamadı. Google Drive bağlantısını ve klasör yetkisini kontrol edin. Fotoğraflar ve kayıtlar silinmedi.", extra_tags="instrument_notice")
    return redirect("instrument_list")
