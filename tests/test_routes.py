from fastapi.testclient import TestClient

from tests.conftest import FakeHealthService


def test_health_reports_database_availability(app_builder) -> None:
    with TestClient(app_builder()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_when_database_is_unavailable(app_builder) -> None:
    health = FakeHealthService(available=False)
    with TestClient(app_builder(health=health)) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "unavailable",
    }


def test_input_page_and_invalid_single_submission(app_builder) -> None:
    with TestClient(app_builder()) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Turn YouTube videos" in response.text

        invalid = client.post("/runs", data={"urls": "https://example.com/video"})
        assert invalid.status_code == 422
        assert "Only YouTube" in invalid.text


def test_empty_dashboard_has_new_canvas_navigation(app_builder) -> None:
    with TestClient(app_builder()) as client:
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Research dashboard" in response.text
    assert "No canvases yet" in response.text
    assert 'href="/"' in response.text


def test_unknown_results_and_events_return_404(app_builder) -> None:
    unknown = "00000000-0000-4000-8000-000000000000"
    with TestClient(app_builder()) as client:
        assert client.get(f"/runs/{unknown}").status_code == 404
        assert client.get(f"/runs/{unknown}/events").status_code == 404


def test_more_than_ten_unique_videos_is_rejected(app_builder) -> None:
    video_ids = [f"VID{i:08d}" for i in range(11)]
    with TestClient(app_builder()) as client:
        response = client.post("/runs", data={"urls": ",".join(video_ids)})
        assert response.status_code == 422
        assert "at most 10 unique" in response.text
