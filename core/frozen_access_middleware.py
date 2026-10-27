from django.http import HttpResponse


class FrozenUserAccessMiddleware:
    """Deny every authenticated request for a frozen account, including API writes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            from core.models import UserProfile
            if UserProfile.objects.filter(user_id=request.user.pk, system_frozen=True).exists():
                html = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sistem Erişimi Kapalı</title><style>
*{box-sizing:border-box}html,body{margin:0;height:100%;font-family:Arial,sans-serif;background:#eef3fb}
.screen{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(16,37,71,.78);z-index:999999}
.modal{width:min(100%,490px);background:#fff;border-radius:20px;text-align:center;padding:42px 30px;box-shadow:0 25px 80px #06152955}
.icon{font-size:39px;margin-bottom:15px;color:#cc5c46}.heading{font-size:23px;font-weight:800;color:#18345f;margin-bottom:13px}
.message{font-size:15px;line-height:1.7;color:#51647e}.brand{font-size:12px;letter-spacing:2px;font-weight:800;color:#8d9bb0;margin-top:24px}
</style></head><body><div class="screen" role="alertdialog" aria-modal="true" aria-labelledby="title"><div class="modal"><div class="icon">&#128274;</div><div class="heading" id="title">Sistem Erişiminiz Kapalıdır</div><div class="message">Sisteme giriş izniniz yoktur.<br>Hesabınızın erişimi yönetim tarafından geçici olarak durdurulmuştur.<br>Erişim için patron veya müdür ile iletişime geçiniz.</div><div class="brand">MOLİAPP</div></div></div></body></html>"""
                response = HttpResponse(html, status=403, content_type="text/html; charset=utf-8")
                response["Cache-Control"] = "no-store, private"
                return response
        return self.get_response(request)
