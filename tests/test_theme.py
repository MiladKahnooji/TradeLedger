from pathlib import Path

import tomllib

from app import THEME_PALETTES, chart_layout, plotly_template, pnl_color


def test_plotly_template_matches_selected_theme():
    assert plotly_template("Dark") == "plotly_dark"
    assert plotly_template("Light") == "plotly_white"


def test_chart_layout_uses_theme_surfaces_and_readable_text():
    light = chart_layout("Light")
    dark = chart_layout("Dark")
    assert light["template"] == "plotly_white"
    assert light["paper_bgcolor"] == THEME_PALETTES["Light"]["surface"]
    assert light["plot_bgcolor"] == THEME_PALETTES["Light"]["surface"]
    assert light["font"]["color"] == THEME_PALETTES["Light"]["text"]
    assert light["hoverlabel"]["font"]["color"] == THEME_PALETTES["Light"]["text"]
    assert dark["template"] == "plotly_dark"
    assert dark["paper_bgcolor"] == THEME_PALETTES["Dark"]["surface"]


def test_pnl_colors_are_limited_to_realized_result_values():
    assert pnl_color("10", "Light") == THEME_PALETTES["Light"]["positive"]
    assert pnl_color("-10", "Light") == THEME_PALETTES["Light"]["negative"]
    assert pnl_color("0", "Dark") == THEME_PALETTES["Dark"]["text"]


def test_theme_palettes_have_readable_foreground_and_surface_tokens():
    for palette in THEME_PALETTES.values():
        assert palette["text"] != palette["surface"]
        assert palette["text"]
        assert palette["muted"]
        assert palette["border"]


def test_streamlit_upload_limit_is_ten_megabytes():
    with Path(".streamlit/config.toml").open("rb") as config_file:
        config = tomllib.load(config_file)
    assert config["server"]["maxUploadSize"] == 10
