from django.contrib import admin

from .models import Device, FileResource, Project, Tag


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'device_type')
    list_filter = ('device_type',)
    search_fields = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(FileResource)
class FileResourceAdmin(admin.ModelAdmin):
    list_display = ('project', 'device', 'file_name', 'extension', 'size_bytes', 'created_at_fs')
    list_filter = ('project', 'device', 'extension', 'tags')
    search_fields = ('file_name', 'relative_path', 'project__name')
    filter_horizontal = ('tags',)
    readonly_fields = ('created_at',)
