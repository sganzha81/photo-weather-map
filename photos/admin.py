import os

from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils.html import format_html

from .file_utils import format_file_size
from .models import Photo, SiteSettings


class HasGeoFilter(admin.SimpleListFilter):
    title = "геоданные"
    parameter_name = "has_geo"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Да"),
            ("no", "Нет"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(latitude__isnull=False, longitude__isnull=False)
        if self.value() == "no":
            return queryset.filter(latitude__isnull=True) | queryset.filter(
                longitude__isnull=True
            )
        return queryset


class HasWeatherFilter(admin.SimpleListFilter):
    title = "погода"
    parameter_name = "has_weather"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Да"),
            ("no", "Нет"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(weather_data__isnull=False)
        if self.value() == "no":
            return queryset.filter(weather_data__isnull=True)
        return queryset


class HasClimateFilter(admin.SimpleListFilter):
    title = "климатическая норма"
    parameter_name = "has_climate"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Да"),
            ("no", "Нет"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(climate_data__isnull=False)
        if self.value() == "no":
            return queryset.filter(climate_data__isnull=True)
        return queryset


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "thumbnail",
        "user",
        "short_filename",
        "file_size_display",
        "uploaded_at",
        "taken_at",
        "has_geo",
        "has_weather",
        "has_climate",
    )
    list_filter = (
        "uploaded_at",
        "taken_at",
        "user",
        HasGeoFilter,
        HasWeatherFilter,
        HasClimateFilter,
    )
    search_fields = ("image", "user__username", "user__email")
    readonly_fields = (
        "preview",
        "file_hash",
        "pixel_hash",
        "file_size",
        "file_size_display",
        "uploaded_at",
        "weather_data",
        "climate_data",
        "exif_raw",
    )
    ordering = ("-uploaded_at",)

    @admin.display(description="Превью")
    def thumbnail(self, obj):
        return self._image_tag(obj, width=80)

    @admin.display(description="Превью")
    def preview(self, obj):
        return self._image_tag(obj, width=240)

    def _image_tag(self, obj, width):
        try:
            if not obj.image:
                return "—"
            return format_html(
                '<img src="{}" style="width: {}px; height: auto; max-height: {}px; object-fit: contain;" />',
                obj.image.url,
                width,
                width,
            )
        except Exception:
            return "—"

    @admin.display(description="Файл")
    def short_filename(self, obj):
        if not obj.image:
            return "—"
        return os.path.basename(obj.image.name)

    @admin.display(description="Размер файла", ordering="file_size")
    def file_size_display(self, obj):
        return format_file_size(obj.file_size)

    @admin.display(boolean=True, description="Гео")
    def has_geo(self, obj):
        return obj.latitude is not None and obj.longitude is not None

    @admin.display(boolean=True, description="Погода")
    def has_weather(self, obj):
        return bool(obj.weather_data)

    @admin.display(boolean=True, description="Норма")
    def has_climate(self, obj):
        return bool(obj.climate_data)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("user_storage_limit_mb", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)


try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = BaseUserAdmin.list_display + (
        "photo_count",
        "total_photo_size_display",
    )

    @admin.display(description="Фото")
    def photo_count(self, obj):
        return obj.photo_set.count()

    @admin.display(description="Размер фото")
    def total_photo_size_display(self, obj):
        total_size = obj.photo_set.aggregate(total=Sum("file_size"))["total"]
        return format_file_size(total_size or 0)
