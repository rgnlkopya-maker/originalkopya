from django.urls import path
from . import views, status_views

urlpatterns = [
    path("", views.product_card_list, name="product_card_list"),
    path("kur-guncelle/", views.refresh_exchange_rate, name="refresh_exchange_rate"),
    path("durum-degistir/", status_views.toggle_product_card_status, name="toggle_product_card_status"),
    path("<int:card_id>/", views.product_card_detail, name="product_card_detail"),
    path("malzemeler/", views.material_list, name="material_list"),
]
