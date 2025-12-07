from django import forms

from .models import Device, FileResource, Project, Tag


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['name', 'device_type', 'comment']


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']


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


class FileSearchForm(forms.Form):
    file_name = forms.CharField(required=False, label='File name contains')
    relative_path = forms.CharField(required=False, label='Path contains')
    project = forms.ModelChoiceField(queryset=Project.objects.all(), required=False)
    device = forms.ModelChoiceField(queryset=Device.objects.all(), required=False)
    extension = forms.CharField(required=False)
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False)
    size_min = forms.IntegerField(required=False, min_value=0, label='Min size (bytes)')
    size_max = forms.IntegerField(required=False, min_value=0, label='Max size (bytes)')
    created_at_fs_start = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    created_at_fs_end = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    updated_at_fs_start = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    updated_at_fs_end = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))

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
