"""Checks for the shared documentation illustration sprite."""

from pathlib import Path
import xml.etree.ElementTree as ET


SPRITE = Path(__file__).resolve().parents[1] / "docs/images/step-illustrations.svg"
SVG = "{http://www.w3.org/2000/svg}"


def test_external_symbols_have_self_contained_styles():
    root = ET.parse(SPRITE).getroot()

    # External <use> instances must not depend on the sprite's stylesheet.
    assert not root.findall(f".//{SVG}style")
    assert all("class" not in element.attrib for element in root.iter())

    groups = root.find(f".//{SVG}symbol[@id='groups']")
    assert groups.find(f"{SVG}rect").get("fill") == "#eaf5ee"
    assert groups.find(f"{SVG}text").get("fill") == "#172d35"

    sampling = root.find(f".//{SVG}symbol[@id='sampling']")
    assert sampling.find(f"{SVG}g").get("fill") == "#fff"
    assert sampling.find(f"{SVG}path").get("fill") == "none"

    scatter = root.find(f".//{SVG}symbol[@id='plot-scatter']")
    assert scatter.find(f"{SVG}path").get("fill") == "none"
    assert [group.get("fill") for group in scatter.findall(f"{SVG}g")] == [
        "#0173b2",
        "#de8f05",
    ]
