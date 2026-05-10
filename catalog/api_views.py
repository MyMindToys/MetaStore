"""REST API views for scanner and catalog."""

from __future__ import annotations

import secrets
from pathlib import Path

from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from catalog.api_serializers import (
    DeviceRegistrationSerializer,
    HeartbeatSerializer,
    MaterialLocationSerializer,
    MaterialSerializer,
    ScanUploadSerializer,
    StorageLocationSerializer,
)
from catalog.authentication import ScannerTokenAuthentication, ScannerUser
from catalog.models import (
    Device,
    FileResource,
    FileResourceLocation,
    Material,
    MaterialKind,
    MaterialLocation,
    StorageLocation,
)

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def _parse_entry_mtime(entry: dict):
    raw = entry.get('modified_at_fs')
    if raw is None:
        return None
    if hasattr(raw, 'isoformat'):
        return raw
    return parse_datetime(str(raw))


def _link_file_resources_from_scan_entry(
    entry: dict,
    device,
    loc,
    rel: str,
    name: str,
    checksum_raw: str,
) -> None:
    """Сначала все записи каталога с тем же SHA-256 (один файл — несколько путей), иначе по имени файла."""
    rel_key = rel[:2048]
    ch = (checksum_raw or '').strip()[:128]
    size_b = entry.get('size_bytes')
    if size_b is not None:
        try:
            size_b = int(size_b)
        except (TypeError, ValueError):
            size_b = None
    mtime_fs = _parse_entry_mtime(entry)

    defaults: dict = {}
    if size_b is not None:
        defaults['size_bytes'] = size_b
    if mtime_fs is not None:
        defaults['mtime_fs'] = mtime_fs

    def upsert(fr) -> None:
        FileResourceLocation.objects.update_or_create(
            file_resource=fr,
            device=device,
            storage_location=loc,
            relative_path=rel_key,
            defaults=defaults,
        )

    if ch:
        by_hash = FileResource.objects.filter(checksum__iexact=ch)
        if by_hash.exists():
            for fr in by_hash:
                upsert(fr)
            return

    fr_qs = FileResource.objects.filter(file_name=name)
    if ch:
        fr_qs = fr_qs.filter(Q(checksum='') | Q(checksum__iexact=ch))
    for fr in fr_qs:
        upsert(fr)


class IsScannerAgent(permissions.BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, ScannerUser)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def register_device(request):
    ser = DeviceRegistrationSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    machine_uid = data['machine_uid']

    display_name = (data.get('display_name') or data.get('hostname') or machine_uid)[:255]

    device = Device.objects.filter(machine_uid=machine_uid).first()
    created = False
    if device is None:
        device = Device.objects.create(
            name=display_name,
            hostname=data.get('hostname') or '',
            os_name=data.get('os_name') or '',
            platform_name=data.get('platform_name') or '',
            machine_uid=machine_uid,
            device_type=Device.DeviceType.OTHER,
        )
        created = True
    else:
        Device.objects.filter(pk=device.pk).update(
            name=display_name,
            hostname=data.get('hostname') or '',
            os_name=data.get('os_name') or '',
            platform_name=data.get('platform_name') or '',
        )
        device.refresh_from_db()

    if not device.scanner_token:
        device.scanner_token = secrets.token_urlsafe(48)[:128]
        device.save(update_fields=['scanner_token'])

    return Response(
        {
            'device_id': device.pk,
            'scanner_token': device.scanner_token,
            'created': created,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([ScannerTokenAuthentication])
@permission_classes([IsScannerAgent])
def upload_scan(request):
    ser = ScanUploadSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    payload = ser.validated_data

    user = request.user
    assert isinstance(user, ScannerUser)
    device = user.device

    if payload['device_machine_uid'] and device.machine_uid != payload['device_machine_uid']:
        return Response({'detail': 'machine_uid mismatch'}, status=status.HTTP_400_BAD_REQUEST)

    root = payload['storage_location_root']
    loc, _ = StorageLocation.objects.get_or_create(
        device=device,
        root_path=root,
        defaults={'name': Path(root).name[:255]},
    )

    entries = payload.get('entries') or []
    deleted = payload.get('deleted_relative_paths') or []

    generic_kind = MaterialKind.objects.filter(code='generic').order_by('pk').first()
    if generic_kind is None:
        generic_kind = MaterialKind.objects.order_by('pk').first()

    with transaction.atomic():
        for entry in entries:
            if entry.get('availability') != 'present':
                continue
            if entry.get('kind') == 'folder':
                continue

            rel = entry.get('relative_path') or ''
            name = entry.get('name') or Path(rel).name
            checksum = (entry.get('checksum_sha256') or '').strip()

            material = None
            if checksum:
                material = Material.objects.filter(checksum_sha256=checksum, file_name=name).first()
            if material is None:
                if generic_kind is None:
                    return Response(
                        {'detail': 'No MaterialKind in database (run migrations).'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                material = Material.objects.create(
                    material_kind=generic_kind,
                    file_name=name,
                    extension=(entry.get('extension') or '')[:50],
                    size_bytes=entry.get('size_bytes'),
                    checksum_sha256=checksum[:128] if checksum else '',
                    scan_import_pending=True,
                )

            MaterialLocation.objects.update_or_create(
                device=device,
                storage_location=loc,
                relative_path=rel[:2048],
                defaults={
                    'material': material,
                    'checksum': checksum[:128] if checksum else '',
                    'availability': MaterialLocation.Availability.PRESENT,
                    'sync_status': MaterialLocation.SyncStatus.SYNCED,
                },
            )

            _link_file_resources_from_scan_entry(entry, device, loc, rel, name, checksum)

        if deleted:
            MaterialLocation.objects.filter(
                device=device,
                storage_location=loc,
                relative_path__in=[d[:2048] for d in deleted],
            ).update(availability=MaterialLocation.Availability.MISSING)
            FileResourceLocation.objects.filter(
                device=device,
                storage_location=loc,
                relative_path__in=[d[:2048] for d in deleted],
            ).delete()

        Device.objects.filter(pk=device.pk).update(last_sync_at=timezone.now())

    return Response({'status': 'ok', 'processed_entries': len(entries), 'marked_missing': len(deleted)})


@api_view(['POST'])
@authentication_classes([ScannerTokenAuthentication])
@permission_classes([IsScannerAgent])
def heartbeat(request):
    ser = HeartbeatSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = request.user
    assert isinstance(user, ScannerUser)
    device = user.device

    Device.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
    return Response({'status': 'ok'})


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def server_status(request):
    return Response({'ok': True, 'service': 'metastore-server'})


@api_view(['GET'])
@authentication_classes([ScannerTokenAuthentication])
@permission_classes([IsScannerAgent])
def materials_list(request):
    qs = Material.objects.select_related('material_kind').order_by('-created_at')[:500]
    return Response(MaterialSerializer(qs, many=True).data)


@api_view(['GET'])
@authentication_classes([ScannerTokenAuthentication])
@permission_classes([IsScannerAgent])
def locations_list(request):
    qs = MaterialLocation.objects.select_related('material', 'device', 'storage_location').order_by('id')[:1000]
    return Response(MaterialLocationSerializer(qs, many=True).data)


@api_view(['GET'])
@authentication_classes([ScannerTokenAuthentication])
@permission_classes([IsScannerAgent])
def storage_locations_list(request):
    qs = StorageLocation.objects.all().order_by('id')[:500]
    return Response(StorageLocationSerializer(qs, many=True).data)
