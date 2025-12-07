from django.db import models
from django.utils import timezone


class BibliographicTag(models.Model):
    name = models.CharField(max_length=150, unique=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class BibliographicRecord(models.Model):
    title = models.CharField(max_length=500)
    authors = models.CharField(max_length=500, blank=True)
    publication_year = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=255, blank=True)
    abstract = models.TextField(blank=True)
    content = models.TextField(blank=True)
    tags = models.ManyToManyField(BibliographicTag, related_name="records", blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        indexes = [
            models.Index(fields=["title"], name="library_record_title_idx"),
            models.Index(fields=["authors"], name="library_record_authors_idx"),
        ]

    def __str__(self) -> str:
        return self.title
