from django.urls import path
from . import views, guided_views

urlpatterns = [
    path("", views.prospect_list, name="prospect_list"),
    path("arama/<int:history_id>/", views.prospect_list, name="prospect_list_with_history"),
    path("sonraki-20/", guided_views.automatic_next_batch, name="prospect_automatic_batch"),
    path("arama-baslat/", guided_views.start, name="prospect_guided_start"),
    path("secili-sonuclari-aktar/", guided_views.import_results, name="prospect_guided_import"),
    path("yeni/", views.prospect_new, name="prospect_new"),
    path("csv-aktar/", views.import_prospect_csv, name="prospect_csv_import"),
    path("csv-ornek/", views.prospect_csv_template, name="prospect_csv_template"),
    path("<int:pk>/", views.prospect_detail, name="prospect_detail"),
    path("<int:pk>/iletisim-tara/", views.scan_public_contacts, name="prospect_scan_contacts"),
    path("<int:pk>/e-posta-onayla/", views.approve_outreach, name="prospect_approve_outreach"),
    path("<int:pk>/takip-onayla/", views.queue_outreach_followup, name="prospect_queue_followup"),
    path("<int:pk>/iletisimi-durdur/", views.stop_outreach, name="prospect_stop_outreach"),
    path("e-posta-cikis/<str:token>/", views.unsubscribe_public, name="prospect_unsubscribe"),
    path("gunluk-arama/", views.search_today, name="prospect_search_today"),
]
