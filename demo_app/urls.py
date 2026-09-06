from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import logout
from django.shortcuts import redirect
from core import views
from core.order_transfer_views import transfer_production_history, search_transfer_targets, order_by_number
from core.views import health_check
from core.order_list_enhanced import order_list as enhanced_order_list
from core.assistant_views import assistant_page, assistant_api, assistant_clear
from core.team_views import employee_detail, user_management_view
from core.fason_views import fasoncu_raporu, fasoncu_detay
from core.nakis_views import nakisci_raporu, nakisci_detay
from core.depo_views import depo_ozet as managed_depo_ozet
from core.customer_report_views import customer_comparison_report, customer_detail_report

def logout_view(request):
    logout(request)
    return redirect('/login/')

urlpatterns = [
    path("notifications/", views.notification_list, name="notification_list"), path("admin/", admin.site.urls), path("login/", views.custom_login, name="login"), path("custom-login/", views.custom_login, name="custom_login"), path("logout/", logout_view, name="logout"),
    path("attendance/", include("attendance.urls")), path("planlama/", include("planning.urls")), path("urun-kartlari/", include("product_cards.urls")), path("stok/", include("inventory.urls")), path("kalite/", include("quality_tracking.urls")), path("ayarlar/", include("app_settings.urls")),
    path("", enhanced_order_list, name="order_list"), path("order/new/", views.order_create, name="order_create"), path("order/<int:pk>/", views.order_detail, name="order_detail"), path("order/<int:pk>/edit/", views.order_edit, name="order_edit"), path("order/by-number/<str:order_number>/", order_by_number, name="order_by_number"),
    path("order/<int:source_order_id>/production-transfer/", transfer_production_history, name="transfer_production_history"), path("order/<int:source_order_id>/production-transfer/search/", search_transfer_targets, name="search_transfer_targets"),
    path("orders/<int:pk>/update/", views.update_stage, name="update_stage"), path("order/<int:pk>/delete/", views.order_delete, name="order_delete"), path("orders/<int:pk>/upload-image/", views.order_upload_image, name="order_upload_image"), path("orders/<int:pk>/add-image/", views.order_add_image, name="order_add_image"), path("images/<int:image_id>/delete/", views.delete_order_image, name="delete_order_image"), path("images/<int:image_id>/", views.view_image, name="view_image"), path("orders/multi-create/", views.order_multi_create, name="order_multi_create"),
    path("musteri/new/", views.musteri_create, name="musteri_create"), path("ajax/musteri/ekle/", views.ajax_musteri_ekle, name="ajax_musteri_ekle"), path("ajax/musteri/pasif-yap/", views.musteri_pasif_yap_ajax, name="ajax_musteri_pasif_yap_ajax"), path("users/", user_management_view, name="user_management"), path("users/<int:user_id>/", employee_detail, name="employee_detail"),
    path("reports/", views.reports_view, name="reports"), path("staff-reports/", views.staff_reports_view, name="staff_reports"), path("reports/giden-urunler/", views.giden_urunler_raporu, name="giden_urunler_raporu"), path("reports/home/", views.reports_home, name="reports_home"), path("reports/fasoncu/", fasoncu_raporu, name="fasoncu_raporu"), path("reports/fasoncu/<int:fasoncu_id>/", fasoncu_detay, name="fasoncu_detay"), path("reports/nakisci/", nakisci_raporu, name="nakisci_raporu"), path("reports/nakisci/<int:nakisci_id>/", nakisci_detay, name="nakisci_detay"), path("reports/musteri-karsilastirma/", customer_comparison_report, name="customer_comparison_report"), path("reports/musteri-karsilastirma/<int:customer_id>/", customer_detail_report, name="customer_detail_report"),
    path("product-costs/", views.product_cost_list, name="product_cost_list"), path("events/<int:event_id>/delete/", views.delete_order_event, name="delete_order_event"), path("asistan/", assistant_page, name="ai_assistant"), path("api/assistant/", assistant_api, name="ai_assistant_api"), path("api/assistant/clear/", assistant_clear, name="ai_assistant_clear"), path("bildirim/<int:pk>/", views.notification_read, name="notification_read"), path("bildirim-okundu/<int:pk>/", views.mark_notification_read, name="mark_notification_read"),
    path("fasoncu/yeni/", views.fasoncu_yeni, name="fasoncu_yeni"), path("nakisci/yeni/", views.nakisci_ekle, name="nakisci_yeni"), path("order/<int:order_id>/stok-ekle/", views.stok_ekle, name="stok_ekle"), path("depolar/", managed_depo_ozet, name="depo_ozet"), path("depolar/detay/<str:depo_adi>/", views.depo_detay, name="depo_detay"), path("depolar/arama/", views.depo_arama, name="depo_arama"), path("depolar/hazirdan-ver/<int:stok_id>/", views.hazirdan_ver, name="hazirdan_ver"), path("order/<int:pk>/cikti-alindi/", views.cikti_alindi, name="cikti_alindi"),
    path("ajax/beden/ekle/", views.beden_ekle_ajax, name="beden_ekle_ajax"), path("ajax/beden/pasif-yap/", views.beden_pasif_yap_ajax, name="beden_pasif_yap_ajax"), path("ajax/urun-kod/ekle/", views.urun_kod_ekle_ajax, name="urun_kod_ekle_ajax"), path("ajax/urun-kod/tip-guncelle/", views.urun_kod_tipi_guncelle_ajax, name="urun_kod_tipi_guncelle_ajax"), path("ajax/urun-kod/pasif-yap/", views.urun_kod_pasif_yap_ajax, name="urun_kod_pasif_yap_ajax"), path("ajax/renk/ekle/", views.renk_ekle_ajax, name="renk_ekle_ajax"), path("ajax/renk/pasif-yap/", views.renk_pasif_yap_ajax, name="renk_pasif_yap_ajax"),
    path("orders/print/", views.order_print, name="order_print"), path("orders/label/print/", views.order_label_print, name="order_label_print"), path("orders/export/excel/", views.order_excel_export, name="order_excel_export"), path("order/<int:pk>/toggle-active/", views.order_toggle_active, name="order_toggle_active"), path("reports/dashboard/", views.dashboard_view, name="dashboard"), path("reports/shipped-live/", views.live_shipped_orders, name="live_shipped_orders"), path("reports/sevkiyat-finans/", views.sevkiyat_finans_tablosu, name="sevkiyat_finans_tablosu"), path("reports/personel/", views.personel_raporu, name="personel_raporu"), path("health/", health_check),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
