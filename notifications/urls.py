from django.urls import path
from . import views

urlpatterns = [
    path('', views.notifications_list, name='notifications'),
    path('read/', views.mark_all_read, name='mark_all_read'),
]
