import plotly.express as px

color_sequences = dict(
    light_blue=px.colors.sequential.Blues[1:3],
    dark_blue=px.colors.sequential.Blues[3:-2] + px.colors.sequential.Teal[2::2],
    # mint = ,
    green=px.colors.sequential.Greens[2::2] + px.colors.sequential.Tealgrn[::2],
    brown=px.colors.sequential.Oranges,
    grey=px.colors.sequential.Greys,
)


def get_color(generation_type: str, color_sequences_cp: dict[str, list[str]]) -> str:
    color_map = {
        "brown": "saddlebrown",
        "hard": "black",
        "fossil": "brown",
        "hydro": "dark_blue",
        "onshore": "rgb(222,235,247)",
        "offshore": "rgb(158,202,225)",
        "wind": "light_blue",
        "waste": "purple",
        "solar": "gold",
        "geo": "green",
        "renewable": "green",
        "biomass": "#1B8A85",
    }
    try:
        color = [
            val for key, val in color_map.items() if key in generation_type.lower()
        ][0]
    except IndexError:
        color = "grey"

    if color in color_sequences_cp.keys() and len(color_sequences_cp[color]) > 0:
        mid = len(color_sequences_cp[color]) // 2
        return color_sequences_cp[color].pop(mid)

    return color


def get_iso_alpha(country_code):
    # https://en.wikipedia.org/wiki/ISO_3166-1_alpha-3
    country_code_iso_mapping = {
        "DE": "DEU",
        "AL": "ALB",
        "AT": "AUT",
        "BY": "BLR",
        "BE": "BEL",
        "BA": "BIH",
        "BG": "BGR",
        "CZ": "CZE",
        "HR": "",
        "CWE": "",
        "CY": "",
        "LU": "LUX",
        "DK": "DNK",
        "EE": "",
        "FI": "FIN",
        "MK": "",
        "FR": "FRA",
        "GR": "",
        "HU": "",
        "IS": "",
        "IE": "",
        "IT": "ITA",
        "KGD": "",
        "LV": "",
        "LT": "",
        "MT": "",
        "ME": "",
        "GB": "",
        "UK": "",
        "NL": "",
        "NO": "NOR",
        "PL": "POL",
        "PT": "",
        "MD": "",
        "RO": "",
        "RU": "RUS",
        "SE": "SEW",
        "RS": "",
        "SK": "SVN",
        "SI": "",
        "NIR": "IRL",
        "ES": "ESP",
        "CH": "",
        "TR": "",
        "UA": "",
        "XK": "",
    }
    return country_code_iso_mapping.get(country_code, None)
