def click_through_rate(clicks: int, views: int) -> float:
    if views <= 0:
        return 0.0
    return round(clicks / views, 4)


def merge_scores(windows: list[list[tuple[str, float]]], limit: int) -> list[tuple[str, float]]:
    totals: dict[str, float] = {}
    for window in windows:
        for member, score in window:
            totals[member] = totals.get(member, 0.0) + score
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return ranked[:limit]
