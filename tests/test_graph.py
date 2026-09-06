import time

from fastapi.testclient import TestClient


def _wait_for_terminal(client: TestClient, location: str) -> str:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(location)
        if "Analysis complete" in response.text or "could not be completed" in response.text:
            return response.text
        time.sleep(0.02)
    raise AssertionError("Background graph did not reach a terminal state.")


def test_graph_checkpoints_single_run_and_renders_report(app_builder) -> None:
    with TestClient(app_builder()) as client:
        submitted = client.post(
            "/runs",
            data={"urls": "https://youtu.be/dQw4w9WgXcQ?t=2"},
            follow_redirects=False,
        )
        assert submitted.status_code == 303
        html = _wait_for_terminal(client, submitted.headers["location"])
        assert "A concise test analysis." in html
        assert "Saved transcripts" in html
        assert "fake-captions" in html
        events = client.get(submitted.headers["location"] + "/events")
        assert events.status_code == 200
        assert '"terminal":true' in events.text
