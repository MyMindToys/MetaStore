"""Custom authentication for scanner agents (Authorization: Scanner <token>)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions

from catalog.models import Device


class ScannerTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Scanner"

    def authenticate(self, request):
        auth = request.headers.get("Authorization")
        if not auth:
            return None
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword.lower():
            return None
        token = parts[1].strip()
        if not token:
            return None
        device = Device.objects.filter(scanner_token=token).first()
        if device is None:
            raise exceptions.AuthenticationFailed(_("Invalid scanner token"))
        # DRF expects (user, auth); use device as user surrogate with is_authenticated True
        return (ScannerUser(device), token)


class ScannerUser:
    """Minimal user-like wrapper so IsAuthenticated works."""

    is_authenticated = True

    def __init__(self, device: Device) -> None:
        self.device = device
        self.pk = device.pk

    def __str__(self) -> str:
        return f"ScannerUser(device={self.device.pk})"
