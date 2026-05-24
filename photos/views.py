from datetime import datetime

import requests

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.views.decorators.http import require_POST

from .forms import PhotoEditForm
from .climate import fetch_climate_comparison_for_photo
from .models import Photo
from .weather import fetch_weather_for_photo
from .weather_codes import get_weather_info


def format_weather_time(weather_time):
    if not weather_time:
        return None

    try:
        return datetime.strptime(weather_time, "%Y-%m-%dT%H:%M").strftime("%d.%m.%Y, %H:%M")
    except (TypeError, ValueError):
        return weather_time


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
        weather_info = get_weather_info(w.get("weathercode"))
        weather_source = None
        weather_temperature = None
        weather_temperature_max = None
        weather_temperature_min = None
        weather_precipitation = None
        weather_time = None

        if w.get("source") == "hourly":
            weather_source = "hourly"
            weather_temperature = w.get("temperature")
            weather_precipitation = w.get("precipitation")
            weather_time = w.get("weather_time")
        elif w:
            weather_source = "daily"
            weather_temperature_max = w.get("temperature_max")
            weather_temperature_min = w.get("temperature_min")
            weather_precipitation = w.get("precipitation")

        weather_parts = [f"{weather_info['emoji']} {weather_info['label']}"]
        if weather_source == "hourly" and weather_temperature is not None:
            weather_parts.append(f"{weather_temperature}°C")
        elif weather_source == "daily":
            if weather_temperature_max is not None:
                weather_parts.append(f"Макс {weather_temperature_max}°C")
            if weather_temperature_min is not None:
                weather_parts.append(f"Мин {weather_temperature_min}°C")
        if weather_precipitation is not None:
            weather_parts.append(f"Осадки {weather_precipitation} мм")
        weather_str = " · ".join(weather_parts) if w else "Нет данных"

        taken = photo.taken_at or photo.uploaded_at
        date_str = taken.strftime("%d.%m.%Y %H:%M") if taken else "Неизвестно"
        climate_data = photo.climate_data or {}

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
                "weather_emoji": weather_info["emoji"],
                "weather_label": weather_info["label"],
                "weather_css_class": weather_info["css_class"],
                "weather_source": weather_source,
                "weather_temperature": weather_temperature,
                "weather_temperature_max": weather_temperature_max,
                "weather_temperature_min": weather_temperature_min,
                "weather_precipitation": weather_precipitation,
                "weather_time": weather_time,
                "weather_time_display": format_weather_time(weather_time),
                "climate_normal_temperature": climate_data.get("normal_temperature"),
                "climate_temperature_anomaly": climate_data.get("temperature_anomaly"),
                "climate_comparison_text": climate_data.get("comparison_text"),
                "climate_source": climate_data.get("source"),
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

    for photo in photos:
        weather_data = photo.weather_data or {}
        photo.weather_info = get_weather_info(weather_data.get("weathercode"))
        photo.weather_time_display = format_weather_time(weather_data.get("weather_time"))

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
@require_POST
def calculate_climate_norm(request, photo_id):
    photo = get_object_or_404(Photo, pk=photo_id, user=request.user)

    if (
        photo.latitude is None
        or photo.longitude is None
        or photo.taken_at is None
        or not photo.weather_data
    ):
        messages.warning(
            request,
            "Для расчёта нормы нужны координаты, дата и погода.",
        )
        return redirect("user_photos")

    result = fetch_climate_comparison_for_photo(photo)
    if result is not None:
        photo.climate_data = result
        photo.save(update_fields=["climate_data"])
        messages.success(request, "Климатическая норма рассчитана.")
    else:
        messages.warning(
            request,
            "Не удалось рассчитать климатическую норму. Попробуйте позже.",
        )

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
