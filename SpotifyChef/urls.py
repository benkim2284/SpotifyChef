"""
URL configuration for SpotifyChef project.

The `urlpatterns` list routes URLs to views. For more information, please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("SpotifyWrappedApp/", include("SpotifyWrappedApp.urls")),  # SpotifyWrappedApp URLs
    path('admin/', admin.site.urls),  # Admin site URLs
    path('', include('SpotifyWrappedApp.urls')),  # Main app URLs
]
