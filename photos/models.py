import json
import io, os
import hashlib

from datetime import datetime

from PIL.Image import Exif

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

import pillow_heif
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS

from .weather import fetch_weather_for_photo

pillow_heif.register_heif_opener()

from fractions import Fraction
import piexif

def _normalize_heic_exif_bytes(exif_bytes: bytes) -> bytes:
    """Делает EXIF-байты пригодными для piexif, добавляя 'Exif\x00\x00' если надо."""
    if not exif_bytes:
        return exif_bytes
    if exif_bytes.startswith(b"Exif\x00\x00"):
        return exif_bytes
    tiff_markers = [b"II*\x00", b"MM\x00*"]
    for marker in tiff_markers:
        idx = exif_bytes.find(marker)
        if idx != -1:
            return b"Exif\x00\x00" + exif_bytes[idx:]
    return exif_bytes

def _rational_to_float(value):
    """Переводит rational-пару (num, den) в float."""
    if isinstance(value, tuple) and len(value) == 2:
        num, den = value
        if den == 0:
            raise ZeroDivisionError("Invalid EXIF rational with denominator = 0")
        return float(Fraction(num, den))
    return float(value)

def _dms_to_decimal(dms, ref):
    """dms: ((num,den), (num,den), (num,den)), ref: b'N' или 'N'."""
    if isinstance(ref, bytes):
        ref = ref.decode("ascii", errors="ignore")
    ref = str(ref).strip().upper()
    if not dms or len(dms) != 3:
        raise ValueError(f"Invalid GPS DMS value: {dms!r}")
    degrees = _rational_to_float(dms[0])
    minutes = _rational_to_float(dms[1])
    seconds = _rational_to_float(dms[2])
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal

def extract_gps_from_heif(file_bytes):
    """Извлекает (latitude, longitude) из HEIC-файла, используя pillow_heif и piexif."""
    try:
        heif_file = pillow_heif.open_heif(io.BytesIO(file_bytes))
        exif_bytes = heif_file.info.get("exif")
        if not exif_bytes:
            return None, None

        normalized_exif = _normalize_heic_exif_bytes(exif_bytes)
        exif_dict = piexif.load(normalized_exif)
        gps = exif_dict.get("GPS") or {}

        lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef)
        lat_dms = gps.get(piexif.GPSIFD.GPSLatitude)
        lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef)
        lon_dms = gps.get(piexif.GPSIFD.GPSLongitude)

        if not lat_ref or not lat_dms or not lon_ref or not lon_dms:
            return None, None

        lat = _dms_to_decimal(lat_dms, lat_ref)
        lon = _dms_to_decimal(lon_dms, lon_ref)
        return lat, lon
    except Exception as e:
        print(f"Ошибка извлечения GPS из HEIC: {e}")
        return None, None

def validate_image_size(image):
    max_size_mb = 10
    if image.size > max_size_mb * 1024 * 1024:
        raise ValidationError(
            f"Файл слишком большой! Максимальный размер: {max_size_mb} МБ."
        )


def get_exif_data(image, file_bytes=None):
    """Извлекает EXIF из изображения, предпочитая прямой парсинг байтов."""
    exif_dict = {}
    # Пробуем получить сырые EXIF-байты
    exif_bytes = None
    if hasattr(image, 'info') and 'exif' in image.info:
        exif_bytes = image.info.get('exif')
    if not exif_bytes and file_bytes:
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                exif_bytes = img.info.get('exif')
        except Exception:
            pass

    if exif_bytes:
        try:
            exif_obj = Exif.from_bytes(exif_bytes)
            for tag_id, value in exif_obj.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "GPSInfo":
                    # GPSInfo в объекте Exif – это уже распарсенный словарь, просто переводим ключи
                    gps_data = {}
                    if isinstance(value, dict):
                        for gps_tag_id, gps_value in value.items():
                            gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            gps_data[gps_tag_name] = gps_value
                    exif_dict[tag_name] = gps_data if gps_data else value
                else:
                    exif_dict[tag_name] = value
            return exif_dict
        except Exception as e:
            print(f"Ошибка парсинга Exif.from_bytes: {e}")

    # Если не получилось, возвращаемся к getexif() с защитой от ошибок
    try:
        exif = image.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "GPSInfo":
                    gps_data = {}
                    if isinstance(value, dict):
                        for gps_tag_id, gps_value in value.items():
                            gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            gps_data[gps_tag_name] = gps_value
                    exif_dict[tag_name] = gps_data if gps_data else value
                else:
                    exif_dict[tag_name] = value
    except Exception as e:
        print(f"Ошибка getexif(): {e}")

    return exif_dict

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
                # --- 0. Читаем сырые байты ---
                self.image.seek(0)
                file_bytes = self.image.read()
                self.image.seek(0)

                # --- 1. Если файл HEIC – извлекаем GPS напрямую, конвертируем только пиксели ---
                lower_name = self.image.name.lower()
                if lower_name.endswith(('.heic', '.heif')):
                    # Извлекаем координаты из исходного HEIC
                    lat, lon = extract_gps_from_heif(file_bytes)
                    if lat is not None and lon is not None:
                        self.latitude = lat
                        self.longitude = lon
                    # Конвертируем в JPEG для отображения (без сохранения EXIF)
                    try:
                        img_heic = Image.open(io.BytesIO(file_bytes))
                        buf = io.BytesIO()
                        img_heic.save(buf, format='JPEG', quality=92)
                        buf.seek(0)
                        new_name = os.path.splitext(self.image.name)[0] + '.jpg'
                        self.image = SimpleUploadedFile(new_name, buf.read(), content_type='image/jpeg')
                        self.image.seek(0)
                        file_bytes = self.image.read()
                        self.image.seek(0)
                    except Exception as e:
                        print(f"Ошибка конвертации HEIC в JPEG: {e}")

                # --- 2. Побайтовый хэш всего файла (теперь JPEG) ---
                self.file_hash = hashlib.sha256(file_bytes).hexdigest()

                # --- 3. Открываем изображение Pillow ---
                img = Image.open(io.BytesIO(file_bytes))

                # --- 4. Пиксельный хэш ---
                with io.BytesIO() as out:
                    img.save(out, format='BMP')
                    pixel_bytes = out.getvalue()
                self.pixel_hash = hashlib.sha256(pixel_bytes).hexdigest()

                # --- 5. Проверка на дубликат ---
                if self.user and self.pixel_hash:
                    if Photo.objects.filter(user=self.user, pixel_hash=self.pixel_hash).exclude(pk=self.pk).exists():
                        raise ValidationError('Вы уже загружали такое фото (визуально идентичное).')

                # --- 6. EXIF для не-HEIC (для JPEG и др.) ---
                if not lower_name.endswith(('.heic', '.heif')):
                    exif = get_exif_data(img, file_bytes)
                    if exif:
                        lat, lon = extract_gps(exif)
                        if lat is not None and lon is not None:
                            self.latitude = lat
                            self.longitude = lon
                        taken = extract_datetime(exif)
                        if taken:
                            self.taken_at = taken
                        # Сохраняем сырые EXIF
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
                else:
                    # Для HEIC EXIF уже извлечён, можно сохранить пустой или только GPS
                    self.exif_raw = {}

            except ValidationError:
                raise
            except Exception:
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
    
    def delete(self, *args, **kwargs):
        # Удаляем файл изображения с диска, если он есть
        if self.image:
            storage, path = self.image.storage, self.image.name
            storage.delete(path)
        # Затем вызываем стандартное удаление, чтобы запись исчезла из БД
        super().delete(*args, **kwargs)