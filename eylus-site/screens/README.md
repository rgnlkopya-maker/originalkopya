# EYLUS - Onaylı gerçek ekran görüntüleri

Bu klasör Çözümler sayfasında kullanılacak **gerçek** uygulama ekranlarına ayrılmıştır.

## Yayın kuralı
- Sadece MoliApp/Eylus uygulamasından alınmış, kullanıcı tarafından **tek tek onaylanmış** gerçek ekranlar kullanılır. Yapay görüntü veya temsili bir tasarım "gerçek ekran" diye yayımlanmaz.
- Görsel herkese açık bir GitHub dalına konulmadan **önce** müşteri, personel, telefon, adres, fatura/çek numarası, tutar, hesap, kimlik, URL tokenı ve benzeri özel/ticari alanlar geri döndürülemeyecek biçimde anonimleştirilir; gerekiyorsa örnek veriyle **ayrı demo ortamında** gerçek ekran kaydı alınır.
- Bulanıklaştırma tek başına yeterli olmayabilir: hassas kısımları düz renk ile kapatıp görseli yeniden dışa aktarın; dosya meta verisini kontrol edin. Kullanıcı izin vermeden finans/personel ekranı yayımlanmaz.
- Öncelikle sıkıştırılmış WebP kullanın, mobilde okunabilirliği kontrol edin. Geniş ekran görüntülerinin dosya boyutunu düşük tutun.

## Teknik bağlantı
1. Onaylı, anonimleştirilmiş dosyayı `eylus-site/screens/` klasörüne ekleyin (örnek: `siparis-listesi.webp`).
2. Yalnızca **o görsel onaylandıktan sonra** `eylus-site/build.py` içinde `APPROVED_SOLUTION_SCREENSHOTS` sözlüğüne kayıt girin:
   `"operasyon-01": ("siparis-listesi.webp", "Eylus Sipariş Listesi ekranı")`
3. Site üretilirken yalnızca onay sözlüğündeki dosyalar `dist/assets/solutions/` konumuna kopyalanır. Sözlükte olmayan görüntüler sitede kullanılmaz. Beklenen dosya yoksa derleme açık hatayla durur.
4. Görsel bilgisayar ve telefon görünümünde gösterilir; dokunularak yeni sekmede büyütülebilir.
5. Render canlı yayını ve mobil/masaüstü görünüm doğrulanmadan "yayınlandı" denmez.

İlk öncelik: **Operasyon 01 — Sipariş Listesi**, ardından **Yönetim — Patron Ekranı** ve **Satış — Sipariş Föyü Yapay Zekâ Okuma**.

Sadece genel pazarlama sitesi `eylus-website` dalı düzenlenir. MoliApp `main` ve demo bu işlemde değiştirilmez.
