from django.db.models import Q
from django.urls import reverse_lazy
from django.views import generic

from .forms import BibliographicRecordForm, BibliographicTagForm
from .models import BibliographicRecord, BibliographicTag


class BibliographicRecordListView(generic.ListView):
    model = BibliographicRecord
    template_name = "library/record_list.html"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("tags")
        query = self.request.GET.get("q")
        tag_id = self.request.GET.get("tag")
        filters = Q()
        if query:
            filters &= Q(title__icontains=query) | Q(authors__icontains=query) | Q(abstract__icontains=query)
        if tag_id:
            filters &= Q(tags__id=tag_id)
        if filters:
            queryset = queryset.filter(filters).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tags"] = BibliographicTag.objects.all()
        context["selected_tag"] = self.request.GET.get("tag")
        context["query"] = self.request.GET.get("q", "")
        return context


class BibliographicRecordDetailView(generic.DetailView):
    model = BibliographicRecord
    template_name = "library/record_detail.html"


class BibliographicRecordCreateView(generic.CreateView):
    model = BibliographicRecord
    form_class = BibliographicRecordForm
    template_name = "library/record_form.html"
    success_url = reverse_lazy("library:record_list")


class BibliographicRecordUpdateView(generic.UpdateView):
    model = BibliographicRecord
    form_class = BibliographicRecordForm
    template_name = "library/record_form.html"
    success_url = reverse_lazy("library:record_list")


class BibliographicRecordDeleteView(generic.DeleteView):
    model = BibliographicRecord
    template_name = "library/record_confirm_delete.html"
    success_url = reverse_lazy("library:record_list")


class BibliographicTagListView(generic.ListView):
    model = BibliographicTag
    template_name = "library/tag_list.html"
    paginate_by = 20


class BibliographicTagCreateView(generic.CreateView):
    model = BibliographicTag
    form_class = BibliographicTagForm
    template_name = "library/tag_form.html"
    success_url = reverse_lazy("library:tag_list")


class BibliographicTagUpdateView(generic.UpdateView):
    model = BibliographicTag
    form_class = BibliographicTagForm
    template_name = "library/tag_form.html"
    success_url = reverse_lazy("library:tag_list")


class BibliographicTagDeleteView(generic.DeleteView):
    model = BibliographicTag
    template_name = "library/tag_confirm_delete.html"
    success_url = reverse_lazy("library:tag_list")
