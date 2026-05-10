from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from .forms import (
    DeviceForm,
    FileResourceForm,
    FileSearchForm,
    LinkedResourceForm,
    LiteratureSearchForm,
    MaterialForm,
    MaterialKindForm,
    MaterialLocationTagsForm,
    ProjectForm,
    TagForm,
)
from .models import (
    Device,
    FileResource,
    FileResourceLocation,
    LinkedResource,
    Material,
    MaterialKind,
    MaterialLocation,
    Project,
    Tag,
)


def _parse_tag_names(raw: str) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.replace(';', ',').split(',') if t.strip()][:200]


def _sync_file_resource_from_material(material: Material) -> None:
    """Дублирует запись в раздел «Файлы» (FileResource) по первому известному пути на диске."""
    if not material.project_id:
        return
    loc = (
        material.locations.filter(availability=MaterialLocation.Availability.PRESENT)
        .select_related('device', 'storage_location')
        .first()
    )
    if loc is None:
        return
    rel = (loc.relative_path or '')[:1024]
    fr, _ = FileResource.objects.update_or_create(
        device=loc.device,
        relative_path=rel,
        defaults={
            'project': material.project,
            'file_name': (material.file_name or '')[:255],
            'extension': (material.extension or '')[:50],
            'size_bytes': material.size_bytes,
            'checksum': (material.checksum_sha256 or '')[:255],
        },
    )
    fr.tags.set(material.tags.all())


class ScanInboxView(View):
    """Список материалов, пришедших с полного сканирования и ожидающих проект и теги."""

    template_name = 'catalog/scan_inbox.html'
    paginate_by = 40

    def get_context(self, request):
        qs = (
            Material.objects.filter(scan_import_pending=True)
            .select_related('project', 'material_kind')
            .prefetch_related(
                'tags',
                Prefetch(
                    'locations',
                    queryset=MaterialLocation.objects.select_related(
                        'device',
                        'storage_location',
                    ).order_by('device_id', 'relative_path'),
                ),
            )
            .order_by('-created_at')
        )
        paginator = Paginator(qs, self.paginate_by)
        page = request.GET.get('page') or 1
        page_obj = paginator.get_page(page)
        return {
            'page_obj': page_obj,
            'projects': Project.objects.all(),
            'pending_count': Material.objects.filter(scan_import_pending=True).count(),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request))

    def post(self, request, *args, **kwargs):
        ids = request.POST.getlist('material_id')
        if not ids:
            messages.warning(request, 'Не выбрано ни одной записи.')
            next_url = request.POST.get('next') or reverse('catalog:scan_inbox')
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = reverse('catalog:scan_inbox')
            return redirect(next_url)

        updated = 0
        with transaction.atomic():
            for sid in ids:
                try:
                    pk = int(sid)
                except (TypeError, ValueError):
                    continue
                material = Material.objects.filter(pk=pk, scan_import_pending=True).first()
                if material is None:
                    continue
                proj_raw = (request.POST.get(f'project_{pk}', '') or '').strip()
                project = None
                if proj_raw.isdigit():
                    project = Project.objects.filter(pk=int(proj_raw)).first()
                tag_names = _parse_tag_names(request.POST.get(f'tags_{pk}', ''))
                tags = []
                for name in tag_names:
                    tag, _ = Tag.objects.get_or_create(name=name[:100])
                    tags.append(tag)
                material.project = project
                material.scan_import_pending = False
                material.save(update_fields=['project', 'scan_import_pending'])
                material.tags.set(tags)
                _sync_file_resource_from_material(material)
                updated += 1

        messages.success(request, f'Сохранено записей: {updated}. Они убраны из очереди разбора.')
        next_url = request.POST.get('next') or reverse('catalog:scan_inbox')
        if not next_url.startswith('/') or next_url.startswith('//'):
            next_url = reverse('catalog:scan_inbox')
        return redirect(next_url)


class ScannerHelpView(TemplateView):
    """Памятка для пользователей: как запускать сканер, без технических деталей."""

    template_name = 'catalog/scanner_help.html'


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

    def get_queryset(self):
        loc_qs = FileResourceLocation.objects.select_related('device', 'storage_location').order_by(
            'device_id', 'relative_path'
        )
        return FileResource.objects.select_related('project', 'device').prefetch_related(
            Prefetch('disk_locations', queryset=loc_qs),
            'tags',
        )


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


