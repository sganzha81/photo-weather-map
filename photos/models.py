import json
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from django.db import models
from .weather import fetch_weather_for_photo


def get_exif_data(image):
    """Извлекает все EXIF-теги из открытого изображения."""
    exif_data = {}
    info = image._getexif()
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                gps_data = {}
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_data[sub_decoded] = value[t]
                exif_data[decoded] = gps_data
            else:
                exif_data[decoded] = value
    return exif_data


def dms_to_decimal(dms, ref):
    """Переводит координаты из градусов/минут/секунд в десятичные."""
    degrees, minutes, seconds = dms
    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    if ref in ["S", "W"]:
        decimal = -decimal
    return decimal


def extract_gps(exif_data):
    """Вытаскивает широту и долготу из GPSInfo, если есть."""
    gps_info = exif_data.get("GPSInfo")
    if not gps_info:
        return None, None
    lat_dms = gps_info.get("GPSLatitude")
    lat_ref = gps_info.get("GPSLatitudeRef")
    lon_dms = gps_info.get("GPSLongitude")
    lon_ref = gps_info.get("GPSLongitudeRef")
    if not all([lat_dms, lat_ref, lon_dms, lon_ref]):
        return None, None
    lat = dms_to_decimal(lat_dms, lat_ref)
    lon = dms_to_decimal(lon_dms, lon_ref)
    return lat, lon


def extract_datetime(exif_data):
    """Вытаскивает дату и время съёмки."""
    date_str = exif_data.get("DateTimeOriginal") or exif_data.get("DateTimeDigitized")
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except (ValueError, TypeError):
            pass
    return None


class Photo(models.Model):
    image = models.ImageField(upload_to="photos/%Y/%m/")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    weather_data = models.JSONField(null=True, blank=True)
    exif_raw = models.JSONField(null=True, blank=True)

    def clean(self):
        """При сохранении попытаемся извлечь EXIF, но только у новых фото."""
        if self.image and not self.pk:
            try:
                img = Image.open(self.image)
                exif = get_exif_data(img)

                # Сохраним все читаемые поля как JSON
                serializable = {}
                for k, v in exif.items():
                    if isinstance(v, bytes):
                        continue
                    try:
                        json.dumps(v)
                        serializable[k] = v
                    except (TypeError, ValueError):
                        pass
                self.exif_raw = serializable

                lat, lon = extract_gps(exif)
                if lat is not None and lon is not None:
                    self.latitude = lat
                    self.longitude = lon

                taken = extract_datetime(exif)
                if taken:
                    self.taken_at = taken
                if (
                    self.latitude is not None
                    and self.longitude is not None
                    and self.taken_at is not None
                ):
                    weather = fetch_weather_for_photo(
                        self.latitude, self.longitude, self.taken_at
                    )
                    if weather:
                        self.weather_data = weather
            except Exception:
                # Если не получилось – не страшно, фото сохранится без EXIF
                pass

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        dt = self.taken_at or self.uploaded_at
        coords = (
            f"({self.latitude}, {self.longitude})" if self.latitude else "без координат"
        )
        return f"Photo {self.id} {dt} {coords}"
