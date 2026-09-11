from django.utils.html import escape

from .price_list_views import price_list


def showroom_page(request):
    response = price_list(request)

    if getattr(response, "status_code", None) != 200:
        return response

    html = response.content.decode(response.charset or "utf-8")
    html = html.replace("<th>İşlem</th>", "<th>Föye Ekle</th>", 1)

    marker = '<td><form method="post" action="/product-cards/fiyat-listesi/durum/">'
    if marker in html:
        parts = html.split(marker)
        rebuilt = [parts[0]]
        for part in parts[1:]:
            form_end = part.find("</form></td>")
            if form_end == -1:
                rebuilt.append(marker + part)
                continue

            form_html = part[:form_end]
            card_marker = 'name="card_id" value="'
            card_start = form_html.find(card_marker)
            card_id = ""
            if card_start != -1:
                card_start += len(card_marker)
                card_end = form_html.find('"', card_start)
                if card_end != -1:
                    card_id = form_html[card_start:card_end]

            rebuilt.append(
                '<td><button type="button" class="status-link showroom-add" '
                f'data-card-id="{escape(card_id)}">Föye Ekle</button></td>'
                + part[form_end + len("</form></td>"):]
            )
        html = "".join(rebuilt)

    response.content = html.encode(response.charset or "utf-8")
    return response
