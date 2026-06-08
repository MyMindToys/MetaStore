from django.contrib import admin

from .models import (
    Device,
    FileResource,
    FileResourceLocation,
    LinkedResource,
    Material,
    MaterialKind,
    MaterialLocation,
    Project,
    StorageLocation,
    Tag,
)


class LinkedResourceInline(admin.TabularInline):
    model = LinkedResource
    extra = 0
    autocomplete_fields = ('file_resource',)
    filter_horizontal = ('tags',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'device_type',
        'machine_uid',
        'hostname',
        'last_seen_at',
        'last_sync_at',
    )
    list_filter = ('device_type',)
    search_fields = ('name', 'machine_uid', 'hostname')
    readonly_fields = ('scanner_token', 'last_seen_at', 'last_sync_at')


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ('device', 'name', 'root_path')
    search_fields = ('root_path', 'name')


@admin.register(MaterialKind)
class MaterialKindAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_literature', 'sort_order')
    list_filter = ('is_literature',)
    search_fields = ('code', 'name')
    ordering = ('sort_order', 'name')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'material_kind', 'topic', 'extension', 'size_bytes', 'checksum_sha256', 'created_at')
    list_filter = ('material_kind',)
    search_fields = ('file_name', 'topic', 'checksum_sha256', 'description', 'source_path')
    filter_horizontal = ('tags',)
    inlines = (LinkedResourceInline,)


@admin.register(LinkedResource)
class LinkedResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'material', 'resource_type', 'url', 'file_resource', 'created_at')
    list_filter = ('resource_type',)
    search_fields = ('title', 'url', 'description')
    autocomplete_fields = ('material', 'file_resource')
    filter_horizontal = ('tags',)


@admin.register(MaterialLocation)
class MaterialLocationAdmin(admin.ModelAdmin):
    list_display = ('material', 'device', 'storage_location', 'relative_path', 'availability', 'sync_status')
    list_filter = ('availability', 'sync_status', 'device')
    search_fields = ('relative_path', 'material__file_name')
    filter_horizontal = ('tags',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class FileResourceLocationInline(admin.TabularInline):
    model = FileResourceLocation
    extra = 0
    readonly_fields = ('device', 'storage_location', 'relative_path', 'size_bytes', 'mtime_fs', 'updated_at')
    can_delete = True


@admin.register(FileResource)
class FileResourceAdmin(admin.ModelAdmin):
    list_display = ('project', 'device', 'file_name', 'extension', 'size_bytes', 'created_at_fs')
    list_filter = ('project', 'device', 'extension', 'tags')
    search_fields = ('file_name', 'relative_path', 'project__name')
    filter_horizontal = ('tags',)
    readonly_fields = ('created_at',)
    inlines = (FileResourceLocationInline,)
