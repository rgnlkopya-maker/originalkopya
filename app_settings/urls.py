from django.urls import path
from . import views

urlpatterns = [
    path('', views.settings_home, name='settings_home'),
    path('personel-erisim-salteri/', views.toggle_staff_access, name='toggle_staff_access'),
]
