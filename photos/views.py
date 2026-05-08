import json
from django.shortcuts import render
from .models import Photo

def photo_list(request):
    photos = Photo.objects.all()
    photos_data = []          # переименовали, чтобы не путать со строкой
    for photo in photos:
        photos_data.append({
            'id': photo.id,
            'latitude': photo.latitude,
            'longitude': photo.longitude,
            'image_url': photo.image.url if photo.image else '',
        })
    # Передаём список словарей напрямую — json_script сам превратит его в JSON
    return render(request, 'photos/photo_list.html', {
        'photos_json': photos_data
    })
