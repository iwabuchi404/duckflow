POSTS = [
    {"id": 1, "score": 30, "ts": "2026-09-01"},
    {"id": 2, "score": 95, "ts": "2026-09-02"},
    {"id": 3, "score": 50, "ts": "2026-09-03"},
]


def get_feed() -> list[dict]:
    return list(POSTS)
