import re

from django.urls import reverse

from .showroom_link_models import ShowroomOrderLink, ensure_showroom_folio


class ShowroomOrderLinkMiddleware:
    ORDER_RE = re.compile(r"^/order/(\d+)/$")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        match = self.ORDER_RE.match(request.path or "")
        if not match:
            return response
        if getattr(response, "status_code", 200) != 200:
            return response
        content_type = response.get("Content-Type", "")
        if not content_type.startswith("text/html"):
            return response

        link = (
            ShowroomOrderLink.objects
            .select_related("draft")
            .filter(order_id=int(match.group(1)))
            .first()
        )
        if not link:
            return response

        folio = ensure_showroom_folio(link.draft)
        url = reverse("showroom_detail_page", kwargs={"draft_id": link.draft_id})
        badge = (
            '<div class="info-item">'
            '<span class="info-label">Föy No</span>'
            f'<div class="info-value"><a href="{url}" '
            'style="font-weight:850;color:#4055d8;text-decoration:none">'
            f'Föy #{folio.number}</a></div></div>'
        )

        html = response.content.decode(response.charset or "utf-8")
        marker = '<div class="info-grid">'
        if marker in html and "Föy No" not in html:
            html = html.replace(marker, marker + badge, 1)
            response.content = html.encode(response.charset or "utf-8")
            if response.has_header("Content-Length"):
                del response["Content-Length"]
        return response
