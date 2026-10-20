from wishly.ratelimit import RateLimiter


def test_allows_up_to_the_limit_per_key_then_resets() -> None:
    now = [0.0]
    limiter = RateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])

    assert [limiter.allow("a") for _ in range(3)] == [True, True, False]
    assert limiter.allow("b")  # keys are counted separately

    now[0] = 60.0  # next window
    assert limiter.allow("a")
