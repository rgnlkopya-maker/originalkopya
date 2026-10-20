"""Isolated CAD experiment: illustrative geometry only, no production patterns."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.html import escape

@login_required
def cad_lab(request):
    user = request.user
    role = str(getattr(user, "role", "") or getattr(user, "rol", "")).lower()
    if not (user.is_superuser or user.is_staff or role in ("patron", "mudur", "müdür")):
        return HttpResponse("Bu test ekranina erisim yetkiniz yok.", status=403)
    def measure(key, default):
        try:
            value = float(request.GET.get(key, default))
            return value if 50 <= value <= 160 else default
        except (TypeError, ValueError):
            return default
    bust, waist = measure("gogus", 100), measure("bel", 82)
    # Half-body allocation: 50% front, 50% back; within front 40% center / 60% cup.
    front_bust = (bust - 90) * 5
    front_waist = (waist - 70) * 5
    cb, cw = front_bust * .4, front_waist * .4
    pb, pw = front_bust * .6, front_waist * .6
    html = """<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Moli CAD Laboratuvar</title><style>body{font:16px system-ui;background:#f4f6fa;color:#152237;margin:0;padding:16px}
    main{max-width:1050px;margin:auto}header,.panel{background:white;padding:18px;border-radius:14px;margin-bottom:14px}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
    input{width:100px;padding:10px;border:1px solid #bbb;border-radius:8px;font-size:17px}
    button{padding:11px 18px;border:0;border-radius:8px;background:#1646a0;color:white}
    svg{width:100%;height:auto;background:#fbfcff;border:1px solid #e2e6ed;border-radius:8px}
    .warn{color:#994b00;background:#fff5dd;padding:12px;border-radius:8px}</style>
    <main><header><h2>Moli CAD Laboratuvarı</h2><p class="warn">DENEYSEL: Çizimler temsili. Üretim, kesim ve gerçek DXF kalıbı olarak kullanılamaz.</p>
    <form method="get"><label>Göğüs (cm) <input name="gogus" type="number" min="50" max="160" step=".5" value="__BUST__"></label>
    <label>Bel (cm) <input name="bel" type="number" min="50" max="160" step=".5" value="__WAIST__"></label>
    <button type="submit">Hesapla</button></form></header>
    <div class="grid"><section class="panel"><h3>38 beden — 90 / 70</h3>
    <svg viewBox="0 0 300 390" aria-label="Temsili baz kalip"><path d="M48 65 Q32 95 40 160 L50 320 L136 320 Q155 265 142 205 Q125 150 138 80 Q95 42 48 65Z" fill="#dbeafe" stroke="#2463a6" stroke-width="2"/>
    <path d="M160 80 Q203 42 247 65 Q265 100 252 165 L248 320 L162 320 Q146 267 155 208 Q173 155 160 80Z" fill="#f0dcfa" stroke="#7c3aa6" stroke-width="2"/>
    <path d="M138 80 Q125 150 142 205 Q155 265 136 320" fill="none" stroke="#e34d4d" stroke-width="4"/>
    <path d="M160 80 Q173 155 155 208 Q146 267 162 320" fill="none" stroke="#e34d4d" stroke-width="4"/></svg>
    <p>Ön orta (mavi) · Ön kup (mor)</p></section>
    <section class="panel"><h3>Özel ölçü — __BUST__ / __WAIST__</h3>
    <svg viewBox="0 0 300 390" aria-label="Temsili hedef kalip"><g transform="translate(-8,0)">
    <path d="M48 65 Q32 95 40 160 L__CENTER_BOTTOM__ 320 L__CENTER_SEAM_BOTTOM__ 320 Q__CENTER_CURVE__ 265 142 205 Q125 150 138 80 Q95 42 48 65Z" fill="#dbeafe" stroke="#2463a6" stroke-width="2"/>
    <path d="M160 80 Q203 42 __CUP_TOP__ 65 Q__CUP_OUT__ 100 __CUP_OUT__ 165 L__CUP_BOTTOM__ 320 L162 320 Q146 267 155 208 Q173 155 160 80Z" fill="#f0dcfa" stroke="#7c3aa6" stroke-width="2"/>
    <path d="M138 80 Q125 150 142 205 Q__CENTER_CURVE__ 265 __CENTER_SEAM_BOTTOM__ 320" fill="none" stroke="#e34d4d" stroke-width="4"/>
    <path d="M160 80 Q173 155 155 208 Q146 267 162 320" fill="none" stroke="#e34d4d" stroke-width="4"/></g></svg>
    <p>Ön orta: göğüs +__CB__ mm / bel +__CW__ mm<br>Ön kup: göğüs +__PB__ mm / bel +__PW__ mm</p></section></div>
    <section class="panel"><h3>Teknik durum</h3><p>Ön/arka payı %50/%50; ön orta/ön kup payı %40/%60 varsayılmıştır.</p>
    <p class="warn">Dikiş hatları, çıtlar, pensler ve gerçek kalıp ölçüleri tanımlı değil. Dikiş uyumu onaylanmadı. Görseldeki dönüşüm yalnızca şematik genişleme gösterimidir.</p></section></main></html>"""
    replacements = {
      "__BUST__": bust, "__WAIST__": waist, "__CB__": cb, "__CW__": cw, "__PB__": pb, "__PW__": pw,
      "__CENTER_BOTTOM__": 50-cw*.25, "__CENTER_SEAM_BOTTOM__": 136+cw*.25, "__CENTER_CURVE__": 155+cb*.25,
      "__CUP_TOP__": 247+pb*.20, "__CUP_OUT__": 265+pb*.20, "__CUP_BOTTOM__": 248+pw*.20
    }
    for key, value in replacements.items():
        html = html.replace(key, escape(f"{value:.1f}" if isinstance(value, float) else str(value)))
    return HttpResponse(html)
