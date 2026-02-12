"""
URL configuration for Kronon project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, path

from config.api import api

urlpatterns: list[URLPattern | URLResolver] = [
    # Админка
    path("admin/", admin.site.urls),
    # API
    path("api/", api.urls),
]


# Раздача медиа-файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
