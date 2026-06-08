from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('catalog.api_urls')),
    path('', include('catalog.urls')),
]
