from app import discover_tools
from core.registry import all_tools


def test_tools_are_discovered_and_registered(client):
    assert "refunds" in discover_tools()
    assert "_template" not in discover_tools()
    assert "/refunds" in {t.path for t in all_tools()}


def test_errors_render_friendly_page_with_status(login):
    response = login("bob").get("/refunds/999999")
    assert response.status_code == 404 and "Refund 999999 not found" in response.text
