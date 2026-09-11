from django.urls import path
from . import views, status_views, finance_views, price_list_views, showroom_views

urlpatterns = [
    path("", views.product_card_list, name="product_card_list"),
    path("kur-guncelle/", views.refresh_exchange_rate, name="refresh_exchange_rate"),
    path("fiyat-listesi/", price_list_views.price_list, name="price_list"),
    path("showroom-foyu/", showroom_views.showroom_page, name="showroom_page"),
    path("showroom-foyu/kaydet/", showroom_views.showroom_save, name="showroom_save"),
    path("showroom-foyu/urun-ekle/", showroom_views.showroom_add_item, name="showroom_add_item"),
    path("showroom-foyu/urun-guncelle/", showroom_views.showroom_update_item, name="showroom_update_item"),
    path("showroom-foyu/urun-sil/", showroom_views.showroom_delete_item, name="showroom_delete_item"),
    path("fiyat-listesi/kaydet/", price_list_views.save_price_list_settings, name="save_price_list_settings"),
    path("fiyat-listesi/excel/", price_list_views.export_price_list_excel, name="export_price_list_excel"),
    path("fiyat-listesi/durum/", price_list_views.toggle_price_list_status, name="toggle_price_list_status"),
    path("durum-degistir/", status_views.toggle_product_card_status, name="toggle_product_card_status"),
    path("finans/<int:order_id>/", finance_views.order_finance_movements, name="order_finance_movements"),
    path("finans/<int:order_id>/hareket-ekle/", finance_views.add_order_finance_movement, name="add_order_finance_movement"),
    path("malzemeler/", views.material_list, name="material_list"),
    path("depo-stoklari/", views.warehouse_inventory, name="warehouse_inventory"),
    path("<int:card_id>/", views.product_card_detail, name="product_card_detail"),
]
