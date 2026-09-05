from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent.parent
ICON_NAMES = ("car-front", "utensils", "coffee", "concierge-bell")


def test_benefit_icons_share_one_lucide_visual_system():
    for name in ICON_NAMES:
        root = ElementTree.parse(ROOT / "static" / "icons" / f"{name}.svg").getroot()
        assert root.attrib["viewBox"] == "0 0 24 24"
        assert root.attrib["fill"] == "none"
        assert root.attrib["stroke-width"] == "2"
        assert root.attrib["stroke-linecap"] == "round"
        assert root.attrib["stroke-linejoin"] == "round"


def test_vendored_icon_license_is_present():
    license_text = (ROOT / "static" / "icons" / "LICENSE").read_text()
    assert "Lucide Icons and Contributors" in license_text
    assert "ISC License" in license_text


def test_analytics_chart_uses_visible_bar_fill_layout():
    analytics = (ROOT / "templates" / "analytics.html").read_text()
    styles = (ROOT / "static" / "style.css").read_text()

    assert 'class="bar-fill"' in analytics
    assert "value / month.total * 100" in analytics
    assert ".bar-stack span" in styles
    assert ".bar-stack .series-dunkin" in styles
