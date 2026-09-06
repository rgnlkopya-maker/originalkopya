from django.urls import path
from . import views

urlpatterns = [
    path("", views.planning_page, name="planning_page"),
    path("sevkiyat/", views.shipment_planning_page, name="shipment_planning_page"),
    path("kaydet/", views.save_entry, name="planning_save_entry"),
]