class TagListView(ListView):
    model = Tag
    template_name = 'catalog/tag_list.html'
    context_object_name = 'tags'

    def get_queryset(self):
        return (
            Tag.objects.annotate(
                num_files=Count('files', distinct=True),
                num_materials=Count('materials', distinct=True),
                num_links=Count('linked_resource_links', distinct=True),
                num_locations=Count('material_location_paths', distinct=True),
            )
            .order_by('name')
        )


class TagCreateView(CreateView):
    model = Tag
    form_class = TagForm
    template_name = 'catalog/tag_form.html'
    success_url = reverse_lazy('catalog:tag_list')


class TagUpdateView(UpdateView):
    model = Tag
    form_class = TagForm
    template_name = 'catalog/tag_form.html'
    success_url = reverse_lazy('catalog:tag_list')


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


class MaterialKindListView(ListView):
    model = MaterialKind
    template_name = 'catalog/material_kind_list.html'
    context_object_name = 'material_kinds'

    def get_queryset(self):
        return MaterialKind.objects.annotate(material_count=Count('materials')).order_by('sort_order', 'name')


class MaterialKindCreateView(CreateView):
    model = MaterialKind
    form_class = MaterialKindForm
    template_name = 'catalog/material_kind_form.html'
    success_url = reverse_lazy('catalog:material_kind_list')


class MaterialKindUpdateView(UpdateView):
    model = MaterialKind
    form_class = MaterialKindForm
    template_name = 'catalog/material_kind_form.html'
    success_url = reverse_lazy('catalog:material_kind_list')


class MaterialListView(ListView):
    model = Material
    template_name = 'catalog/material_list.html'
    context_object_name = 'materials'
    paginate_by = 25

    def get_queryset(self):
        qs = Material.objects.select_related('project', 'material_kind').prefetch_related('tags').order_by('-created_at')
        show_all = self.request.GET.get('all') == '1'
        if not show_all:
            qs = qs.filter(material_kind__is_literature=True)
        kind = self.request.GET.get('kind')
        if kind:
            qs = qs.filter(material_kind__code=kind)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['literature_kinds'] = MaterialKind.objects.filter(is_literature=True).order_by('sort_order', 'name')
        ctx['show_all'] = self.request.GET.get('all') == '1'
        ctx['filter_kind'] = self.request.GET.get('kind') or ''
        query = self.request.GET.copy()
        query.pop('page', None)
        ctx['querystring'] = query.urlencode()
        return ctx


class LiteratureSearchView(ListView):
    model = Material
    template_name = 'catalog/literature_search.html'
    context_object_name = 'materials'
    paginate_by = 25

    def get_queryset(self):
        self.form = LiteratureSearchForm(self.request.GET or None)
        qs = (
            Material.objects.filter(material_kind__is_literature=True)
            .select_related('project', 'material_kind')
            .prefetch_related('tags')
            .distinct()
            .order_by('-created_at')
        )

        if self.form.is_valid():
            q = (self.form.cleaned_data.get('q') or '').strip()
            kind = self.form.cleaned_data.get('material_kind')
            if kind:
                qs = qs.filter(material_kind=kind)
            if q:
                linked_ids = LinkedResource.objects.filter(
                    Q(title__icontains=q) | Q(url__icontains=q) | Q(description__icontains=q)
                ).values_list('material_id', flat=True)
                file_linked_ids = LinkedResource.objects.filter(
                    Q(file_resource__file_name__icontains=q)
                    | Q(file_resource__relative_path__icontains=q)
                ).values_list('material_id', flat=True)
                linked_tag_material_ids = LinkedResource.objects.filter(
                    tags__name__icontains=q
                ).values_list('material_id', flat=True)
                location_tag_material_ids = MaterialLocation.objects.filter(
                    tags__name__icontains=q
                ).values_list('material_id', flat=True)
                material_tag_ids = Material.objects.filter(tags__name__icontains=q).values_list('pk', flat=True)
                qs = qs.filter(
                    Q(topic__icontains=q)
                    | Q(file_name__icontains=q)
                    | Q(source_path__icontains=q)
                    | Q(description__icontains=q)
                    | Q(pk__in=material_tag_ids)
                    | Q(pk__in=linked_ids)
                    | Q(pk__in=file_linked_ids)
                    | Q(pk__in=linked_tag_material_ids)
                    | Q(pk__in=location_tag_material_ids)
                ).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = getattr(self, 'form', LiteratureSearchForm())
        query = self.request.GET.copy()
        query.pop('page', None)
        ctx['querystring'] = query.urlencode()
        return ctx


