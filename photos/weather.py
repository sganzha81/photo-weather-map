import logging

import requests
from datetime import datetime

logger = logging.getLogger(__name__)


def fetch_weather_for_photo(latitude, longitude, taken_at):
    """
    Принимает широту, долготу и datetime съёмки.
    Возвращает ближайшие к времени съёмки hourly-данные или None при ошибке.
    """
    if latitude is None or longitude is None or taken_at is None:
        return None

    date_str = taken_at.date().isoformat()

    url = 'https://archive-api.open-meteo.com/v1/archive'
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'start_date': date_str,
        'end_date': date_str,
        'hourly': 'temperature_2m,precipitation,weather_code',
        'timezone': 'auto'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        hourly = data.get('hourly', {})

        times = hourly.get('time') or []
        temperatures = hourly.get('temperature_2m') or []
        precipitations = hourly.get('precipitation') or []
        weather_codes = hourly.get('weather_code') or []

        if not times:
            return None

        taken_at_naive = taken_at.replace(tzinfo=None)
        nearest_index = min(
            range(len(times)),
            key=lambda index: abs(
                datetime.fromisoformat(times[index]) - taken_at_naive
            ),
        )

        return {
            'source': 'hourly',
            'temperature': temperatures[nearest_index],
            'precipitation': precipitations[nearest_index],
            'weathercode': weather_codes[nearest_index],
            'weather_time': times[nearest_index],
        }
    except (requests.RequestException, ValueError, IndexError) as e:
        logger.warning("Ошибка запроса погоды: %s", e)
        return None
