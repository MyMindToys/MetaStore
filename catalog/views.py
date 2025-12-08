from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import DeviceForm, FileResourceForm, FileSearchForm, ProjectForm, TagForm
from .models import Device, FileResource, Project, Tag


class HomeView(TemplateView):
    template_name = 'catalog/home.html'

    def get(self, request, *args, **kwargs):
        return redirect('catalog:search')


class ProjectListView(ListView):
    model = Project
    template_name = 'catalog/project_list.html'
    context_object_name = 'projects'


class ProjectDetailView(DetailView):
    model = Project
    template_name = 'catalog/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['files'] = self.object.files.select_related('device').prefetch_related('tags')
        return context


class ProjectCreateView(CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'catalog/project_form.html'
    success_url = reverse_lazy('catalog:project_list')


class ProjectUpdateView(UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'catalog/project_form.html'
    success_url = reverse_lazy('catalog:project_list')


class ProjectDeleteView(DeleteView):
    model = Project
    template_name = 'catalog/project_confirm_delete.html'
    success_url = reverse_lazy('catalog:project_list')


class DeviceListView(ListView):
    model = Device
    template_name = 'catalog/device_list.html'
    context_object_name = 'devices'


class DeviceDetailView(DetailView):
    model = Device
    template_name = 'catalog/device_detail.html'
    context_object_name = 'device'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['files'] = self.object.files.select_related('project').prefetch_related('tags')
        return context


class DeviceCreateView(CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'catalog/device_form.html'
    success_url = reverse_lazy('catalog:device_list')


class DeviceUpdateView(UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'catalog/device_form.html'
    success_url = reverse_lazy('catalog:device_list')


class DeviceDeleteView(DeleteView):
    model = Device
    template_name = 'catalog/device_confirm_delete.html'
    success_url = reverse_lazy('catalog:device_list')


class FileResourceListView(ListView):
    model = FileResource
    template_name = 'catalog/file_list.html'
    context_object_name = 'files'
    paginate_by = 20

    def get_queryset(self):
        return FileResource.objects.select_related('project', 'device').prefetch_related('tags')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop('page', None)
        context['querystring'] = query.urlencode()
        return context


class FileResourceDetailView(DetailView):
    model = FileResource
    template_name = 'catalog/file_detail.html'
    context_object_name = 'file'


class FileResourceCreateView(CreateView):
    model = FileResource
    form_class = FileResourceForm
    template_name = 'catalog/file_form.html'
    success_url = reverse_lazy('catalog:file_list')


class FileResourceUpdateView(UpdateView):
    model = FileResource
    form_class = FileResourceForm
    template_name = 'catalog/file_form.html'
    success_url = reverse_lazy('catalog:file_list')


class FileResourceDeleteView(DeleteView):
    model = FileResource
    template_name = 'catalog/file_confirm_delete.html'
    success_url = reverse_lazy('catalog:file_list')


class TagCreateView(CreateView):
    model = Tag
    form_class = TagForm
    template_name = 'catalog/tag_form.html'
    success_url = reverse_lazy('catalog:file_create')


class TagUpdateView(UpdateView):
    model = Tag
    form_class = TagForm
    template_name = 'catalog/tag_form.html'
    success_url = reverse_lazy('catalog:file_create')


class FileSearchView(ListView):
    model = FileResource
    template_name = 'catalog/search.html'
    context_object_name = 'files'
    paginate_by = 20

    def get_queryset(self):
        self.form = FileSearchForm(self.request.GET or None)
        qs = FileResource.objects.select_related('project', 'device').prefetch_related('tags')

        if self.form.is_valid():
            data = self.form.cleaned_data
            if data.get('file_name'):
                qs = qs.filter(file_name__icontains=data['file_name'])
            if data.get('relative_path'):
                qs = qs.filter(relative_path__icontains=data['relative_path'])
            if data.get('project'):
                qs = qs.filter(project=data['project'])
            if data.get('device'):
                qs = qs.filter(device=data['device'])
            if data.get('extension'):
                qs = qs.filter(extension__iexact=data['extension'])
            if data.get('tags'):
                qs = qs.filter(tags__in=data['tags']).distinct()
            if data.get('size_min') is not None:
                qs = qs.filter(size_bytes__gte=data['size_min'])
            if data.get('size_max') is not None:
                qs = qs.filter(size_bytes__lte=data['size_max'])
            if data.get('created_at_fs_start'):
                qs = qs.filter(created_at_fs__gte=data['created_at_fs_start'])
            if data.get('created_at_fs_end'):
                qs = qs.filter(created_at_fs__lte=data['created_at_fs_end'])
            if data.get('updated_at_fs_start'):
                qs = qs.filter(updated_at_fs__gte=data['updated_at_fs_start'])
            if data.get('updated_at_fs_end'):
                qs = qs.filter(updated_at_fs__lte=data['updated_at_fs_end'])

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = getattr(self, 'form', FileSearchForm())
        query = self.request.GET.copy()
        query.pop('page', None)
        context['querystring'] = query.urlencode()
        return context
