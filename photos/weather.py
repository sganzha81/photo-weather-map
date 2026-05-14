import requests
from datetime import datetime, timezone

def fetch_weather_for_photo(latitude, longitude, taken_at):
    """
    Принимает широту, долготу и datetime съёмки.
    Возвращает словарь с погодными данными или None при ошибке.
    """
    if latitude is None or longitude is None or taken_at is None:
        return None

    # Open-Meteo ожидает дату в формате 'YYYY-MM-DD'
    date_str = taken_at.strftime('%Y-%m-%d')

    url = 'https://archive-api.open-meteo.com/v1/archive'
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'start_date': date_str,
        'end_date': date_str,
        'daily': [
            'temperature_2m_max',
            'temperature_2m_min',
            'precipitation_sum',
            'weathercode'
        ],
        'timezone': 'auto'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        print("Open-Meteo response:", data)
        
        daily = data.get('daily', {})

        # Извлекаем значения (они приходят списками, берём первый элемент)
        max_temp = daily.get('temperature_2m_max', [None])[0]
        min_temp = daily.get('temperature_2m_min', [None])[0]
        precip = daily.get('precipitation_sum', [None])[0]
        weathercode = daily.get('weathercode', [None])[0]

        return {
            'temperature_max': max_temp,
            'temperature_min': min_temp,
            'precipitation': precip,
            'weathercode': weathercode
        }
    except requests.RequestException as e:
        # В реальном проекте лучше логировать ошибки
        print(f'Ошибка запроса погоды: {e}')
        return None