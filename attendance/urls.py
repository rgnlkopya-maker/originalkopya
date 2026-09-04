from django.urls import path
from . import views

urlpatterns = [
    path("", views.scan, name="attendance_scan"),
    path("punch/", views.punch, name="attendance_punch"),
    path("panel/", views.dashboard, name="attendance_dashboard"),
    path("panel/konum-kaydet/", views.save_workplace, name="attendance_save_workplace"),
    path("rapor/<int:user_id>/", views.month_report, name="attendance_month_report_current"),
    path("rapor/<int:user_id>/<int:year>/<int:month>/", views.month_report, name="attendance_month_report"),
]
