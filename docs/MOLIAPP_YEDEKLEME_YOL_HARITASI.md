# MoliApp — Yedekleme Merkezi Geliştirme Çalışma Dosyası

**Sürüm:** 1.1 · **Başlangıç:** 30.10.2026 · **Durum:** PLAN / AŞAMA 1 BEKLİYOR  
**Ana depo:** rgnlkopya-maker/originalkopya · **Dal:** main  
**Canlı uygulama:** https://originalkopya.onrender.com/yonetim/yedekleme-merkezi/

> **DEVAM NOKTASI (güncel):** AŞAMA 1 — Mevcut Drive yedeklerinin okunabilirliğini kontrol et; ardından **AŞAMA 2: şifreli, bağımsız tam PostgreSQL yedeği + izole ortamda geri yükleme** önceliğine geç. Modül bazlı yeni yedeklemeleri bu temelden sonra geliştir. Her oturum sonunda test kanıtını, commit'i ve sonraki adımı bu dosyaya işle.

## 0. Şu anda var olan sistem — değiştirmeden koru
- **Sipariş Föyleri:** Her föy için PDF, yazdırma HTML'si, JSON, orijinal görseller; mevcutları karşılaştırarak yükleme. Otomatik zamanlama ve parça parça ilerleme altyapısı oluşturuldu. Son gözlenen çalışma 30.10.2026 16.50'de devam ediyordu; **tamamlandığı doğrulanmadı**.
- **Çek/Senet:** Her çalışmada yeni tarihli Excel ve JSON, yalnızca eksik fotoğraflar. 30.10.2026 16.25 ve 16.46 yedekleri başarılı; 16 kayıt, 2 dosya, 0 yeni fotoğraf. 
- **Yedekleme Merkezi:** Her modülün saat/sıklık ayarı, kurallar, otomatik çalışma geçmişi.
- **Render Cron:** moli-backup-scheduler, mevcut MoliApp web servisinin korumalı uç noktasına çağrı yapıyor. Yedekleme saati Avrupa/İstanbul.
- **ÖNEMLİ:** Çek/Senet her çalışmada yeni Excel+JSON çıkarmaya devam etmeli. Kullanıcının onayı olmadan bu davranış değiştirilmez.
- **Not:** Mevcut geçmiş ekranı ağırlıkla otomatik çalışmaları gösterir. Eski manuel çalışmaları tek geçmişe birleştirme geliştirmesi henüz yapılmadı.

## TEMEL HEDEF — Sistem tamamen çökerse MoliApp'i yeniden ayağa kaldırabilmek

**Hedef senaryo:** Mevcut Render web servisi ve üretim veritabanı kullanılamaz hale gelirse, GitHub'daki uygulama kodu yeni bir servise dağıtılacak; yeni PostgreSQL veritabanına **doğrulanmış tam DB yedeği** geri yüklenecek; harici fotoğraf/video ve diğer dosyalar ayrı yedeklerden yeniden bağlanacak; uygulama kontrollerden sonra açılacak. Bu süreç önce **canlıya dokunmayan test ortamında** ispatlanmalıdır.

### Mevcut Drive JSON'ları tam kurtarma için yeterli mi?
- **Çek/Senet:** Excel ve JSON, mevcut 16 kayıt gibi verilerin kurtarılmasına yardımcı olur; kaynak fotoğraflar ayrıca tutulur. Fakat **JSON'dan MoliApp tablolarına otomatik geri yükleme aracı henüz yapılmadı**. Kayıt ve ilişki alanlarının eksiksiz olduğu ayrıca test edilmelidir.
- **Sipariş Föyleri:** JSON, PDF, HTML ve orijinal görseller değerli kurtarma kaynaklarıdır; **tek tıkla geri yükleme yoktur**, ilişkili müşteri/ürün kayıtlarının ayrıca bulunması gerekir.
- **Diğer modüller:** Siparişlerin tamamı, üretim hareketleri, faturalar, maaşlar, stoklar ve yetkiler için modül JSON'ları henüz kapsamlı bir kurtarma kanıtı değildir.
- **GitHub:** Kod ve şema değişikliklerini saklar; **işletmenin canlı verilerini ve harici medya dosyalarını kendiliğinden içermez**.
- **Gizli ayarlar:** OAuth/API anahtarları ve çevresel değişkenler JSON arşivlerine katılmamalı; yeni servis için ayrı, güvenli bir kurulum prosedürü oluşturulmalı.

