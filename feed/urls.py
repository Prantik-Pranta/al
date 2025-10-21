from django.urls import path
from . import views
from User.views import home  # Home feed rendered from User app

urlpatterns = [
    # Home
    path('home/', home, name='home'),

    # Search
    path('search_results', views.search_results, name='search_results'),

    # Connections
    path("my_connections/", views.my_connections, name="my_connections"),
    path('send_request/<int:user_id>/', views.send_connection_request, name='send_request'),
    path('accept_request/<int:user_id>/', views.accept_connection_request, name='accept_connection_request'),
    path('delete_request/<int:user_id>/', views.delete_connection_request, name='delete_connection_request'),


    # Posts
    path('create_post/', views.create_post, name='create_post'),
    path('toggle_like/', views.toggle_like_post, name='toggle_like'),
    path('add_comment/', views.add_comment, name='add_comment'),
    path('share_post/', views.share_post, name='share_post'),
    path('delete_comment/<int:comment_id>/', views.delete_comment, name='delete_comment'),
    path('delete_post/<int:id>/', views.delete_post, name='delete_post'),

    # Optional edit/delete pages
    path("edit_post/<int:id>/", views.edit_post, name="edit_post"),
    path("delete_post/<int:id>/", views.delete_post, name="delete_post"),

    path('send_request/<int:user_id>/', views.send_connection_request, name='send_request'),
    path('accept_request/<int:user_id>/', views.accept_connection_request, name='accept_connection_request'),
    path('delete_request/<int:user_id>/', views.delete_connection_request, name='delete_connection_request'),

]
