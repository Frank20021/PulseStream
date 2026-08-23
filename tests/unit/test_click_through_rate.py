from shared.analytics.metrics import click_through_rate, merge_scores


def test_click_through_rate_divides_clicks_by_views() -> None:
    assert click_through_rate(25, 100) == 0.25


def test_click_through_rate_is_zero_without_views() -> None:
    assert click_through_rate(10, 0) == 0.0
    assert click_through_rate(0, 0) == 0.0


def test_merge_scores_adds_rolling_windows() -> None:
    windows = [
        [("post_101", 2.0), ("post_202", 1.0)],
        [("post_101", 1.0), ("post_303", 4.0)],
    ]
    assert merge_scores(windows, limit=2) == [("post_303", 4.0), ("post_101", 3.0)]