### Kurtarma sırasında hedef sıra
1. GitHub'dan doğru sürüm/commit seç; yeni uygulama servisi kur; gerekli bağımlılıkları yükle.
2. Boş ve **izole** yeni PostgreSQL oluştur; tam yedeği doğrula ve bu veritabanına geri yükle.
3. Şema/migration uyumluluğunu, kullanıcı yetkilerini, sipariş–üretim ve fatura ilişkilerini test et.
4. Fotoğraf, video, folyo görselleri ve çek/senet eklerini yedek depodan uygun ortama geri getir veya erişilebilir bağlantılarını doğrula.
5. Gizli yapılandırmaları yetkili kasadan yeniden tanımla; Drive, Supabase ve diğer servis bağlantılarını sınayarak aç.
6. Sayım ve mutabakat yap: müşteri/sipariş/üretim/fatura/maaş/çek-senet/stok kayıtları, görsel varlığı, birkaç örnek rapor.
7. **Canlıya geçiş yalnızca açık kullanıcı onayıyla**; sonrasında hata, veri kaybı ve servis sürekliliği kontrolü.

**Kabul ilkesi:** “Yedeklendi” başka, “geri yüklenebildi” başkadır. Sistem kurtarma testini geçmeden “felakete hazır” olarak işaretlenmez.

## 1. Değişmez kurallar
1. Canlı kayıt silinmez, düzenlenmez; yedekleme yalnızca okuma/harici kopyalama yapar.
2. Her modülün sıklığı, dosya türleri, değişiklik kontrolü ve saklama kuralı ayrı tanımlanır.
3. İlk aşama **salt yedekleme**; canlı veriye geri yükleme ancak ayrı onay, test ortamı, ön inceleme ve geri dönüş planıyla olur.
4. Müşteri, çalışan, maaş, kimlik, ödeme ve fatura verisi sınırlı erişimle, aktarımda ve depoda şifrelenerek korunur; erişim tokenları arşivlere yazılmaz.
5. Tam veritabanı yedeği şifreli ve bağımsız ikinci kopyalı olmalı; Drive'daki Excel/JSON tek başına felaket kurtarma sayılmaz.
6. İşlem sonucu dosya sayısına göre değil, bütünlük doğrulaması ve geri okunabilirlik testiyle onaylanır.
7. Her aşama: tasarım → güvenlik kontrolü → geliştirme → test → log/Drive doğrulama → kullanıcı onayı → tamamlandı.
8. Manuel yedekler ve mevcut otomatik planlar korunur; değişecekse önce geriye uyum kontrolü yapılır.

## 2. Aşama takip çizelgesi

| Aşama | İş paketi | Durum | Kabul kanıtı |
|---|---|---|---|
| 0 | Mevcut sistem envanteri ve kurallar | KISMEN TAMAMLANDI | Kodlar incelendi, 2 modül var; folyo son işlemi netleşmeli |
| 1 | Yedekleme sağlamlık kontrolü ve geri yükleme stratejisi | SIRADAKİ | Çek/Senet ve Föy gerçek dosya doğrulama, hata senaryoları, dokümante kurtarma |
| 2 | **Öncelikli: tam PostgreSQL yedeği + izole geri yükleme testi** | BEKLİYOR | Şifreli ve ayrı depoda kopya; yeni test DB'sine başarılı geri yükleme |
| 3 | Siparişler + üretim ve QR hareketleri | BEKLİYOR | Sipariş, olay, aşama, görüntü sayısı ve eşleşen JSON/Excel |
| 4 | Fatura, proforma ve finans | BEKLİYOR | Fatura/satır/aktarım/finans ilişkileri tutarlı dışa aktarılır |
| 5 | Müşteri, ürün, fiyat ve ürün resimleri | BEKLİYOR | İlişkiler korunur, resimlerin erişilebilirliği kontrol edilir |
| 6 | Maaşlar, İK ve puantaj | BEKLİYOR | Şifreleme, rol kontrolü, gizli veri erişim testi |
| 7 | Malzeme, depo ve konsinye hareketleri | BEKLİYOR | Stok ve hareket mutabakatı, JSON/Excel |
| 8 | Tek merkezden arama, ayrıntı, sağlık ve alarm | BEKLİYOR | Tekil geçmiş, gerçek hata, başarısız görev bildirimi |
| 9 | Felaket kurtarma tatbikatı ve işletim rehberi | BEKLİYOR | Test ortamında geri dönüş, RPO/RTO ölçümü, imzalı kontrol listesi |

