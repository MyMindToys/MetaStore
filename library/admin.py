from django.contrib import admin

from .models import BibliographicRecord, BibliographicTag


@admin.register(BibliographicTag)
class BibliographicTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name",)
    ordering = ("name",)


@admin.register(BibliographicRecord)
class BibliographicRecordAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "authors",
        "publication_year",
        "source",
        "created_at",
    )
    search_fields = ("title", "authors", "abstract", "source")
    list_filter = ("publication_year", "tags")
    filter_horizontal = ("tags",)
    ordering = ("title",)
