# EYLUS WEB — Onaylı Tipografi ve Sayfa Anlatım Standardı

**Onay tarihi:** 10 Kasım 2026. Kullanıcı yeni açıklama tipografisini "güzeeel" diyerek onayladı ve tüm özellikler/sayfalarda kullanılmasını istedi.

**Kalıcı proje kaydı:** https://chatgpt.com/space/page_bedf87e015588191909bfa55f05c493c
**Canlı referans:** https://eylus.com.tr/tekstil/ → Operasyon → 01, "Siparişlerin son durumunu tek ekrandan görün".
**Uygulama commit'i:** `fadaa7a3444ec1028f4247f9b7f9284f2f4f0337` (`eylus-website` dalı). `eylus-site/build.py` içinde `.sol-answer`, `.sol-lead`, `.sol-support` sınıfları.

## Bütün sayfalar için editoryal düzen

1. **Çözüm / özellik başlığı:** Kısa, iş sonucunu anlatan, güçlü ama zarif. Gereksiz büyük veya sert kalınlık olmasın.
2. **Lead:** Bir kısa fayda cümlesi; işletme sahibinin gündelik sıkıntısını ortadan kaldırdığını somut söylesin. Az vurgulu, 500 weight.
3. **Support:** Bir-üç satırlık açıklayıcı destek; özellikleri ve kapsamı belirtir. Koyu gri, ancak başlıkla yarışmaz; 400 weight.
4. **Ekran:** Yalnızca kullanıcı tarafından onaylanan gerçek ve anonimleştirilmiş uygulama ekranı; hiçbir gerçek müşteri/personel/veri sızmamalı. Ekran yoksa büyük dekoratif boşluk veya "ilgili ekran" kartı üretme.
5. **Görüntüleme:** Ekrana sığan görüntüleyici, X / dışa dokunma / Esc ile kapatma, yakınlaştır ve sığdır kontrolü.
6. **Mobil:** İki sütun yerine soru altında açılan akordeon. Aynı anda tek çözüm, rahat dokunma hedefleri. Gereksiz yatay taşma yok.
7. **Tutarlılık:** Operasyon, Satış, Muhasebe, Yönetim, Ana Sayfa, Ürün, Neden Eylus, Demo, İletişim ve gelecekteki sayfalar bu hiyerarşi ve marka dilini temel alır. Hero boyutu içerik panelinden farklı olabilir; kontrast, ağırlık, ritim aynı kalır.

## Teknik referans

| Öğe | Masaüstü | Mobil |
| --- | --- | --- |
| Başlık | clamp(24px, 2.25vw, 31px); weight 700; line 1.23; letter -0.035em | 23px; line 1.24 |
| Genel gövde | 15px; #5b5668; weight 400; line 1.78 | 14.5px; weight 400; line 1.76 |
| Lead | 16px; #40394d; weight 500; line 1.6 | 15.5px; line 1.63 |
| Support | 14.5px; #676172; weight 400; line 1.78; max-width 60ch | 14px; line 1.76 |
| Alt boşluk | title 17px; lead 11px; support 24px | title 15px; lead 10px; support 22px |

**Kaçınılacak örnekler:** Bütün açıklamayı 500/550 weight ile yazmak, tek uzun paragraf, çok soluk gri yazı, her yerde gereksiz etiket/düğme, gerçek ekranı değiştirerek onaysız görsel oluşturmak.

## Onaylı örnek

**Başlık:** Siparişlerin son durumunu tek ekrandan görün

**Lead:** Atölyeyi aramadan, siparişinizin hangi aşamada olduğunu tek bakışta görün.

**Support:** Kesimden sevkiyata güncel durumları; müşteri, model, beden ve teslim tarihiyle birlikte takip edin. Arama ve filtrelerle istediğiniz siparişe kolayca ulaşın.

**Mevcut görsel:** `eylus-site/screens/siparis-listesi-onayli.webp`, kırmızı elipsli, anonimleştirilmiş, kullanıcı tarafından onaylandı. Değiştirmeden koru.

## Çalışma prensibi ve devam

- Müşteriye hitap eden soru → çözüm başlığı → bir kısa lead → support → gerçek uygulama görseli. Yeni içeriği MoliApp koduyla doğrula; doğrulanmamış ticari veya teknik vaat verme.
- Sayfaların tasarımını değiştirirken kullanıcı onaylı parçaları koru. İzin olmadan onaylı görseli yeniden üretme.
- **Statüleri ayır:** yalnızca taslak, GitHub'a işlendi, Render'da canlı, cihazda görsel doğrulandı.
- **Repo sınırı:** yalnızca `eylus-website` dalı; MoliApp üretim ana dalını veya demo verisini etkileme.
- Kaynak gerçekleri ve kullanıcı kararları için proje çalışma kaydını güncel tut.
