import pytest

from app.services.url_normalizer import InvalidYouTubeUrl, normalize_youtube_url


@pytest.mark.parametrize(
    "value",
    [
        "dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=20",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=abc",
        "https://youtube.com/shorts/dQw4w9WgXcQ?feature=share",
        "https://youtube.com/embed/dQw4w9WgXcQ",
        "https://youtube.com/live/dQw4w9WgXcQ?si=abc",
    ],
)
def test_equivalent_urls_normalize_to_same_hash(value: str) -> None:
    normalized = normalize_youtube_url(value)
    assert normalized.video_id == "dQw4w9WgXcQ"
    assert normalized.canonical_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert len(normalized.url_hash) == 64


@pytest.mark.parametrize(
    "value",
    ["", "https://example.com/watch?v=dQw4w9WgXcQ", "https://youtube.com/watch?v=bad"],
)
def test_invalid_urls_are_rejected(value: str) -> None:
    with pytest.raises(InvalidYouTubeUrl):
        normalize_youtube_url(value)
