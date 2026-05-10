import json
import requests

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from .models import Photo


@login_required
def upload_photo(request):
    if request.method == "POST":
        image_files = request.FILES.getlist("image")  # теперь список файлов
        if image_files:
            for image_file in image_files:
                photo = Photo(image=image_file)
                photo.user = request.user
                photo.save()
            messages.success(request, f"Загружено {len(image_files)} фото.")
            return redirect("photo_list")
        else:
            messages.error(request, "Пожалуйста, выберите хотя бы один файл.")
    return render(request, "photos/upload.html")


def get_weather_emoji(weathercode):
    """Возвращает строку с эмодзи и кратким описанием погоды по коду Open-Meteo."""
    mapping = {
        0: ("☀️", "Ясно"),
        1: ("🌤️", "Преимущественно ясно"),
        2: ("⛅", "Переменная облачность"),
        3: ("☁️", "Пасмурно"),
        45: ("🌫️", "Туман"),
        48: ("🌫️", "Изморозь"),
        51: ("🌦️", "Лёгкая морось"),
        53: ("🌧️", "Морось"),
        55: ("🌧️", "Сильная морось"),
        61: ("🌧️", "Слабый дождь"),
        63: ("🌧️", "Дождь"),
        65: ("🌧️", "Сильный дождь"),
        71: ("❄️", "Слабый снег"),
        73: ("❄️", "Снег"),
        75: ("❄️", "Сильный снег"),
        77: ("🌨️", "Снежные зёрна"),
        80: ("🌦️", "Кратковременный дождь"),
        81: ("🌧️", "Ливень"),
        82: ("🌧️", "Очень сильный ливень"),
        85: ("❄️", "Снегопад"),
        86: ("❄️", "Сильный снегопад"),
        95: ("⛈️", "Гроза"),
        96: ("⛈️", "Гроза с градом"),
        99: ("⛈️", "Сильная гроза с градом"),
    }
    emoji, desc = mapping.get(weathercode, ("🌈", "Неизвестно"))
    return f"{emoji} {desc}"


@login_required
def photo_list(request):
    photos = Photo.objects.filter(user=request.user)

    photos_data = []
    for photo in photos:
        w = photo.weather_data or {}
        temp_max = w.get("temperature_max")
        temp_min = w.get("temperature_min")
        precip = w.get("precipitation")
        weathercode = w.get("weathercode")
        # Получаем эмодзи + описание по коду погоды
        weather_emoji = (
            get_weather_emoji(weathercode) if weathercode is not None else ""
        )

        weather_parts = []
        if weather_emoji:
            weather_parts.append(weather_emoji)  # эмодзи идёт первым
        if temp_max is not None:
            weather_parts.append(f"Макс {temp_max}°C")
        if temp_min is not None:
            weather_parts.append(f"Мин {temp_min}°C")
        if precip is not None and precip > 0:
            weather_parts.append(f"Осадки {precip} мм")
        weather_str = " · ".join(weather_parts) if weather_parts else "Нет данных"

        # дата съёмки
        taken = photo.taken_at or photo.uploaded_at
        date_str = taken.strftime("%d.%m.%Y %H:%M") if taken else "Неизвестно"
        photos_data.append(
            {
                "id": photo.id,
                "latitude": photo.latitude,
                "longitude": photo.longitude,
                "image_url": photo.image.url if photo.image else "",
                "date": date_str,
                "weather": weather_str,
                "weathercode": weathercode,
            }
        )

    return render(request, "photos/photo_list.html", {"photos_json": photos_data})


def get_place_name(request):
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    if not lat or not lon:
        return JsonResponse({"error": "Неверные координаты"}, status=400)
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
            "zoom": 10,  # уровень детализации: 10 — район/город
            "accept-language": "ru",
        }
        headers = {
            "User-Agent": "PhotoWeatherMap/1.0 (sganzha@gmail.com)"
        }  # укажи свой email
        resp = requests.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        name = data.get("name", "")
        # часто поле 'name' содержит слишком мелкий объект, можно взять более крупный
        display_name = data.get("display_name", name)
        return JsonResponse({"name": name, "display_name": display_name})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def delete_photo(request, photo_id):
    photo = get_object_or_404(Photo, pk=photo_id)
    # Проверяем, что пользователь – владелец фото
    if photo.user != request.user:
        return JsonResponse(
            {"error": "У вас нет прав на удаление этого фото"}, status=403
        )
    if request.method == "POST":
        photo.delete()
        return JsonResponse({"status": "ok"})
    else:
        return JsonResponse({"error": "Метод не разрешён"}, status=405)
