from django.urls import path
from . import views

urlpatterns = [
    path("", views.planning_page, name="planning_page"),
    path("sevkiyat/", views.shipment_planning_page, name="shipment_planning_page"),
    path("sevkiyat/siparis/<int:order_id>/planla/", views.plan_order_shipment, name="plan_order_shipment"),
    path("sevkiyat/<int:plan_id>/kaldir/", views.remove_shipment_plan, name="remove_shipment_plan"),
    path("not/<int:entry_id>/sil/", views.delete_entry, name="planning_delete_entry"),
    path("kaydet/", views.save_entry, name="planning_save_entry"),
]
