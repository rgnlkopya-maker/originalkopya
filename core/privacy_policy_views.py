"""Public information about the MoliApp Google Drive backup integration."""
from django.http import HttpResponse

POLICY = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MoliApp - Gizlilik Politikası</title>
<style>body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#1e293b;background:#f8fafc;margin:0;line-height:1.65}main{max-width:780px;margin:40px auto;background:white;padding:40px;border:1px solid #e2e8f0;border-radius:14px}h1{font-size:30px}h2{font-size:20px;margin-top:28px}a{color:#2563eb}@media(max-width:680px){main{margin:0;padding:22px;border:0;border-radius:0}}</style></head>
<body><main><h1>MoliApp Gizlilik Politikası</h1><p><strong>Son güncelleme:</strong> 27 Ekim 2026</p>
<p>MoliApp, Moli Tekstil'in üretim ve şirket içi kayıt işlemleri için kullandığı bir uygulamadır. Bu metin, özellikle MoliApp'in Google Drive yedekleme bağlantısında verilerin nasıl işlendiğini açıklar.</p>
<h2>1. İşlenen bilgiler</h2>
<p>MoliApp, uygulamaya kaydedilen çek/senet bilgileri, ilgili cari ve işlem kayıtları ile kullanıcıların yüklediği belge fotoğraflarını işler. Google bağlantısı sırasında Google'ın verdiği erişim yetkileri ve bağlantıyı sürdürmeye yarayan kimlik doğrulama bilgileri de işlenir.</p>
<h2>2. Google Drive erişiminin amacı</h2>
<p>Yetkili kullanıcı MoliApp'ten manuel olarak yedekleme başlattığında, uygulama çek/senet verilerini JSON ve Excel dosyaları, ilgili fotoğrafları da görsel dosyalar olarak kullanıcının belirlediği Google Drive klasörüne yükler. Bağlantının çalışması için Google Drive dosyalarına erişim yetkisi istenir. Uygulamanın amaçlanan Drive kullanımı bu yedekleme işlemidir; kullanıcının diğer Drive içeriklerini analiz etmek veya reklam amacıyla kullanmak değildir.</p>
<h2>3. Saklama ve güvenlik</h2>
<p>Yedeklenen dosyalar, yetkilendirme yapılan Google hesabının Drive alanında tutulur ve o hesaba uygulanan Google Drive erişim ve saklama ayarlarına tabidir. MoliApp bağlantının yenilenmesi için gereken Google OAuth yenileme anahtarını sunucu veritabanında şifreli olarak saklar. Yetki verilen hesap sahibi erişimi Google hesap ayarlarından geri alabilir; MoliApp içindeki yetkili kişiler de uygulama bağlantısını sonlandırabilir.</p>
<h2>4. Paylaşım ve üçüncü taraf hizmetler</h2>
<p>Drive yedeklemesi için gerekli veriler Google Drive hizmetine aktarılır. MoliApp ayrıca uygulamanın işletilmesi için barındırma ve dosya depolama hizmetlerinden yararlanır. Bu yedekleme özelliği Google kullanıcı verilerini reklam hedefleme amacıyla kullanmaz veya satmaz.</p>
<h2>5. Süre, silme ve talepler</h2>
<p>Google Drive'a gönderilmiş yedekler, Google Drive'da hesap sahibi tarafından silinene veya ilgili saklama politikası uygulanana kadar kalabilir. MoliApp bağlantısını kaldırmak, daha önce oluşturulmuş Drive yedeklerini otomatik olarak silmez. Verilerin incelenmesi, silinmesi veya uygulamayla ilgili gizlilik soruları için aşağıdaki adresten iletişime geçilebilir.</p>
<h2>6. İletişim</h2><p>Moli Tekstil<br>E-posta: <a href="mailto:tekstilmoil@gmail.com">tekstilmoil@gmail.com</a></p>
<p>Bu politika, MoliApp'in Google Drive entegrasyonunda açıklanan işlevler değişirse güncellenebilir.</p>
</main></body></html>"""


def privacy_policy(request):
    response = HttpResponse(POLICY, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response
