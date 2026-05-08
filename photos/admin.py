from django.contrib import admin
from .models import Photo

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('id', 'image', 'latitude', 'longitude', 'taken_at', 'uploaded_at')
    readonly_fields = ('latitude', 'longitude', 'taken_at', 'weather_data', 'exif_raw', 'uploaded_at')