from django.urls import path
from . import views

urlpatterns = [
    path("", views.prospect_list, name="prospect_list"),
    path("yeni/", views.prospect_new, name="prospect_new"),
    path("<int:pk>/", views.prospect_detail, name="prospect_detail"),
    path("gunluk-arama/", views.search_today, name="prospect_search_today"),
]
