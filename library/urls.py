from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("records/", views.BibliographicRecordListView.as_view(), name="record_list"),
    path("records/add/", views.BibliographicRecordCreateView.as_view(), name="record_add"),
    path("records/<int:pk>/", views.BibliographicRecordDetailView.as_view(), name="record_detail"),
    path("records/<int:pk>/edit/", views.BibliographicRecordUpdateView.as_view(), name="record_edit"),
    path("records/<int:pk>/delete/", views.BibliographicRecordDeleteView.as_view(), name="record_delete"),
    path("tags/", views.BibliographicTagListView.as_view(), name="tag_list"),
    path("tags/add/", views.BibliographicTagCreateView.as_view(), name="tag_add"),
    path("tags/<int:pk>/edit/", views.BibliographicTagUpdateView.as_view(), name="tag_edit"),
    path("tags/<int:pk>/delete/", views.BibliographicTagDeleteView.as_view(), name="tag_delete"),
]
