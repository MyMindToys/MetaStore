from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_update'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    path('devices/', views.DeviceListView.as_view(), name='device_list'),
    path('devices/create/', views.DeviceCreateView.as_view(), name='device_create'),
    path('devices/<int:pk>/', views.DeviceDetailView.as_view(), name='device_detail'),
    path('devices/<int:pk>/edit/', views.DeviceUpdateView.as_view(), name='device_update'),
    path('devices/<int:pk>/delete/', views.DeviceDeleteView.as_view(), name='device_delete'),
    path('files/', views.FileResourceListView.as_view(), name='file_list'),
    path('files/create/', views.FileResourceCreateView.as_view(), name='file_create'),
    path('files/<int:pk>/', views.FileResourceDetailView.as_view(), name='file_detail'),
    path('files/<int:pk>/edit/', views.FileResourceUpdateView.as_view(), name='file_update'),
    path('files/<int:pk>/delete/', views.FileResourceDeleteView.as_view(), name='file_delete'),
    path('tags/', views.TagListView.as_view(), name='tag_list'),
    path('tags/create/', views.TagCreateView.as_view(), name='tag_create'),
    path('tags/<int:pk>/edit/', views.TagUpdateView.as_view(), name='tag_update'),
    path('search/', views.FileSearchView.as_view(), name='search'),
    path('scan-inbox/', views.ScanInboxView.as_view(), name='scan_inbox'),
    path('how-to-scan/', views.ScannerHelpView.as_view(), name='scanner_help'),
    path('material-kinds/', views.MaterialKindListView.as_view(), name='material_kind_list'),
    path('material-kinds/create/', views.MaterialKindCreateView.as_view(), name='material_kind_create'),
    path('material-kinds/<int:pk>/edit/', views.MaterialKindUpdateView.as_view(), name='material_kind_update'),
    path('materials/', views.MaterialListView.as_view(), name='material_list'),
    path('materials/search/', views.LiteratureSearchView.as_view(), name='literature_search'),
    path('materials/create/', views.MaterialCreateView.as_view(), name='material_create'),
    path('materials/<int:pk>/', views.MaterialDetailView.as_view(), name='material_detail'),
    path('materials/<int:pk>/edit/', views.MaterialUpdateView.as_view(), name='material_update'),
    path('materials/<int:pk>/delete/', views.MaterialDeleteView.as_view(), name='material_delete'),
    path(
        'materials/<int:material_pk>/links/add/',
        views.LinkedResourceCreateView.as_view(),
        name='linked_resource_create',
    ),
    path(
        'materials/<int:material_pk>/links/<int:pk>/edit/',
        views.LinkedResourceUpdateView.as_view(),
        name='linked_resource_update',
    ),
    path(
        'materials/<int:material_pk>/links/<int:pk>/delete/',
        views.LinkedResourceDeleteView.as_view(),
        name='linked_resource_delete',
    ),
    path(
        'materials/<int:material_pk>/locations/<int:pk>/tags/',
        views.MaterialLocationTagsUpdateView.as_view(),
        name='material_location_tags',
    ),
]
