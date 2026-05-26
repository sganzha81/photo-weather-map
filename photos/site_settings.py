from django.db.utils import OperationalError, ProgrammingError

from .models import SiteSettings

DEFAULT_USER_STORAGE_LIMIT_MB = 100
BYTES_IN_MB = 1024 * 1024


def get_user_storage_limit_mb():
    try:
        settings = SiteSettings.objects.order_by("pk").first()
    except (OperationalError, ProgrammingError):
        return DEFAULT_USER_STORAGE_LIMIT_MB
    except Exception:
        return DEFAULT_USER_STORAGE_LIMIT_MB

    if not settings:
        return DEFAULT_USER_STORAGE_LIMIT_MB

    return settings.user_storage_limit_mb or DEFAULT_USER_STORAGE_LIMIT_MB


def get_user_storage_limit_bytes():
    return get_user_storage_limit_mb() * BYTES_IN_MB
