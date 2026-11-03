# MoliApp yedekleme / kurtarma hazırlığı — 03.11.2026

Bu dal yalnızca hazırlık, test ve dokümantasyon içindir. **Canlı main dalında değişiklik yapılmadı.**

## Gerçek durum
- Render workspace: My Workspace; üretim DB: originalkopya-db, PostgreSQL 18.6, 33 MB, 117 public tablo (salt okunur kontrol, 03.11).
- Föy otomatik yedeği: 03.11 00:24 TSİ tamamlandı, 25 kayıt, 0 yeni belge/fotoğraf (DB kaydı).
- Çek/Senet: 03.11 00:11 TSİ tamamlandı, 16 kayıt, 2 yeni veri dosyası (DB kaydı).
- Render cron aktif ve her dakika kontrol ediyor; outcomes=[] bir yedek üretildiği anlamına gelmez.
- **Güvenlik:** Cron başlangıç komutu ve logları erişim sırrını düz metin ifşa ediyor. Bu anahtar belgelere veya kodlara kopyalanmamalı. Güvenli dönüşüm için web servisi ile cron tarafı birlikte değiştirilip sır yenilenmeli; mevcut Render bağlantısında cron start command düzenleme aksiyonu bulunmuyor.
- Tam şifreli PostgreSQL dökümü, ikinci kopya, izole geri yükleme testi henüz yapılmadı.

## Öncelikli sonraki adımlar
1. Render cron komutunu, anahtarı yalnız ortam değişkeninden okuyan betiğe geçir; yeni sırrı web ve cron ortamına koordineli yaz; sonra eski sırrı geçersiz kıl. Gizli değeri loga basma.
2. Üretim ve demo DB'yi karıştırmadan, uyumlu pg_dump 18.x ile salt okunur custom dump tasarımını uygula.
3. AES-256-GCM şifreleme anahtarını ayrı, güvenli bir ortamda yönet; düz metin dump artığı bırakmayan yöntem seç.
4. Bağımsız ikinci depolamaya şifreli kopya; boyut/hash kontrolü, otomatik saklama ve hata alarmı.
5. İzole DB'ye pg_restore ve tablo/satır/ilişki kontrolleri. **Canlı veritabanına restore yapılmayacak.**

## Test edilmiş çevrimdışı bileşen
03.11'de yerel ortamda şifreleme/açma prototipi sahte PGDMP içerikli veri üzerinde test edildi: round-trip, dosya değiştirilince kimlik doğrulama hatası, boş dosya reddi, mevcut hedefin üzerine yazmama. Bu, gerçek DB dump/restore testi değildir. Prototip dosyaları kullanıcıya ayrı indirilebilir çalışma ekleri olarak verildi; bu dalda otomatik deploy başlatılmadı.

## Kabul ilkesi
Kod hazır ≠ canlı yedek oluştu ≠ yedekten geri yüklenebildi. Her aşamaya gerçek test kanıtı eklenmeden tamamlandı işaretlenmeyecek.
