from datetime import date, datetime

import requests


ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MIN_HISTORY_VALUES = 3
HISTORY_YEARS = 5
REQUEST_TIMEOUT = 10


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_photo_temperature(weather_data):
    if not weather_data:
        return None

    if weather_data.get("source") == "hourly":
        return _to_float(weather_data.get("temperature"))

    temperature_max = _to_float(weather_data.get("temperature_max"))
    temperature_min = _to_float(weather_data.get("temperature_min"))
    if temperature_max is None or temperature_min is None:
        return None

    return (temperature_max + temperature_min) / 2


def _historical_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _fetch_temperature_for_day(latitude, longitude, target_date, target_hour):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
        "hourly": "temperature_2m",
        "timezone": "auto",
    }

    try:
        response = requests.get(ARCHIVE_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    temperatures = hourly.get("temperature_2m") or []
    if not times or not temperatures:
        return None

    target_dt = datetime.combine(target_date, datetime.min.time()).replace(
        hour=target_hour
    )

    try:
        nearest_index = min(
            range(min(len(times), len(temperatures))),
            key=lambda index: abs(datetime.fromisoformat(times[index]) - target_dt),
        )
    except ValueError:
        return None

    return _to_float(temperatures[nearest_index])


def _build_comparison_text(anomaly):
    if anomaly >= 1.0:
        return "теплее обычного", f"На {anomaly:.1f} °C теплее обычного"
    if anomaly <= -1.0:
        return "холоднее обычного", f"На {abs(anomaly):.1f} °C холоднее обычного"
    return "примерно как обычно", "Примерно как обычно"


def fetch_climate_comparison_for_photo(photo):
    if (
        photo.latitude is None
        or photo.longitude is None
        or photo.taken_at is None
        or not photo.weather_data
    ):
        return None

    photo_temperature = _get_photo_temperature(photo.weather_data)
    if photo_temperature is None:
        return None

    taken_at = photo.taken_at
    target_month = taken_at.month
    target_day = taken_at.day
    target_hour = taken_at.hour

    history_values = []
    years_used = []

    start_year = taken_at.year - HISTORY_YEARS
    end_year = taken_at.year
    for year in range(start_year, end_year):
        target_date = _historical_date(year, target_month, target_day)
        if target_date is None:
            continue

        temperature = _fetch_temperature_for_day(
            photo.latitude,
            photo.longitude,
            target_date,
            target_hour,
        )
        if temperature is None:
            continue

        history_values.append(temperature)
        years_used.append(year)

    if len(history_values) < MIN_HISTORY_VALUES:
        return None

    normal_temperature = round(sum(history_values) / len(history_values), 1)
    rounded_photo_temperature = round(photo_temperature, 1)
    anomaly = round(rounded_photo_temperature - normal_temperature, 1)
    label, text = _build_comparison_text(anomaly)

    return {
        "source": "hourly_climate_mvp",
        "years_used": years_used,
        "normal_temperature": normal_temperature,
        "photo_temperature": rounded_photo_temperature,
        "temperature_anomaly": anomaly,
        "comparison_label": label,
        "comparison_text": text,
        "target_month_day": f"{target_month:02d}-{target_day:02d}",
        "target_hour": target_hour,
    }
