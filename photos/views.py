import json
from django.shortcuts import render
from .models import Photo


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


def photo_list(request):
    photos = Photo.objects.all()
    photos_data = []
    for photo in photos:
        w = photo.weather_data or {}
        temp = w.get("temperature_max")
        temp_str = f"{temp}°C" if temp is not None else ""
        icon_desc = (
            get_weather_emoji(w.get("weathercode"))
            if w.get("weathercode") is not None
            else ""
        )
        photos_data.append(
            {
                "id": photo.id,
                "latitude": photo.latitude,
                "longitude": photo.longitude,
                "image_url": photo.image.url if photo.image else "",
                "temp_str": temp_str,
                "icon_desc": icon_desc,
            }
        )
    return render(request, "photos/photo_list.html", {"photos_json": photos_data})
