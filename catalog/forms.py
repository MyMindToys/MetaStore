from django import forms

from .models import Device, FileResource, LinkedResource, Material, MaterialKind, MaterialLocation, Project, Tag


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        labels = {
            'name': 'Название',
            'description': 'Описание',
        }


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['name', 'device_type', 'comment']
        labels = {
            'name': 'Название',
            'device_type': 'Тип устройства',
            'comment': 'Комментарий',
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']
        labels = {'name': 'Имя тега'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.setdefault('class', 'form-control')


class MaterialKindForm(forms.ModelForm):
    class Meta:
        model = MaterialKind
        fields = ['code', 'name', 'is_literature', 'sort_order']
        labels = {
            'code': 'Код',
            'name': 'Название',
            'is_literature': 'Раздел «литература»',
            'sort_order': 'Порядок сортировки',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].widget.attrs.setdefault('class', 'form-control')
        self.fields['name'].widget.attrs.setdefault('class', 'form-control')
        self.fields['sort_order'].widget.attrs.setdefault('class', 'form-control')
        self.fields['is_literature'].widget.attrs.setdefault('class', 'form-check-input')
        self.fields['is_literature'].label_suffix = ''
        if self.instance.pk:
            self.fields['code'].disabled = True
            self.fields['code'].help_text = 'Код не меняется после создания (используется в URL ?kind=…).'


class MaterialForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Material
        fields = [
            'material_kind',
            'topic',
            'project',
            'file_name',
            'extension',
            'size_bytes',
            'checksum_sha256',
            'description',
            'tags',
        ]
        labels = {
            'file_name': 'Название',
            'material_kind': 'Тип материала',
            'topic': 'Тема',
            'project': 'Проект',
            'extension': 'Расширение',
            'size_bytes': 'Размер (байт)',
            'checksum_sha256': 'SHA-256',
            'description': 'Описание',
            'tags': 'Теги',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('file_name', 'topic', 'extension', 'size_bytes', 'checksum_sha256'):
            self.fields[name].widget.attrs.setdefault('class', 'form-control')
        self.fields['material_kind'].queryset = MaterialKind.objects.all().order_by('sort_order', 'name')
        self.fields['material_kind'].widget.attrs.setdefault('class', 'form-select')
        self.fields['project'].widget.attrs.setdefault('class', 'form-select')
        self.fields['description'].widget.attrs.setdefault('class', 'form-control')
        self.fields['description'].widget.attrs.setdefault('rows', 4)
        if not self.instance.pk and not self.data:
            generic = MaterialKind.objects.filter(code='generic').first()
            if generic:
                self.initial.setdefault('material_kind', generic.pk)


class LinkedResourceForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = LinkedResource
        fields = ['resource_type', 'title', 'url', 'file_resource', 'description', 'tags']
        labels = {
            'resource_type': 'Тип ресурса',
            'title': 'Заголовок',
            'url': 'URL / DOI / идентификатор',
            'file_resource': 'Файл из каталога (необязательно)',
            'description': 'Описание',
            'tags': 'Теги',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file_resource'].queryset = FileResource.objects.select_related('project', 'device').order_by(
            '-created_at'
        )
        self.fields['resource_type'].widget.attrs.setdefault('class', 'form-select')
        self.fields['title'].widget.attrs.setdefault('class', 'form-control')
        self.fields['url'].widget.attrs.setdefault('class', 'form-control')
        self.fields['description'].widget.attrs.setdefault('class', 'form-control')
        self.fields['description'].widget.attrs.setdefault('rows', 3)
        self.fields['file_resource'].widget.attrs.setdefault('class', 'form-select')


class MaterialLocationTagsForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = MaterialLocation
        fields = ['tags']
        labels = {'tags': 'Теги для этого пути / копии'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class LiteratureSearchForm(forms.Form):
    q = forms.CharField(required=False, label='Ключевые слова')
    material_kind = forms.ModelChoiceField(
        queryset=MaterialKind.objects.none(),
        required=False,
        label='Тип материала',
        empty_label='Любой тип литературы',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material_kind'].queryset = MaterialKind.objects.filter(is_literature=True).order_by(
            'sort_order', 'name'
        )
        self.fields['q'].widget.attrs.update({'class': 'form-control'})
        self.fields['material_kind'].widget.attrs.update({'class': 'form-select'})


class FileResourceForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = FileResource
        fields = [
            'project',
            'device',
            'relative_path',
            'file_name',
            'extension',
            'size_bytes',
            'created_at_fs',
            'updated_at_fs',
            'checksum',
            'description',
            'tags',
        ]
        widgets = {
            'created_at_fs': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'updated_at_fs': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        labels = {
            'project': 'Проект',
            'device': 'Устройство',
            'relative_path': 'Относительный путь',
            'file_name': 'Имя файла',
            'extension': 'Расширение',
            'size_bytes': 'Размер (байт)',
            'created_at_fs': 'Создано в ФС',
            'updated_at_fs': 'Изменено в ФС',
            'checksum': 'Контрольная сумма',
            'description': 'Описание',
            'tags': 'Теги',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('relative_path', 'file_name', 'extension', 'size_bytes', 'checksum', 'description'):
            self.fields[name].widget.attrs.setdefault('class', 'form-control')
        self.fields['project'].widget.attrs.setdefault('class', 'form-select')
        self.fields['device'].widget.attrs.setdefault('class', 'form-select')
        self.fields['created_at_fs'].widget.attrs.setdefault('class', 'form-control')
        self.fields['updated_at_fs'].widget.attrs.setdefault('class', 'form-control')
        self.fields['description'].widget.attrs.setdefault('rows', 4)


class FileSearchForm(forms.Form):
    file_name = forms.CharField(required=False, label='Имя файла содержит')
    relative_path = forms.CharField(required=False, label='Путь содержит')
    project = forms.ModelChoiceField(queryset=Project.objects.all(), required=False, label='Проект')
    device = forms.ModelChoiceField(queryset=Device.objects.all(), required=False, label='Устройство')
    extension = forms.CharField(required=False, label='Расширение')
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False, label='Теги')
    size_min = forms.IntegerField(required=False, min_value=0, label='Мин. размер (байт)')
    size_max = forms.IntegerField(required=False, min_value=0, label='Макс. размер (байт)')
    created_at_fs_start = forms.DateTimeField(
        required=False,
        label='Создано с',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )
    created_at_fs_end = forms.DateTimeField(
        required=False,
        label='Создано по',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )
    updated_at_fs_start = forms.DateTimeField(
        required=False,
        label='Изменено с',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )
    updated_at_fs_end = forms.DateTimeField(
        required=False,
        label='Изменено по',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_fields = ['file_name', 'relative_path', 'extension', 'size_min', 'size_max']
        select_fields = ['project', 'device', 'tags']
        datetime_fields = ['created_at_fs_start', 'created_at_fs_end', 'updated_at_fs_start', 'updated_at_fs_end']

        for name in text_fields:
            self.fields[name].widget.attrs.update({'class': 'form-control'})
        for name in select_fields:
            self.fields[name].widget.attrs.update({'class': 'form-select'})
        for name in datetime_fields:
            self.fields[name].widget.attrs.update({'class': 'form-control'})
