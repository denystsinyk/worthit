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


def test_dashboard_explains_matched_transactions():
    dashboard = (ROOT / "templates" / "dashboard.html").read_text()

    assert "Why this amount?" in dashboard
    assert "s.matched_transactions" in dashboard