## 3. Aşama bazlı teknik işler ve tamamlanma ölçütleri

### AŞAMA 1 — Sağlamlık ve temeller
- [ ] Mevcut GitHub modülleri, Render görevleri, DB tabloları ve Drive klasörlerinin envanterini çıkar.
- [ ] En son Sipariş Föyleri otomatik yedeğinin tamamlanmasını ve PDF/HTML/JSON/fotoğraf sayısını doğrula.
- [ ] Çek/Senet Excel ve JSON'un içerik ve dosya bütünlüğünü Drive üzerinden teyit et.
- [ ] Yedeklerin UTC/İstanbul zaman damgasını ve işlem başına tek kayıt kuralını doğrula.
- [ ] Hata, erişim reddi, zaman aşımı, eksik/boş dosya durumları için log ve tekrar deneme tasarla.
- [ ] Sistem parolaları, OAuth tokenları, API anahtarları ve hassas verilere ilişkin kapsam dışı alanları listele.
- [ ] Mevcut otomatik ve manuel yedeklerin aynı geçmişte yinelenmeden görünmesini planla.
**Kabul:** İki mevcut modülden örnek dosyalar okunabilir, zamanlayıcı çalışır, hata ile “devam ediyor” ayrılır.

### AŞAMA 2 — Tam PostgreSQL
- [ ] Yedeklenecek üretim DB'sinin kimliğini doğrula; yanlışlıkla demo DB'yi kullanma.
- [ ] pg_dump/uyumlu alternatifin sürüm ve erişim koşullarını incele.
- [ ] Şifreli saklama, ayrı lokasyon, döndürme politikası (örnek: 7 günlük + 4 haftalık + 3 aylık) belirle.
- [ ] Yedek doğrulama: bütünlük, geri açılabilirlik, tablo ve satır sayısı karşılaştırması.
- [ ] **Canlıya geri yükleme yapmadan** izole test DB'sine geri yükleme tatbikatı.
- [ ] Boş bir yeni Render servisi/DB üzerinde GitHub kodları + kurtarılan veritabanıyla uygulama açılış testini yap.
- [ ] Harici medya ve entegrasyon yapılandırmasının ayrı yedeği/yeniden bağlama prosedürünü tasarla.
- [ ] Test sonunda geri yüklenebilir tablo ve kayıt sayıları ile olası veri kaybını raporla.
**Kabul:** Yedek otomatik oluşur, şifreli/erişim kontrollüdür ve test DB'de açılır.

### AŞAMA 3 — Sipariş ve üretim
- [ ] core.Order, OrderEvent, UretimGecmisi, görseller/video, üretim aşamaları ve QR ilişkilerini haritala.
- [ ] Sipariş bazlı Excel raporu + ilişkileri koruyan JSON üret.
- [ ] Harici görseller/videoları bağlantı listesi yerine mümkünse doğrulanmış dosya olarak sakla.
- [ ] Her gün iki plan penceresi; yoğunlukta sayfalama ve devam noktası.
**Kabul:** Örnek siparişin tüm aşama geçmişiyle tekrar okunması mümkündür.

### AŞAMA 4 — Fatura ve finans
- [ ] InvoiceDraft, InvoiceLine, InvoiceManualLine, StandaloneInvoice, ödeme ve finans snapshot modellerini haritala.
- [ ] BizimHesap/Paraşüt eşleştirmelerini ve entegrasyon durumlarını **kimlik bilgileri hariç** arşivle.
- [ ] Para birimi, KDV, satır ve toplam tutar mutabakatı kontrol et.
**Kabul:** Örnek fatura ile arşiv satırları ve toplamlar tutarlı.

