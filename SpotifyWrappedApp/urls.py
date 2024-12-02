from django.urls import path
from . import views
app_name = "SpotifyWrappedApp"



urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("home/", views.home_view, name="home"),

    path("toptracks/", views.toptracks_view, name="toptracks"),
    path("wrapped/<str:wrapped_id>/", views.wrapped_view, name="wrapped"),
    path("oauth_screen/", views.oauth_view, name="oauth_screen"),
    path('logout/', views.logout_view, name='logout'),
    path('api/create_solowrap/', views.create_solowrap, name='create_solowrap'),
    path('friend_select/', views.friend_select_view, name='friend_select_view'),
    path('api/create_duowrap/', views.create_duowrap, name='create_duowrap'),
    path('duo_wrapped/<str:wrapped_id>/', views.duo_wrapped_view, name='duo_wrapped'),

]