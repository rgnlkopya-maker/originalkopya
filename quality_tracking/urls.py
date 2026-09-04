from django.urls import path
from . import views

app_name = "quality_tracking"

urlpatterns = [
    path("order/<int:order_id>/", views.order_quality_issues, name="order_issues"),
    path("issue/<int:issue_id>/resolve/", views.resolve_issue, name="resolve_issue"),
    path("issue/<int:issue_id>/reopen/", views.reopen_issue, name="reopen_issue"),
    path("report/", views.issue_report, name="issue_report"),
    path("personel/<int:user_id>/", views.personnel_detail, name="personnel_detail"),
    path("personel/u/<str:username>/", views.personnel_detail_username, name="personnel_detail_username"),
]