### AŞAMA 5 — Müşteriler ve ürünler
- [ ] Musteri, CustomerDetail, CustomerPricingRule, UrunKod, ProductCard, renk/beden ve fiyat geçmişini eşleştir.
- [ ] Fotoğraflar ve malzeme/ürün bağlantıları için dosya varlığı kontrolü yap.
**Kabul:** En az bir örnek müşteri-ürün-fiyat zinciri eksiksiz geri okunur.

### AŞAMA 6 — Maaş ve puantaj
- [ ] SalaryProfile/Period/Transaction/PaymentPlan ve AttendanceRecord kapsamını doğrula.
- [ ] Patron/müdür ve ayrıca gerekli sınırlı yetki düzenini tanımla.
- [ ] Şifreli arşiv ve denetim izi; görüntülemede hassas alan maskelemesi.
**Kabul:** Yetkisiz kullanıcı ne dosyaya ne geçmiş detayına ulaşabilir.

### AŞAMA 7 — Depo ve stok
- [ ] Material, MaterialStockMovement, MaterialWarehouseStock, DepoStok, ConsignmentStock/Movement kapsamını belirle.
- [ ] Hareket defteriyle dönem başı/sonu stoklarını uzlaştır.
**Kabul:** Stok bakiyesi hareketlerden hesaplanan tutarla eşleşir.

### AŞAMA 8 — Takip ekranı ve alarm
- [ ] İşlem türü: manuel/otomatik, başlangıç/bitiş, durum, işlenen kayıt, yeni/değişen dosya, fotoğraf, hata kodu.
- [ ] Tek tabloda çift kayıt oluşmasını önle.
- [ ] Dosya/klasör bazlı kontrol ve “son doğrulanan yedek” bilgisi.
- [ ] Uzun süren görevi tespit, sınırlı tekrar ve başarısızlık bildirimi.
**Kabul:** Hata ve başarılı senaryolar arayüzde doğru ve anlaşılır.

### AŞAMA 9 — Kurtarma tatbikatı
- [ ] Yedek kurtarma prosedürü, rol yetkileri ve sorumlu kişileri dokümante et.
- [ ] Canlıya dokunmadan geri yükleme prova et, ilişkiler/görseller/raporları doğrula.
- [ ] Hedef kurtarma veri kaybı ve süre metriklerini (RPO/RTO) ölç, değerlendir.
**Kabul:** Kurtarma senaryosu tekrarlanabilir ve yazılıdır.

## 4. Her oturumda güncellenecek ilerleme günlüğü

| Tarih | Aşama | Yapılan işlem | Commit / dağıtım / test kanıtı | Sonraki adım |
|---|---|---|---|---|
| 30.10.2026 | 0 | Mevcut Föy ve Çek/Senet yedekleme sistemi, zamanlayıcı ve Yedekleme Merkezi geliştirildi. | Çek/Senet 16.25 ve 16.46 işlemleri DB'de başarılı. | Aşama 1: mevcut yedeklerin sağlık denetimi |
| 30.10.2026 | PLAN | Modül bazlı uzun vadeli yedekleme yol haritası hazırlandı. | Bu çalışma dosyası | Önce Aşama 1'i uygula |
| 30.10.2026 | PLAN 1.1 | Sistem çökmesi senaryosu ve JSON sınırları eklendi; tam DB yedeği + yeni serviste kurtarma testine öncelik verildi. | Bu dosyanın v1.1 güncellemesi | Aşama 1'i tamamla, sonra Aşama 2'ye geç |

## 5. Bir sonraki görüşmede kullanılacak devam komutu
**“MoliApp yedekleme çalışma dosyasını GitHub'daki `docs/MOLIAPP_YEDEKLEME_YOL_HARITASI.md` konumundan oku. Güncel devam noktasına bak, yalnızca sıradaki aşamayı uygula. Testleri tamamlayınca durum, commit ve sonraki adımı aynı dosyaya kaydet.”**

## 6. Aşama kapanış şablonu
- Aşama:
- Yapılan iş:
- Değişen dosyalar/commit:
- Render dağıtım durumu:
- Test ve gerçek dosya doğrulaması:
- Kalan riskler:
- Kullanıcı onayı:
- Sıradaki aşama:

**Güncelleme kuralı:** “Tamamlandı” yalnızca kod kaydı değil, dağıtım + gerçek yedek + okunabilir dosya/geri yükleme testleri doğrulanınca yazılır.
