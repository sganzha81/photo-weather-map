import json
import io
import hashlib

from datetime import datetime

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

import pillow_heif

from .weather import fetch_weather_for_photo

pillow_heif.register_heif_opener()



def validate_image_size(image):
    max_size_mb = 10
    if image.size > max_size_mb * 1024 * 1024:
        raise ValidationError(
            f"Файл слишком большой! Максимальный размер: {max_size_mb} МБ."
        )


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
    image = models.ImageField(
        upload_to="photos/%Y/%m/", validators=[validate_image_size]
    )
    file_hash = models.CharField(max_length=64, blank=True, null=True, verbose_name='Хэш файла')
    pixel_hash = models.CharField(max_length=64, blank=True, null=True, verbose_name='Хэш пикселей')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Пользователь",
    )
    weather_data = models.JSONField(null=True, blank=True)
    exif_raw = models.JSONField(null=True, blank=True)

    def clean(self):
        if self.image and not self.pk:
            try:
                # Читаем все байты загруженного файла для побайтового хэша
                self.image.seek(0)
                file_bytes = self.image.read()
                self.file_hash = hashlib.sha256(file_bytes).hexdigest()
            
                # Открываем изображение через Pillow
                img = Image.open(io.BytesIO(file_bytes))
            
                # EXIF-парсинг (твоя неизменная логика)
                exif = get_exif_data(img)
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

                # Пиксельный хэш (визуальный)
                with io.BytesIO() as output:
                    img.save(output, format='BMP')
                    pixel_bytes = output.getvalue()
                self.pixel_hash = hashlib.sha256(pixel_bytes).hexdigest()

                # Проверка на дубликат для этого пользователя
                if self.user and self.pixel_hash:
                    exists = Photo.objects.filter(
                        user=self.user,
                        pixel_hash=self.pixel_hash
                    ).exclude(pk=self.pk).exists()
                    if exists:
                        raise ValidationError('Вы уже загружали такое фото (визуально идентичное).')

            except ValidationError:
                raise  # наша ошибка пробрасывается наружу
            except Exception:
                pass  # другие ошибки не прерывают сохранение

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        dt = self.taken_at or self.uploaded_at
        coords = (
            f"({self.latitude}, {self.longitude})" if self.latitude else "без координат"
        )
        return f"Photo {self.id} {dt} {coords}"
    
    def delete(self, *args, **kwargs):
        # Удаляем файл изображения с диска, если он есть
        if self.image:
            storage, path = self.image.storage, self.image.name
            storage.delete(path)
        # Затем вызываем стандартное удаление, чтобы запись исчезла из БД
        super().delete(*args, **kwargs)