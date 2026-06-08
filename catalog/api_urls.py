from django.urls import path

from catalog import api_views

urlpatterns = [
    path('devices/register/', api_views.register_device),
    path('scans/upload/', api_views.upload_scan),
    path('heartbeat/', api_views.heartbeat),
    path('status/', api_views.server_status),
    path('materials/', api_views.materials_list),
    path('locations/', api_views.locations_list),
    path('storage-locations/', api_views.storage_locations_list),
]
