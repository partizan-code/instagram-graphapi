from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("kwargs", [{}, {"image_url": "image", "video_url": "video"}])
def test_story_rejects_missing_or_ambiguous_media(kwargs):
    import publisher

    with pytest.raises(ValueError, match="image_url"):
        publisher.post_story(token="test-token", **kwargs)


@pytest.mark.parametrize("count", [0, 1, 21])
def test_carousel_rejects_invalid_count(count):
    import publisher

    with pytest.raises(ValueError, match="2 до 20"):
        publisher.post_carousel("caption", [{}] * count, "test-token")


def test_photo_creates_container_before_publishing_with_bearer(graph, reply):
    import publisher

    create_response = reply({"id": "container-1"})
    publish_response = reply({"id": "post-1"})
    graph.post.side_effect = [create_response, publish_response]

    assert (
        publisher.post_photo("caption", "https://example.invalid/photo.jpg", "test-token")
        == "post-1"
    )
    create, publish = graph.post.call_args_list
    assert create.args == ("https://graph.facebook.com/v27.0/12345/media",)
    assert create.kwargs["data"] == {
        "image_url": "https://example.invalid/photo.jpg",
        "caption": "caption",
    }
    assert publish.args == ("https://graph.facebook.com/v27.0/12345/media_publish",)
    assert publish.kwargs["data"] == {"creation_id": "container-1"}
    assert graph.headers == {"Authorization": "Bearer test-token"}
    for call in graph.post.call_args_list:
        assert call.kwargs["timeout"] == 30 and call.kwargs["allow_redirects"] is False
        assert "access_token" not in call.kwargs["data"]
    create_response.close.assert_called_once()
    publish_response.close.assert_called_once()
    assert graph.__exit__.call_count == 2


@pytest.mark.parametrize("status", ["ERROR", "EXPIRED"])
def test_failed_container_is_not_published(status, monkeypatch, graph, reply):
    import publisher

    graph.get.return_value = reply({"status_code": status, "status": "private-test-token"})
    publish = Mock()
    monkeypatch.setattr(publisher, "publish_container", publish)

    with pytest.raises(RuntimeError, match=status) as error:
        publisher._wait_ready("container-1", "test-token")
    assert "private" not in str(error.value)
    publish.assert_not_called()


def test_polling_timeout_is_bounded(monkeypatch):
    import publisher

    monkeypatch.setattr(publisher.time, "monotonic", Mock(side_effect=[0, 0, 11]))
    sleep = Mock()
    monkeypatch.setattr(publisher.time, "sleep", sleep)
    monkeypatch.setattr(publisher, "_check_status", Mock(return_value="IN_PROGRESS"))

    with pytest.raises(TimeoutError):
        publisher._wait_ready("container-1", "test-token", timeout=10)
    sleep.assert_called_once_with(10)


@pytest.mark.parametrize(
    "operation, args, kwargs, containers, expected_data",
    [
        (
            "post_reel",
            ("caption", "https://example.invalid/v.mp4", "test-token"),
            {},
            ["container"],
            {"media_type": "REELS", "share_to_feed": "true"},
        ),
        (
            "post_story",
            (),
            {"image_url": "https://example.invalid/p.jpg", "token": "test-token"},
            ["container"],
            {"media_type": "STORIES"},
        ),
        (
            "post_story",
            (),
            {"video_url": "https://example.invalid/v.mp4", "token": "test-token"},
            ["container"],
            {"media_type": "STORIES"},
        ),
        (
            "post_carousel",
            (
                "caption",
                [
                    {"type": "IMAGE", "url": "https://example.invalid/p.jpg"},
                    {"type": "VIDEO", "url": "https://example.invalid/v.mp4"},
                ],
                "test-token",
            ),
            {},
            ["image-child", "video-child", "carousel"],
            {"media_type": "CAROUSEL", "children": "image-child,video-child"},
        ),
    ],
)
def test_media_types_preserve_parameters_and_explicit_account(
    graph, reply, operation, args, kwargs, containers, expected_data
):
    import publisher

    graph.get.return_value = reply({"status_code": "FINISHED"})
    graph.post.side_effect = [reply({"id": value}) for value in [*containers, "post"]]
    assert getattr(publisher, operation)(*args, **kwargs, account_id="67890") == "post"
    for call in graph.post.call_args_list[:-1]:
        assert call.args == ("https://graph.facebook.com/v27.0/67890/media",)
    create_data = graph.post.call_args_list[-2].kwargs["data"]
    assert expected_data.items() <= create_data.items()
    publish = graph.post.call_args_list[-1]
    assert publish.args == ("https://graph.facebook.com/v27.0/67890/media_publish",)
    assert publish.kwargs["data"] == {"creation_id": containers[-1]}
    if operation == "post_reel" or "video_url" in kwargs or operation == "post_carousel":
        expected_container = "video-child" if operation == "post_carousel" else "container"
        graph.get.assert_called_once_with(
            f"https://graph.facebook.com/v27.0/{expected_container}",
            params={"fields": "status_code"},
            timeout=30,
            allow_redirects=False,
        )
    else:
        graph.get.assert_not_called()


def test_publishing_requires_instagram_account_id_before_request(monkeypatch, graph):
    import config
    import publisher

    monkeypatch.setattr(config, "INSTAGRAM_ACCOUNT_ID", "")
    with pytest.raises(RuntimeError, match="INSTAGRAM_ACCOUNT_ID"):
        publisher.post_photo("caption", "https://example.invalid/p.jpg", "test-token")
    graph.post.assert_not_called()


def test_publishing_does_not_ignore_meta_api_version(monkeypatch, graph, reply):
    import config
    import publisher

    monkeypatch.setattr(config, "META_API_VERSION", "v28.0")
    graph.post.return_value = reply({"id": "container"})
    assert publisher.create_container("test-token", image_url="https://example.invalid/p.jpg")
    assert graph.post.call_args.args[0] == "https://graph.facebook.com/v28.0/12345/media"
