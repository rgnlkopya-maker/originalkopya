from django.urls import path
from . import views

urlpatterns = [
    path("", views.product_card_list, name="product_card_list"),
    path("<int:card_id>/", views.product_card_detail, name="product_card_detail"),
    path("malzemeler/", views.material_list, name="material_list"),
]
