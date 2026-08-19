"""Weather condition codes, normalised across providers.

Both providers get mapped onto the same small set of groups, so the UI and the
recommender never need to know which service the data came from.

Groups: clear, cloud, rain, snow, storm, fog
"""

# WMO codes used by Open-Meteo.
WMO = {
    0: ("Clear", "clear"), 1: ("Mainly clear", "clear"), 2: ("Partly cloudy", "cloud"),
    3: ("Overcast", "cloud"), 45: ("Fog", "fog"), 48: ("Rime fog", "fog"),
    51: ("Light drizzle", "rain"), 53: ("Drizzle", "rain"), 55: ("Heavy drizzle", "rain"),
    56: ("Freezing drizzle", "rain"), 57: ("Freezing drizzle", "rain"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"), 80: ("Light showers", "rain"), 81: ("Showers", "rain"),
    82: ("Violent showers", "rain"), 85: ("Snow showers", "snow"), 86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "storm"), 96: ("Thunderstorm with hail", "storm"),
    99: ("Thunderstorm with hail", "storm"),
}

# Met Office "significantWeatherCode". Day and night variants collapse to the
# same label, since the app only cares what to wear.
METOFFICE = {
    -1: ("Not available", "cloud"),
    0: ("Clear", "clear"), 1: ("Sunny", "clear"),
    2: ("Partly cloudy", "cloud"), 3: ("Partly cloudy", "cloud"),
    4: ("Not available", "cloud"),
    5: ("Mist", "fog"), 6: ("Fog", "fog"),
    7: ("Cloudy", "cloud"), 8: ("Overcast", "cloud"),
    9: ("Light rain shower", "rain"), 10: ("Light rain shower", "rain"),
    11: ("Drizzle", "rain"), 12: ("Light rain", "rain"),
    13: ("Heavy rain shower", "rain"), 14: ("Heavy rain shower", "rain"),
    15: ("Heavy rain", "rain"),
    16: ("Sleet shower", "snow"), 17: ("Sleet shower", "snow"), 18: ("Sleet", "snow"),
    19: ("Hail shower", "storm"), 20: ("Hail shower", "storm"), 21: ("Hail", "storm"),
    22: ("Light snow shower", "snow"), 23: ("Light snow shower", "snow"),
    24: ("Light snow", "snow"),
    25: ("Heavy snow shower", "snow"), 26: ("Heavy snow shower", "snow"),
    27: ("Heavy snow", "snow"),
    28: ("Thunder shower", "storm"), 29: ("Thunder shower", "storm"),
    30: ("Thunder", "storm"),
}


def describe(code, table=None) -> dict:
    """Normalise a provider code into {code, label, group}."""
    table = table or WMO
    try:
        key = int(code)
    except (TypeError, ValueError):
        return {"code": code, "label": "Unknown", "group": "cloud"}
    label, group = table.get(key, ("Unknown", "cloud"))
    return {"code": key, "label": label, "group": group}
