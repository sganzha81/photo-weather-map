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

EXIF_IFD_TAG = 34665
GPS_IFD_TAG = 34853

pillow_heif.register_heif_opener()

from fractions import Fraction
import piexif


def is_jpeg_file(file_bytes):
    """Проверяет JPEG по сигнатуре файла."""
    return file_bytes.startswith(b"\xff\xd8")


def is_heif_file(file_bytes):
    """Проверяет HEIC/HEIF по ISO BMFF ftyp brand."""
    heif_brands = {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}
    return (
        len(file_bytes) >= 12
        and file_bytes[4:8] == b"ftyp"
        and file_bytes[8:12] in heif_brands
    )


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


def rational_to_float(value):
    """
    Преобразует EXIF-значение в float.

    В EXIF числа могут приходить в разных форматах:
    - обычное число: 37
    - дробь: (37, 1)
    - объект Pillow IFDRational, который уже умеет превращаться в float
    """

    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value

        if denominator == 0:
            return 0.0

        return float(numerator) / float(denominator)

    return float(value)


def dms_to_decimal(dms, ref):
    """
    Переводит координаты из EXIF-формата:
    градусы / минуты / секунды
    в обычные десятичные координаты.
    """

    if not dms or len(dms) != 3:
        return None

    if isinstance(ref, bytes):
        ref = ref.decode("ascii", errors="ignore")

    ref = str(ref).strip().upper()

    degrees, minutes, seconds = dms

    decimal = (
        rational_to_float(degrees)
        + rational_to_float(minutes) / 60
        + rational_to_float(seconds) / 3600
    )

    if ref in ["S", "W"]:
        decimal = -decimal

    return decimal

    if isinstance(ref, bytes):
        ref = ref.decode("ascii", errors="ignore")

    ref = str(ref).strip().upper()

    degrees, minutes, seconds = dms

    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600

    if ref in ["S", "W"]:
        decimal = -decimal

    return decimal


def extract_gps(exif_data):
    """Вытаскивает широту и долготу из GPSInfo, если есть."""
    gps_info = exif_data.get("GPSInfo")

    if not isinstance(gps_info, dict):
        return None, None

    lat_dms = gps_info.get("GPSLatitude")
    lat_ref = gps_info.get("GPSLatitudeRef")
    lon_dms = gps_info.get("GPSLongitude")
    lon_ref = gps_info.get("GPSLongitudeRef")

    if not all([lat_dms, lat_ref, lon_dms, lon_ref]):
        return None, None

    try:
        lat = dms_to_decimal(lat_dms, lat_ref)
        lon = dms_to_decimal(lon_dms, lon_ref)
        return lat, lon
    except Exception as e:
        print(f"Ошибка преобразования GPS: {e}")
        return None, None


def validate_image_size(image):
    max_size_mb = 10
    if image.size > max_size_mb * 1024 * 1024:
        raise ValidationError(
            f"Файл слишком большой! Максимальный размер: {max_size_mb} МБ."
        )


def get_exif_data(image, file_bytes=None):
    """
    Извлекает EXIF из изображения.

    Важный момент:
    GPSInfo в JPEG часто лежит не как обычный словарь,
    а во вложенном IFD-блоке. Поэтому достаём GPS отдельно
    через exif.get_ifd(34853).
    """
    exif_dict = {}

    try:
        exif = image.getexif()
    except Exception as e:
        print(f"Ошибка image.getexif(): {e}")
        return exif_dict

    if not exif:
        return exif_dict

    # 1. Обычные EXIF-теги
    for tag_id, value in exif.items():
        tag_name = TAGS.get(tag_id, tag_id)

        # GPSInfo обработаем отдельно ниже
        if tag_id == GPS_IFD_TAG or tag_name == "GPSInfo":
            continue

        # ExifOffset обработаем отдельно ниже
        if tag_id == EXIF_IFD_TAG:
            continue

        exif_dict[tag_name] = value

    # 2. Вложенный EXIF IFD — там часто лежит DateTimeOriginal
    try:
        exif_ifd = exif.get_ifd(EXIF_IFD_TAG)
        for tag_id, value in exif_ifd.items():
            tag_name = TAGS.get(tag_id, tag_id)
            exif_dict[tag_name] = value
    except Exception as e:
        print(f"Не удалось прочитать EXIF IFD: {e}")

    # 3. Вложенный GPS IFD — там лежат координаты
    try:
        gps_ifd = exif.get_ifd(GPS_IFD_TAG)
        gps_data = {}

        for gps_tag_id, gps_value in gps_ifd.items():
            gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
            gps_data[gps_tag_name] = gps_value

        if gps_data:
            exif_dict["GPSInfo"] = gps_data

    except Exception as e:
        print(f"Не удалось прочитать GPS IFD: {e}")

    return exif_dict


