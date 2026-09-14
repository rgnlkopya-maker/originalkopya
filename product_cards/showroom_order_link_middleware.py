import json
import re

from django.http import JsonResponse
from django.urls import reverse

from .models import ShowroomDraft
from .showroom_link_models import ShowroomOrderLink, ensure_showroom_folio


class ShowroomOrderLinkMiddleware:
    ORDER_RE = re.compile(r"^/order/(\d+)/$")
    SHOWROOM_RE = re.compile(r"^/urun-kartlari/showroom-foyu/kayit/(\d+)/$")
    SHOWROOM_ACTION_PATH = "/urun-kartlari/showroom-foyu/islem/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Normal showroom action view only deletes PENDING / APPROVED sheets.
        # Keep that behavior, but also allow the owner to delete a sheet after
        # it has already been converted to orders. Orders themselves are NOT
        # deleted; only the folio and its ShowroomOrderLink rows disappear.
        if request.method == "POST" and (request.path or "") == self.SHOWROOM_ACTION_PATH:
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

        response = self.get_response(request)

        if getattr(response, "status_code", 200) != 200:
            return response
        content_type = response.get("Content-Type", "")
        if not content_type.startswith("text/html"):
            return response

        path = request.path or ""
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

                # The template intentionally hides edit/delete actions after
                # transfer. Re-add only the delete action for transferred sheets.
                if draft.status == "TRANSFERRED" and 'id="foyDeleteBtn"' not in html:
                    transferred_note = '<div class="foy-transferred-note">✓ Siparişe Dönüştürüldü</div>'
                    delete_action = (
                        transferred_note
                        + '<div class="foy-action-divider"></div>'
                        + '<button type="button" id="foyDeleteBtn" class="foy-action-item danger">'
                        + '<i class="bi bi-trash"></i>Sil</button>'
                    )
                    if transferred_note in html:
                        html = html.replace(transferred_note, delete_action, 1)
                        changed = True

        if changed:
            response.content = html.encode(response.charset or "utf-8")
            if response.has_header("Content-Length"):
                del response["Content-Length"]
        return response
