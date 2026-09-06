import time

from fastapi.testclient import TestClient

from tests.conftest import FakeTranscriptProvider


def _wait(client: TestClient, location: str) -> str:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(location)
        if "data-terminal=\"true\"" in response.text:
            return response.text
        time.sleep(0.02)
    raise AssertionError("Run did not finish.")


def test_batch_partial_success_and_synthesis(app_builder) -> None:
    provider = FakeTranscriptProvider(failing_ids={"9bZkp7q19f0"})
    with TestClient(app_builder(provider=provider)) as client:
        response = client.post(
            "/runs",
            data={
                "urls": (
                    "https://youtu.be/dQw4w9WgXcQ, "
                    "https://youtu.be/9bZkp7q19f0, "
                    "https://example.com/not-youtube, "
                    "https://youtube.com/watch?v=J---aiyznGQ"
                )
            },
            follow_redirects=False,
        )
        html = _wait(client, response.headers["location"])
        assert "Analysis complete with some unavailable videos" in html
        assert "Compared 2 videos." in html
        assert "Captions unavailable" in html
        assert "Only YouTube" in html


def test_equivalent_url_is_reused_across_runs(app_builder, fake_provider) -> None:
    with TestClient(app_builder(provider=fake_provider)) as client:
        for value in (
            "https://youtu.be/dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ&list=test",
        ):
            response = client.post(
                "/runs",
                data={"urls": value},
                follow_redirects=False,
            )
            _wait(client, response.headers["location"])
    assert fake_provider.calls == ["dQw4w9WgXcQ"]


def test_dashboard_reopens_runs_and_saved_transcripts(app_builder) -> None:
    source_url = "https://youtu.be/dQw4w9WgXcQ"
    with TestClient(app_builder()) as client:
        submitted = client.post(
            "/runs",
            data={"urls": source_url},
            follow_redirects=False,
        )
        location = submitted.headers["location"]
        _wait(client, location)

        dashboard = client.get("/dashboard")

    assert dashboard.status_code == 200
    assert source_url in dashboard.text
    assert "Video dQw4w9WgXcQ" in dashboard.text
    assert f'href="{location}"' in dashboard.text
    assert f'href="{location}#transcripts"' in dashboard.text
    assert f'href="{location}/edit"' in dashboard.text


def test_canvas_markdown_can_be_previewed_saved_and_deleted(app_builder) -> None:
    source_url = "https://youtu.be/dQw4w9WgXcQ"
    edited_markdown = "# My edited analysis\n\n<script>alert('xss')</script>\n\n- Kept point"

    with TestClient(app_builder()) as client:
        submitted = client.post(
            "/runs",
            data={"urls": source_url},
            follow_redirects=False,
        )
        location = submitted.headers["location"]
        _wait(client, location)

        editor = client.get(f"{location}/edit")
        assert editor.status_code == 200
        assert "A concise test analysis." in editor.text

        preview = client.post(
            f"{location}/preview",
            data={"markdown_text": edited_markdown},
        )
        assert preview.status_code == 200
        assert "<h1>My edited analysis</h1>" in preview.text
        assert "<script>alert('xss')</script>" not in preview.text
        assert "&lt;script&gt;alert('xss')&lt;/script&gt;" in preview.text

        saved = client.post(
            f"{location}/content",
            data={"markdown_text": edited_markdown},
            follow_redirects=False,
        )
        assert saved.status_code == 303
        assert saved.headers["location"] == f"{location}?updated=1"

        canvas = client.get(location)
        assert "My edited analysis" in canvas.text
        assert "Kept point" in canvas.text
        assert "A concise test analysis." not in canvas.text
        assert "<script>alert('xss')</script>" not in canvas.text

        invalid = client.post(
            f"{location}/content",
            data={"markdown_text": "   "},
        )
        assert invalid.status_code == 422
        assert "Canvas Markdown cannot be empty" in invalid.text

        deleted = client.post(f"{location}/delete", follow_redirects=False)
        assert deleted.status_code == 303
        assert deleted.headers["location"] == "/dashboard?deleted=1"
        assert client.get(location).status_code == 404

        dashboard = client.get(deleted.headers["location"])
        assert "Canvas deleted" in dashboard.text
        assert source_url not in dashboard.text
        assert "Video dQw4w9WgXcQ" not in dashboard.text


def test_unknown_canvas_cannot_be_edited_or_deleted(app_builder) -> None:
    unknown = "/runs/00000000-0000-0000-0000-000000000000"
    with TestClient(app_builder()) as client:
        assert client.get(f"{unknown}/edit").status_code == 404
        assert client.post(f"{unknown}/delete").status_code == 404
