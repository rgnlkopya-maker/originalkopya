from django.urls import path
from . import views, serial_cutting

urlpatterns = [
    path('seri-kesim/', serial_cutting.serial_cutting_page, name='serial_cutting_page'),
    path('seri-kesim/son-durumlar/', serial_cutting.serial_cutting_statuses, name='serial_cutting_statuses'),
    path('seri-kesim/ekle/', serial_cutting.serial_cutting_add, name='serial_cutting_add'),
    path('seri-kesim/<int:plan_id>/sil/', serial_cutting.serial_cutting_remove, name='serial_cutting_remove'),
    path("", views.planning_page, name="planning_page"),
    path("sevkiyat/", views.shipment_planning_page, name="shipment_planning_page"),
    path("sevkiyat/siparis/<int:order_id>/planla/", views.plan_order_shipment, name="plan_order_shipment"),
    path("sevkiyat/<int:plan_id>/fatura/", views.toggle_shipment_invoice, name="toggle_shipment_invoice"),
    path("sevkiyat/<int:plan_id>/kaldir/", views.remove_shipment_plan, name="remove_shipment_plan"),
    path("not/<int:entry_id>/sil/", views.delete_entry, name="planning_delete_entry"),
    path("kaydet/", views.save_entry, name="planning_save_entry"),
]
