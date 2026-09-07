from django.urls import path
from . import views

urlpatterns = [
    path("", views.scan, name="attendance_scan"),
    path("punch/", views.punch, name="attendance_punch"),
    path("qr.png", views.attendance_qr_image, name="attendance_qr_image"),
    path("qr-yazdir/", views.attendance_qr_print, name="attendance_qr_print"),
    path("cihazlar/", views.device_management, name="attendance_device_management"),
    path("cihazlar/<int:user_id>/onayla/", views.approve_device, name="attendance_approve_device"),
    path("cihazlar/<int:user_id>/sifirla/", views.reset_device, name="attendance_reset_device"),
    path("panel/", views.dashboard, name="attendance_dashboard"),
    path("panel/kayit-duzenle/", views.edit_record, name="attendance_edit_record"),
    path("panel/konum-kaydet/", views.save_workplace, name="attendance_save_workplace"),
    path("rapor/<int:user_id>/", views.month_report, name="attendance_month_report_current"),
    path("rapor/<int:user_id>/<int:year>/<int:month>/", views.month_report, name="attendance_month_report"),
]
