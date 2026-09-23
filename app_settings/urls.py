from django.urls import path
from . import views

urlpatterns = [
    path('', views.settings_home, name='settings_home'),
    path('personel-erisim-salteri/', views.toggle_staff_access, name='toggle_staff_access'),
    path('favoriler/', views.favorites_list, name='favorites_list'),
    path('favoriler/degistir/', views.favorite_toggle, name='favorite_toggle'),
]