class MaterialDetailView(DetailView):
    model = Material
    template_name = 'catalog/material_detail.html'
    context_object_name = 'material'

    def get_queryset(self):
        return Material.objects.select_related('project', 'material_kind').prefetch_related('tags')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        material = self.object
        ctx['linked_resources'] = (
            material.linked_resources.select_related('file_resource')
            .prefetch_related('tags')
            .order_by('created_at')
        )
        ctx['locations'] = (
            material.locations.select_related('device', 'storage_location')
            .prefetch_related('tags')
            .order_by('device_id', 'relative_path')
        )
        return ctx


class MaterialCreateView(CreateView):
    model = Material
    form_class = MaterialForm
    template_name = 'catalog/material_form.html'

    def get_initial(self):
        initial = super().get_initial()
        kind_code = self.request.GET.get('kind')
        if kind_code:
            mk = MaterialKind.objects.filter(code=kind_code).first()
            if mk:
                initial['material_kind'] = mk.pk
        return initial

    def get_success_url(self):
        return reverse('catalog:material_detail', kwargs={'pk': self.object.pk})


class MaterialUpdateView(UpdateView):
    model = Material
    form_class = MaterialForm
    template_name = 'catalog/material_form.html'

    def get_success_url(self):
        return reverse('catalog:material_detail', kwargs={'pk': self.object.pk})


class MaterialDeleteView(DeleteView):
    model = Material
    template_name = 'catalog/material_confirm_delete.html'
    success_url = reverse_lazy('catalog:material_list')


class LinkedResourceCreateView(CreateView):
    model = LinkedResource
    form_class = LinkedResourceForm
    template_name = 'catalog/linked_resource_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.parent_material = get_object_or_404(Material, pk=kwargs['material_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.material = self.parent_material
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['material'] = self.parent_material
        return ctx

    def get_success_url(self):
        return reverse('catalog:material_detail', kwargs={'pk': self.parent_material.pk})


class LinkedResourceUpdateView(UpdateView):
    model = LinkedResource
    form_class = LinkedResourceForm
    template_name = 'catalog/linked_resource_form.html'
    pk_url_kwarg = 'pk'

    def dispatch(self, request, *args, **kwargs):
        self.parent_material = get_object_or_404(Material, pk=kwargs['material_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return LinkedResource.objects.filter(material=self.parent_material)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['material'] = self.parent_material
        return ctx

    def get_success_url(self):
        return reverse('catalog:material_detail', kwargs={'pk': self.parent_material.pk})


class MaterialLocationTagsUpdateView(UpdateView):
    model = MaterialLocation
    form_class = MaterialLocationTagsForm
    template_name = 'catalog/material_location_tags_form.html'
    pk_url_kwarg = 'pk'

    def dispatch(self, request, *args, **kwargs):
        self.parent_material = get_object_or_404(Material, pk=kwargs['material_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return MaterialLocation.objects.filter(material=self.parent_material)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['material'] = self.parent_material
        return ctx

    def get_success_url(self):
        return reverse('catalog:material_detail', kwargs={'pk': self.parent_material.pk})


class LinkedResourceDeleteView(DeleteView):
    model = LinkedResource
    template_name = 'catalog/linked_resource_confirm_delete.html'
    pk_url_kwarg = 'pk'

    def dispatch(self, request, *args, **kwargs):
        self.parent_material = get_object_or_404(Material, pk=kwargs['material_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return LinkedResource.objects.filter(material=self.parent_material)

    def get_success_url(self):
        return reverse('catalog:material_detail', kwargs={'pk': self.parent_material.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['material'] = self.parent_material
        return ctx
