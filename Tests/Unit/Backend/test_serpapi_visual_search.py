"""Provider contract checks without spending a search or sending evidence externally."""

import io

import httpx
import pytest
from PIL import Image

from Backend.App.Core.Exceptions import NextronError
from Backend.App.Modules.NexSrc.SerpApiVisualSearch import MAX_PROVIDER_BYTES, parse_matches, search, search_copy


def test_search_copy_is_a_small_metadata_free_jpeg():
    image = Image.new("RGB", (2200, 1800), (123, 45, 67))
    raw = search_copy(image)
    assert len(raw) <= MAX_PROVIDER_BYTES
    with Image.open(io.BytesIO(raw)) as result:
        assert result.format == "JPEG"
        assert max(result.size) <= 1200
        assert not result.getexif()


def test_free_search_uploads_then_returns_only_safe_unscored_leads():
    visited = []

    def provider(request):
        visited.append(request.url.path)
        if request.url.path == "/account.json":
            assert request.url.params["api_key"] == "test-secret"
            return httpx.Response(200, json={"plan_name": "Free", "plan_monthly_price": 0,
                                             "plan_searches_left": 3, "this_hour_searches": 1,
                                             "account_rate_limit_per_hour": 50})
        if request.url.path == "/image":
            assert b"search-copy.jpg" in request.content
            return httpx.Response(200, json={"image_id": "temporary-id"})
        assert request.url.path == "/search.json"
        assert request.url.params["engine"] == "google_lens"
        assert request.url.params["image_id"] == "temporary-id"
        return httpx.Response(200, json={"search_metadata": {"status": "Success"}, "visual_matches": [
            {"title": "Earlier page", "link": "https://example.org/post", "image": "https://example.org/p.jpg", "exact_matches": True},
            {"title": "Bad", "link": "javascript:alert(1)", "image": "file:///private"},
            {"title": "Related page", "link": "https://example.net/other"},
        ]})

    rows = search(Image.new("RGB", (300, 300), "blue"), "test-secret", 10,
                  transport=httpx.MockTransport(provider))
    assert visited == ["/account.json", "/image", "/search.json"]
    assert [r["match_type"] for r in rows] == ["EXACT_MATCH_REPORTED", "VISUAL_MATCH"]
    assert all(r["score"] is None and r["score_kind"] is None for r in rows)


@pytest.mark.parametrize("account", [
    {"plan_name": "Starter", "plan_monthly_price": 25, "plan_searches_left": 100},
    {"plan_name": "Free", "plan_monthly_price": 0, "plan_searches_left": 0},
])
def test_nonfree_or_depleted_account_never_uploads(account):
    visited = []

    def provider(request):
        visited.append(request.url.path)
        return httpx.Response(200, json=account)

    with pytest.raises(NextronError):
        search(Image.new("RGB", (30, 30), "red"), "test-secret", 5, transport=httpx.MockTransport(provider))
    assert visited == ["/account.json"]


def test_provider_errors_do_not_include_secret():
    def provider(request):
        return httpx.Response(401, json={"error": "test-secret is invalid"})

    with pytest.raises(NextronError) as raised:
        search(Image.new("RGB", (30, 30), "red"), "test-secret", 5, transport=httpx.MockTransport(provider))
    assert "test-secret" not in raised.value.message


def test_result_requires_success_not_a_placeholder():
    with pytest.raises(NextronError):
        parse_matches({"search_metadata": {"status": "Processing"}, "visual_matches": []}, 5)
