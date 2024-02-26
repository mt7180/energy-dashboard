import plotly.express as px

color_sequences = dict(
    light_blue=px.colors.sequential.Blues[1:3],
    dark_blue=px.colors.sequential.Blues[3:-2] + px.colors.sequential.Teal[2::2],
    # mint = ,
    green=px.colors.sequential.Greens[2::2] + px.colors.sequential.Tealgrn[::2],
    brown=px.colors.sequential.Oranges,
    grey=px.colors.sequential.Greys,
)


def get_color(generation_type: str, color_sequences_cp: dict[str, list[dict]]) -> str:
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
    except:
        color = "grey"

    if color in color_sequences_cp.keys() and len(color_sequences_cp[color]) > 0:
        mid = len(color_sequences_cp[color]) // 2
        return color_sequences_cp[color].pop(mid)

    return color
