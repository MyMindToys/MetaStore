"""Serializers for REST API."""

from rest_framework import serializers

from catalog.models import Device, Material, MaterialKind, MaterialLocation, StorageLocation


class MaterialKindSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialKind
        fields = ['id', 'code', 'name', 'is_literature', 'sort_order']


class DeviceRegistrationSerializer(serializers.Serializer):
    machine_uid = serializers.CharField(max_length=128)
    hostname = serializers.CharField(max_length=255, required=False, allow_blank=True)
    os_name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    platform_name = serializers.CharField(max_length=2048, required=False, allow_blank=True)
    display_name = serializers.CharField(max_length=255, required=False, allow_blank=True)


class HeartbeatSerializer(serializers.Serializer):
    machine_uid = serializers.CharField(max_length=128)
    scanner_version = serializers.CharField(max_length=64)


class ScanUploadSerializer(serializers.Serializer):
    device_machine_uid = serializers.CharField(max_length=128)
    storage_location_root = serializers.CharField(max_length=2048)
    scanner_version = serializers.CharField(max_length=64, required=False)
    entries = serializers.ListField(child=serializers.DictField(), allow_empty=True)
    deleted_relative_paths = serializers.ListField(child=serializers.CharField(), required=False)


class MaterialSerializer(serializers.ModelSerializer):
    material_kind = MaterialKindSerializer(read_only=True)
    material_kind_code = serializers.CharField(source='material_kind.code', read_only=True)

    class Meta:
        model = Material
        fields = [
            'id',
            'material_kind',
            'material_kind_code',
            'topic',
            'project_id',
            'file_name',
            'extension',
            'size_bytes',
            'checksum_sha256',
            'source_path',
            'description',
            'created_at',
        ]


class StorageLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageLocation
        fields = ['id', 'device_id', 'name', 'root_path']


class MaterialLocationSerializer(serializers.ModelSerializer):
    material = MaterialSerializer(read_only=True)

    class Meta:
        model = MaterialLocation
        fields = [
            'id',
            'material',
            'device_id',
            'storage_location_id',
            'relative_path',
            'checksum',
            'sync_status',
            'availability',
            'updated_at',
        ]
