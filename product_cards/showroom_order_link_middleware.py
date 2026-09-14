import json
import re

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.urls import reverse

from .models import ShowroomDraft
from .showroom_link_models import ShowroomOrderLink, ensure_showroom_folio


class ShowroomOrderLinkMiddleware:
    ORDER_RE = re.compile(r"^/order/(\d+)/$")
    SHOWROOM_RE = re.compile(r"^/urun-kartlari/showroom-foyu/kayit/(\d+)/$")
    SHOWROOM_EDIT_RE = re.compile(r"^/urun-kartlari/showroom-foyu/kayit/(\d+)/duzenle/$")
    SHOWROOM_EDIT_SAVE_RE = re.compile(r"^/urun-kartlari/showroom-foyu/kayit/(\d+)/duzenle/kaydet/$")
    SHOWROOM_ACTION_PATH = "/urun-kartlari/showroom-foyu/islem/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""

        # Silme işlemi tüm Föy durumlarında çalışsın. Siparişe dönüştürülmüş
        # Föy silinirse daha önce oluşturulmuş siparişler korunur.
        if request.method == "POST" and path == self.SHOWROOM_ACTION_PATH:
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}

            if payload.get("action") == "delete_saved":
                draft_id = payload.get("draft_id")
                if getattr(request, "user", None) and request.user.is_authenticated:
                    target = ShowroomDraft.objects.filter(
                        id=draft_id,
                        created_by=request.user,
                        status="TRANSFERRED",
                    ).first()
                    if target:
                        target.delete()
                        return JsonResponse({
                            "ok": True,
                            "message": "Föy silindi. Oluşturulmuş siparişler korunuyor.",
                        })

        # Eski edit view TRANSFERRED Föyleri kabul etmiyordu. Düzenleme isteği
        # boyunca geçici olarak APPROVED gösterip yanıt üretildikten sonra eski
        # durumuna döndürüyoruz. Böylece Föy düzenlenebilir ama sipariş geçmişi
        # ve 'siparişe dönüştürüldü' bilgisi kaybolmaz.
        edit_match = self.SHOWROOM_EDIT_RE.match(path) or self.SHOWROOM_EDIT_SAVE_RE.match(path)
        restore_transferred_id = None
        if edit_match and getattr(request, "user", None) and request.user.is_authenticated:
            draft = ShowroomDraft.objects.filter(
                pk=int(edit_match.group(1)),
                created_by=request.user,
                status="TRANSFERRED",
            ).first()
            if draft:
                restore_transferred_id = draft.id
                ShowroomDraft.objects.filter(pk=draft.id).update(status="APPROVED")

        try:
            response = self.get_response(request)
        finally:
            if restore_transferred_id:
                ShowroomDraft.objects.filter(pk=restore_transferred_id).update(status="TRANSFERRED")

        if getattr(response, "status_code", 200) != 200:
            return response
        content_type = response.get("Content-Type", "")
        if not content_type.startswith("text/html"):
            return response

        html = response.content.decode(response.charset or "utf-8")
        changed = False

        order_match = self.ORDER_RE.match(path)
        if order_match:
            link = (
                ShowroomOrderLink.objects
                .select_related("draft")
                .filter(order_id=int(order_match.group(1)))
                .first()
            )
            if link:
                folio = ensure_showroom_folio(link.draft)
                url = reverse("showroom_detail_page", kwargs={"draft_id": link.draft_id})
                badge = (
                    '<div class="info-item">'
                    '<span class="info-label">Föy No</span>'
                    f'<div class="info-value"><a href="{url}" '
                    'style="font-weight:850;color:#4055d8;text-decoration:none">'
                    f'Föy #{folio.number}</a></div></div>'
                )
                marker = '<div class="info-grid">'
                if marker in html and "Föy No" not in html:
                    html = html.replace(marker, marker + badge, 1)
                    changed = True

        showroom_match = self.SHOWROOM_RE.match(path)
        if showroom_match:
            draft = ShowroomDraft.objects.filter(pk=int(showroom_match.group(1))).first()
            if draft:
                folio = ensure_showroom_folio(draft)
                new_label = f"SİPARİŞ FÖYÜ · FÖY NO #{folio.number}"
                new_html = re.sub(r"SİPARİŞ FÖYÜ\s*·\s*#\d+", new_label, html, count=1)
                if new_html != html:
                    html = new_html
                    changed = True

                if draft.status == "TRANSFERRED":
                    # Müşteri ile paylaş butonunu tekrar göster.
                    actions_marker = '<div class="foy-actions-menu">'
                    share_url = reverse("staff_draft_share", kwargs={"draft_id": draft.id})
                    share_button = (
                        f'<a class="foy-share" href="{share_url}" target="_blank" rel="noopener">'
                        '<i class="bi bi-send"></i>Müşteri ile Paylaş</a>'
                    )
                    if actions_marker in html and share_url not in html:
                        html = html.replace(actions_marker, share_button + actions_marker, 1)
                        changed = True

                    # İşlemler menüsündeki tüm aksiyonları tekrar aç.
                    transferred_note = '<div class="foy-transferred-note">✓ Siparişe Dönüştürüldü</div>'
                    if transferred_note in html:
                        csrf = get_token(request)
                        status_url = reverse("showroom_change_status", kwargs={"draft_id": draft.id})
                        transfer_url = reverse("showroom_transfer_preview", kwargs={"draft_id": draft.id})
                        edit_url = reverse("showroom_edit_page", kwargs={"draft_id": draft.id})
                        full_actions = (
                            transferred_note
                            + '<form method="post" action="' + status_url + '" '
                              'onsubmit="return confirm(\'Bu Föy tekrar taslağa alınsın mı? Daha önce oluşturulmuş siparişler korunur.\')">'
                            + '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrf + '">'
                            + '<input type="hidden" name="target_status" value="PENDING">'
                            + '<button class="foy-action-item success" type="submit">'
                              '<i class="bi bi-arrow-repeat"></i>Taslağa Çevir</button></form>'
                            + '<a class="foy-action-item primary" href="' + transfer_url + '">'
                              '<i class="bi bi-bag-check"></i>Siparişleri Oluştur</a>'
                            + '<a class="foy-action-item" href="' + edit_url + '">'
                              '<i class="bi bi-pencil"></i>Düzenle</a>'
                            + '<div class="foy-action-divider"></div>'
                            + '<button type="button" id="foyDeleteBtn" class="foy-action-item danger">'
                              '<i class="bi bi-trash"></i>Sil</button>'
                        )
                        html = html.replace(transferred_note, full_actions, 1)
                        changed = True

        if changed:
            response.content = html.encode(response.charset or "utf-8")
            if response.has_header("Content-Length"):
                del response["Content-Length"]
        return response
