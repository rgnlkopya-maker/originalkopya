from django.urls import path
from . import views

urlpatterns = [
    path("", views.prospect_list, name="prospect_list"),
    path("yeni/", views.prospect_new, name="prospect_new"),
    path("<int:pk>/", views.prospect_detail, name="prospect_detail"),
    path("<int:pk>/e-posta-onayla/", views.approve_outreach, name="prospect_approve_outreach"),
    path("<int:pk>/takip-onayla/", views.queue_outreach_followup, name="prospect_queue_followup"),
    path("<int:pk>/iletisimi-durdur/", views.stop_outreach, name="prospect_stop_outreach"),
    path("e-posta-cikis/<str:token>/", views.unsubscribe_public, name="prospect_unsubscribe"),
    path("gunluk-arama/", views.search_today, name="prospect_search_today"),
]
