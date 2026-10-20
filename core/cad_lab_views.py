"""Isolated CAD laboratory: read-only DXF preview."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.utils.html import escape
from django.views.decorators.http import require_http_methods
from app_settings.access import has_full_access
from core.cad_dxf_reader import MAX_BYTES, parse_pattern_dxf
from core.cad_part_assignment import part_assignment_ui
from core.cad_parametric_preview import render_bodice

@login_required
@require_http_methods(["GET", "POST"])
def cad_lab(request):
    if not has_full_access(request.user):
        return HttpResponse("Bu bölüme erişim yetkiniz yok.", status=403)
    error, drawing, summary, unit = "", "", "", ""
    if request.method == "POST":
        upload = request.FILES.get("pattern")
        if not upload:
            error = "Bir DXF dosyası seçin."
        elif not upload.name.lower().endswith(".dxf"):
            error = "Yalnızca .dxf dosyası yükleyin."
        elif upload.size > MAX_BYTES:
            error = "Dosya 3 MB sınırını aşıyor."
        else:
            try:
                result = parse_pattern_dxf(upload.read(MAX_BYTES + 1))
                drawing = part_assignment_ui(result)
                units = "mm" if result["units"] == 4 else "tanımsız; mm doğrulanmadı"
                unit = str(result["units"])
                summary = f'{len(result["paths"])} çizim öğesi · {result["points"]} nokta · {len(result["layers"])} katman · birim: {units}'
            except ValueError as exc:
                error = str(exc)
    if request.method == "POST" and request.POST.get("mode") == "measure":
        try:
            drawing = render_bodice(request.POST)
            summary = "Ölçülerden oluşturulmuş deneysel 5 parçalı şema; kesime uygun değildir."
            error = ""
        except (ValueError, KeyError) as exc:
            error = "Ölçüleri kontrol edin: " + escape(str(exc))
            drawing = ""
    csrf = escape(get_token(request))
    html = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Moli CAD Laboratuvarı</title>
<style>body{font:16px system-ui;background:#f3f6fb;color:#172238;margin:0;padding:16px}main{max-width:1100px;margin:auto}section{background:white;border-radius:14px;padding:20px;margin:12px 0;box-shadow:0 1px 5px #0001}h1{font-size:25px;margin:0 0 8px}p{line-height:1.5}.warn{background:#fff2d6;padding:12px;border-radius:8px}.error{background:#ffe4e4;padding:12px;border-radius:8px}button{background:#174a9d;color:white;border:0;border-radius:8px;padding:12px 16px;font-size:16px}input{max-width:100%;margin:10px 0}.preview{overflow:auto;border:1px solid #dde4f0;border-radius:8px;padding:10px}.preview svg{width:100%;min-width:300px;height:auto;max-height:72vh}.part-layout{display:grid;grid-template-columns:minmax(0,2fr) minmax(260px,1fr);gap:14px}.part-sidebar{max-height:70vh;overflow:auto}.part-row{display:flex;justify-content:space-between;gap:8px;padding:7px;border-bottom:1px solid #eee;font-size:12px}.part-row select{max-width:120px}@media(max-width:760px){.part-layout{grid-template-columns:1fr}}.preview path{cursor:pointer}</style></head><body><main>
<section><h1>Moli CAD Laboratuvarı</h1><p class="warn"><strong>Deneysel:</strong> DXF çizimini görüntüler. Otomatik serileme, dikiş doğrulaması ve kesime hazır kalıp üretimi henüz yok.</p>
<form method="post" enctype="multipart/form-data"><input type="hidden" name="csrfmiddlewaretoken" value="__CSRF__"><label for="pattern">CAD kalıp dosyası (.dxf)</label><br><input id="pattern" type="file" name="pattern" accept=".dxf" required><br><button type="submit">Kalıbı oku ve göster</button></form><hr><h2>Ölçüden kalıp çizimi (deneysel)</h2><form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="__CSRF__"><input type="hidden" name="mode" value="measure"><label>Göğüs (cm) <input type="number" name="bust" value="92" min="65" max="145" step="0.5" required></label><label>Bel (cm) <input type="number" name="waist" value="72" min="45" max="135" step="0.5" required></label><label>Beden boyu (cm) <input type="number" name="length" value="42" min="25" max="65" step="0.5" required></label><button type="submit">5 parçalı çizimi oluştur</button></form></section>
__RESULT__</main></body></html>"""
    result_html = ""
    if error:
        result_html = '<section><p class="error">' + escape(error) + '</p></section>'
    elif drawing:
        result_html = '<section><h2>DXF parça tanımlama</h2><p>' + escape(summary) + '</p><div id="cad-unit" data-unit="' + escape(unit) + '"></div>' + drawing + '<p>Etiketler yalnızca tarayıcıda tutulur. JSON dosyası indirilebilir; dikiş kenarı doğrulaması henüz yoktur.</p></section>'
    if request.method == 'POST' and request.POST.get('mode') == 'measure' and drawing:
        result_html = '<section><h2>Ölçüden oluşturulan şema</h2><p>' + escape(summary) + '</p>' + drawing + '</section>'
    return HttpResponse(html.replace("__CSRF__", csrf).replace("__RESULT__", result_html))
