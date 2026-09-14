import re

from django.urls import reverse

from .models import ShowroomDraft
from .showroom_link_models import ShowroomOrderLink, ensure_showroom_folio


class ShowroomOrderLinkMiddleware:
    ORDER_RE = re.compile(r"^/order/(\d+)/$")
    SHOWROOM_RE = re.compile(r"^/urun-kartlari/showroom-foyu/kayit/(\d+)/$")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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

        if changed:
            response.content = html.encode(response.charset or "utf-8")
            if response.has_header("Content-Length"):
                del response["Content-Length"]
        return response
