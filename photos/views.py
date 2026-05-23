import requests

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.views.decorators.http import require_POST

from .forms import PhotoEditForm
from .models import Photo
from .weather import fetch_weather_for_photo


@login_required
def upload_photo(request):
    if request.method == "POST":
        image_files = request.FILES.getlist("image")
        if not image_files:
            messages.error(request, "Пожалуйста, выберите хотя бы один файл.")
            return render(request, "photos/upload.html")

        success_count = 0
        has_errors = False
        for image_file in image_files:
            photo = Photo(image=image_file)
            photo.user = request.user
            try:
                photo.save()

                if photo.latitude is None or photo.longitude is None:
                    messages.warning(
                        request,
                        f'{image_file.name} загружен, но не отображается на карте (нет геоданных).'
                    )
                else:
                    messages.success(request, f'{image_file.name} загружен.')

                success_count += 1
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, f'{image_file.name}: {error}')

        if success_count:
            messages.success(request, f"Загружено {success_count} фото.")
        if has_errors:
            # Если были ошибки, остаёмся на странице загрузки, чтобы пользователь увидел сообщения
            return render(request, "photos/upload.html")
        else:
            # Всё хорошо — идём на карту
            return redirect("photo_list")

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
    # Вся логика по сбору данных теперь в photos_geojson, а здесь просто рендерим шаблон
    return render(request, 'photos/photo_list.html')

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
def photos_geojson(request):
    """Возвращает все фото текущего пользователя в формате GeoJSON."""
    photos = Photo.objects.filter(user=request.user)
    exclude_photo_id = request.GET.get("exclude")
    if exclude_photo_id:
        photos = photos.exclude(pk=exclude_photo_id)

    features = []
    for photo in photos:
        if photo.latitude is None or photo.longitude is None:
            continue

        w = photo.weather_data or {}
        temp_max = w.get('temperature_max')
        temp_min = w.get('temperature_min')
        precip = w.get('precipitation')
        weathercode = w.get('weathercode')

        weather_parts = []
        weather_emoji = get_weather_emoji(weathercode) if weathercode is not None else ""
        if weather_emoji:
            weather_parts.append(weather_emoji)
        if temp_max is not None:
            weather_parts.append(f"Макс {temp_max}°C")
        if temp_min is not None:
            weather_parts.append(f"Мин {temp_min}°C")
        if precip is not None and precip > 0:
            weather_parts.append(f"Осадки {precip} мм")
        weather_str = " · ".join(weather_parts) if weather_parts else "Нет данных"

        taken = photo.taken_at or photo.uploaded_at
        date_str = taken.strftime("%d.%m.%Y %H:%M") if taken else "Неизвестно"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [photo.longitude, photo.latitude]  # Внимание: долгота, широта!
            },
            "properties": {
                "id": photo.id,
                "date": date_str,
                "weather": weather_str,
                "image_url": photo.image.url if photo.image else "",
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    return JsonResponse(geojson)

@login_required
def delete_photo(request, photo_id):
    photo = get_object_or_404(Photo, pk=photo_id)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Проверка, что пользователь — владелец
    if photo.user != request.user:
        if is_ajax:
            return JsonResponse(
                {"success": False, "error": "У вас нет прав на удаление этого фото"},
                status=403,
            )

        messages.error(request, "У вас нет прав на удаление этого фото.")
        return redirect("user_photos")

    if request.method == "POST":
        photo.delete()

        if is_ajax:
            return JsonResponse({
                "success": True,
                "photo_id": photo_id,
            })

        messages.success(request, "Фото удалено.")
        return redirect("user_photos")

    if is_ajax:
        return JsonResponse(
            {"success": False, "error": "Метод не разрешён"},
            status=405,
        )

    messages.error(request, "Метод не разрешён.")
    return redirect("user_photos")
    
@login_required
def user_photos(request):
    active_status = request.GET.get("status", "all")
    base_photos = Photo.objects.filter(user=request.user)
    photos = base_photos.order_by("-uploaded_at")

    filter_counts = {
        "all": base_photos.count(),
        "on_map": base_photos.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        ).count(),
        "no_geo": base_photos.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True),
        ).count(),
        "no_date": base_photos.filter(taken_at__isnull=True).count(),
        "no_weather": base_photos.filter(weather_data__isnull=True).count(),
    }

    if active_status == "on_map":
        photos = photos.filter(latitude__isnull=False, longitude__isnull=False)
    elif active_status == "no_geo":
        photos = photos.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
    elif active_status == "no_date":
        photos = photos.filter(taken_at__isnull=True)
    elif active_status == "no_weather":
        photos = photos.filter(weather_data__isnull=True)
    else:
        active_status = "all"

    return render(
        request,
        "photos/user_photos.html",
        {
            "photos": photos,
            "active_status": active_status,
            "filter_counts": filter_counts,
        },
    )


@login_required
@require_POST
def refresh_weather(request, photo_id):
    photo = get_object_or_404(Photo, pk=photo_id, user=request.user)

    if (
        photo.latitude is None
        or photo.longitude is None
        or photo.taken_at is None
    ):
        messages.warning(
            request,
            "Для обновления погоды нужны координаты и дата съёмки.",
        )
        return redirect("user_photos")

    result = fetch_weather_for_photo(
        photo.latitude,
        photo.longitude,
        photo.taken_at,
    )

    if result is not None:
        photo.weather_data = result
        photo.save(update_fields=["weather_data"])
        messages.success(request, "Погода обновлена.")
    else:
        messages.warning(request, "Не удалось получить погоду. Попробуйте позже.")

    return redirect("user_photos")


@login_required
def edit_photo(request, photo_id):
    photo = get_object_or_404(Photo, pk=photo_id, user=request.user)

    if request.method == "POST":
        form = PhotoEditForm(request.POST, instance=photo)

        if form.is_valid():
            photo = form.save(commit=False)

            if (
                photo.latitude is not None
                and photo.longitude is not None
                and photo.taken_at is not None
            ):
                photo.weather_data = fetch_weather_for_photo(
                    photo.latitude,
                    photo.longitude,
                    photo.taken_at,
                )
                messages.success(request, "Фото сохранено, погода обновлена.")
            else:
                if photo.latitude is None or photo.longitude is None:
                    photo.weather_data = None
                    messages.warning(
                        request,
                        "Фото сохранено, но без координат оно не появится на карте.",
                    )
                else:
                    messages.warning(
                        request,
                        "Фото сохранено, но без даты съёмки погоду обновить нельзя.",
                    )

            photo.save()
            return redirect("user_photos")
    else:
        form = PhotoEditForm(instance=photo)

    return render(
        request,
        "photos/edit_photo.html",
        {
            "form": form,
            "photo": photo,
        },
    )