def extract_metadata_from_heif(file_bytes):
    """
    Извлекает из HEIC:
    - latitude
    - longitude
    - taken_at

    Используем pillow_heif, чтобы достать EXIF-байты,
    и piexif, чтобы распарсить GPS и дату.
    """
    try:
        heif_file = pillow_heif.open_heif(io.BytesIO(file_bytes))
        exif_bytes = heif_file.info.get("exif")

        if not exif_bytes:
            return None, None, None

        normalized_exif = _normalize_heic_exif_bytes(exif_bytes)
        exif_dict = piexif.load(normalized_exif)

        # --- GPS ---
        gps = exif_dict.get("GPS") or {}

        lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef)
        lat_dms = gps.get(piexif.GPSIFD.GPSLatitude)
        lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef)
        lon_dms = gps.get(piexif.GPSIFD.GPSLongitude)

        latitude = None
        longitude = None

        if lat_ref and lat_dms and lon_ref and lon_dms:
            latitude = dms_to_decimal(lat_dms, lat_ref)
            longitude = dms_to_decimal(lon_dms, lon_ref)

        # --- DateTimeOriginal ---
        taken_at = None

        exif_part = exif_dict.get("Exif") or {}
        zeroth_part = exif_dict.get("0th") or {}

        date_value = (
            exif_part.get(piexif.ExifIFD.DateTimeOriginal)
            or exif_part.get(piexif.ExifIFD.DateTimeDigitized)
            or zeroth_part.get(piexif.ImageIFD.DateTime)
        )

        if isinstance(date_value, bytes):
            date_value = date_value.decode("utf-8", errors="ignore")

        if date_value:
            try:
                taken_at = datetime.strptime(date_value, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                taken_at = None

        return latitude, longitude, taken_at

    except Exception as e:
        print(f"Ошибка извлечения метаданных из HEIC: {e}")
        return None, None, None


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
    file_hash = models.CharField(
        max_length=64, blank=True, null=True, verbose_name="Хэш файла"
    )
    pixel_hash = models.CharField(
        max_length=64, blank=True, null=True, verbose_name="Хэш пикселей"
    )
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
            validate_image_size(self.image)
            try:
                # --- 0. Читаем сырые байты ---
                self.image.seek(0)
                file_bytes = self.image.read()
                self.image.seek(0)

                lower_name = self.image.name.lower()
                file_looks_like_heif = is_heif_file(file_bytes)
                file_looks_like_jpeg = is_jpeg_file(file_bytes)

                # --- 1. Если файл HEIC – извлекаем GPS напрямую, конвертируем только пиксели ---
                if file_looks_like_heif:
                    # Извлекаем координаты из исходного HEIC
                    lat, lon, taken = extract_metadata_from_heif(file_bytes)

                    if lat is not None and lon is not None:
                        self.latitude = lat
                        self.longitude = lon

                    if taken:
                        self.taken_at = taken
                    # Конвертируем в JPEG для отображения (без сохранения EXIF)
                    try:
                        img_heic = Image.open(io.BytesIO(file_bytes))
                        buf = io.BytesIO()
                        img_heic.save(buf, format="JPEG", quality=92)
                        buf.seek(0)
                        new_name = os.path.splitext(self.image.name)[0] + ".jpg"
                        self.image = SimpleUploadedFile(
                            new_name, buf.read(), content_type="image/jpeg"
                        )
                        self.image.seek(0)
                        file_bytes = self.image.read()
                        self.image.seek(0)
                    except Exception as e:
                        print(f"Ошибка конвертации HEIC в JPEG: {e}")

                # --- 2. Побайтовый хэш всего файла (теперь JPEG) ---
                self.file_hash = hashlib.sha256(file_bytes).hexdigest()

                # --- 3. Открываем изображение Pillow ---
                img = Image.open(io.BytesIO(file_bytes))

                if file_looks_like_jpeg and lower_name.endswith((".heic", ".heif")):
                    new_name = os.path.splitext(self.image.name)[0] + ".jpg"
                    self.image.name = new_name

                # --- 4. Пиксельный хэш ---
                with io.BytesIO() as out:
                    img.save(out, format="BMP")
                    pixel_bytes = out.getvalue()
                self.pixel_hash = hashlib.sha256(pixel_bytes).hexdigest()

                # --- 5. Проверка на дубликат ---
                if self.user and self.pixel_hash:
                    if (
                        Photo.objects.filter(user=self.user, pixel_hash=self.pixel_hash)
                        .exclude(pk=self.pk)
                        .exists()
                    ):
                        raise ValidationError(
                            "Вы уже загружали такое фото (визуально идентичное)."
                        )

                # --- 6. EXIF для не-HEIC (для JPEG и др.) ---
                if not file_looks_like_heif:
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
            except Exception as e:
                print(f"Ошибка обработки фото: {type(e).__name__}: {e}")

    def save(self, *args, **kwargs):
        self.clean()

        if (
            self.latitude is not None
            and self.longitude is not None
            and self.taken_at is not None
            and not self.weather_data
        ):
            self.weather_data = fetch_weather_for_photo(
                self.latitude,
                self.longitude,
                self.taken_at,
            )

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
