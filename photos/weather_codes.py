def get_weather_info(code):
    mapping = {
        0: {"emoji": "☀️", "label": "Ясно", "css_class": "clear"},
        1: {"emoji": "🌤️", "label": "Переменная облачность", "css_class": "partly-cloudy"},
        2: {"emoji": "🌤️", "label": "Переменная облачность", "css_class": "partly-cloudy"},
        3: {"emoji": "☁️", "label": "Пасмурно", "css_class": "overcast"},
        45: {"emoji": "🌫️", "label": "Туман", "css_class": "fog"},
        48: {"emoji": "🌫️", "label": "Туман", "css_class": "fog"},
        51: {"emoji": "🌦️", "label": "Морось", "css_class": "drizzle"},
        53: {"emoji": "🌦️", "label": "Морось", "css_class": "drizzle"},
        55: {"emoji": "🌦️", "label": "Морось", "css_class": "drizzle"},
        56: {"emoji": "🌧️", "label": "Ледяная морось", "css_class": "freezing-drizzle"},
        57: {"emoji": "🌧️", "label": "Ледяная морось", "css_class": "freezing-drizzle"},
        61: {"emoji": "🌧️", "label": "Дождь", "css_class": "rain"},
        63: {"emoji": "🌧️", "label": "Дождь", "css_class": "rain"},
        65: {"emoji": "🌧️", "label": "Дождь", "css_class": "rain"},
        66: {"emoji": "🌧️", "label": "Ледяной дождь", "css_class": "freezing-rain"},
        67: {"emoji": "🌧️", "label": "Ледяной дождь", "css_class": "freezing-rain"},
        71: {"emoji": "❄️", "label": "Снег", "css_class": "snow"},
        73: {"emoji": "❄️", "label": "Снег", "css_class": "snow"},
        75: {"emoji": "❄️", "label": "Снег", "css_class": "snow"},
        77: {"emoji": "🌨️", "label": "Снежные зёрна", "css_class": "snow-grains"},
        80: {"emoji": "🌦️", "label": "Ливень", "css_class": "showers"},
        81: {"emoji": "🌦️", "label": "Ливень", "css_class": "showers"},
        82: {"emoji": "🌦️", "label": "Ливень", "css_class": "showers"},
        85: {"emoji": "🌨️", "label": "Снегопад", "css_class": "snow-showers"},
        86: {"emoji": "🌨️", "label": "Снегопад", "css_class": "snow-showers"},
        95: {"emoji": "⛈️", "label": "Гроза", "css_class": "thunderstorm"},
        96: {"emoji": "⛈️", "label": "Гроза с градом", "css_class": "thunderstorm-hail"},
        99: {"emoji": "⛈️", "label": "Гроза с градом", "css_class": "thunderstorm-hail"},
    }

    try:
        normalized_code = int(code)
    except (TypeError, ValueError):
        normalized_code = None

    return mapping.get(
        normalized_code,
        {"emoji": "🌡️", "label": "Нет данных", "css_class": "unknown"},
    )
