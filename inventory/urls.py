from django.urls import path
from . import views

urlpatterns = [
    path("hazirlik/siparis/<int:order_id>/", views.use_preparation, name="inventory_use_preparation"),
    path("<str:code>/hazirlik-giris/", views.add_preparation, name="inventory_add_preparation"),
    path("<str:code>/", views.warehouse_detail, name="inventory_warehouse_detail"),
    path("<str:code>/malzeme/<int:material_id>/", views.material_card, name="inventory_material_card"),
    path("<str:code>/urun/<int:product_id>/", views.product_card, name="inventory_product_card"),
    path("<str:code>/malzeme-hareket/", views.add_material_movement, name="inventory_add_material_movement"),
    path("<str:code>/urun-hareket/", views.add_product_movement, name="inventory_add_product_movement"),
]
