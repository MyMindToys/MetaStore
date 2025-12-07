from django import forms

from .models import BibliographicRecord, BibliographicTag


class BibliographicRecordForm(forms.ModelForm):
    class Meta:
        model = BibliographicRecord
        fields = [
            "title",
            "authors",
            "publication_year",
            "source",
            "abstract",
            "content",
            "tags",
        ]
        widgets = {
            "abstract": forms.Textarea(attrs={"rows": 3}),
            "content": forms.Textarea(attrs={"rows": 6}),
            "tags": forms.SelectMultiple(attrs={"class": "form-select"}),
        }


class BibliographicTagForm(forms.ModelForm):
    class Meta:
        model = BibliographicTag
        fields = ["name"]
