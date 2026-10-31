"""Unit tests for the quiz leaderboard (temp files and a fake HTTP session)."""

import threading
from datetime import datetime, timezone

import pytest
import requests

from pitchsense.leaderboard import (
    FileStore,
    LeaderboardError,
    RateLimiter,
    SupabaseStore,
    add_score,
    board,
    clean_name,
    get_store,
    load_scores,
    make_entry,
    ranked,
    save,
    save_scores,
    top,
)


def test_make_entry_computes_averages_and_margin():
    entry = make_entry("Sam", total_points=360, model_points=300, rounds=6,
                       when=datetime(2026, 7, 17, tzinfo=timezone.utc))
    assert entry["name"] == "Sam"
    assert entry["rounds"] == 6
    assert entry["avg_points"] == 60.0
    assert entry["model_avg"] == 50.0
    assert entry["vs_model"] == 10.0        # beat the model by 10 pts/round
    assert entry["date"] == "2026-07-17"


def test_make_entry_defaults_blank_name_and_validates_rounds():
    assert make_entry("   ", 10, 10, 1)["name"] == "Anonymous"
    with pytest.raises(ValueError):
        make_entry("Sam", 0, 0, 0)


def test_load_missing_file_is_empty(tmp_path):
    assert load_scores(tmp_path / "nope.json") == []


def test_add_and_load_roundtrip(tmp_path):
    path = tmp_path / "lb.json"
    add_score(make_entry("A", 300, 200, 5), path)
    add_score(make_entry("B", 450, 200, 5), path)
    scores = load_scores(path)
    assert len(scores) == 2
    assert {s["name"] for s in scores} == {"A", "B"}


def test_corrupt_file_yields_empty_board(tmp_path):
    path = tmp_path / "lb.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_scores(path) == []


def test_ranked_orders_by_average_then_margin_then_rounds():
    scores = [
        make_entry("Low", 250, 250, 5),      # avg 50
        make_entry("High", 400, 300, 5),     # avg 80, +20
        make_entry("Mid", 300, 200, 5),      # avg 60, +20
    ]
    order = [s["name"] for s in ranked(scores)]
    assert order == ["High", "Mid", "Low"]


def test_margin_breaks_ties_on_average():
    scores = [
        make_entry("Beats", 300, 200, 5),    # avg 60, +20
        make_entry("Ties", 300, 300, 5),     # avg 60, 0
    ]
    order = [s["name"] for s in ranked(scores)]
    assert order == ["Beats", "Ties"]


def test_min_rounds_filter_excludes_thin_scores():
    scores = [
        make_entry("Cameo", 100, 50, 1),     # perfect-ish but only 1 round
        make_entry("Steady", 240, 200, 6),   # avg 40 over 6 rounds
    ]
    assert [s["name"] for s in ranked(scores, min_rounds=5)] == ["Steady"]


def test_top_limits_count(tmp_path):
    scores = [make_entry(f"P{i}", 300 + i, 200, 5) for i in range(12)]
    assert len(top(scores, n=10)) == 10


def test_save_scores_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "lb.json"
    save_scores([make_entry("A", 300, 200, 5)], path)
    assert path.exists()
    assert load_scores(path)[0]["name"] == "A"


def test_clean_name_strips_control_and_invisible_characters():
    assert clean_name("  Ada\u202e\u200b  \n Lovelace\x00 ") == "Ada Lovelace"
    assert clean_name("\u200b\t") == "Anonymous"
    assert clean_name(None) == "Anonymous"
    assert len(clean_name("x" * 100)) == 20
    assert make_entry("  \x07Bob ", 50, 40, 5)["name"] == "Bob"


def test_add_score_caps_the_board_keeping_the_best(tmp_path):
    path = tmp_path / "board.json"
    for i in range(8):
        add_score(make_entry(f"p{i}", i * 10 * 5, 0, 5), path, max_entries=5)
    names = [s["name"] for s in load_scores(path)]
    assert names == ["p7", "p6", "p5", "p4", "p3"]


def test_concurrent_saves_keep_every_row(tmp_path):
    path = tmp_path / "board.json"
    threads = [threading.Thread(target=add_score, args=(make_entry(f"p{i}", 300, 200, 5), path))
               for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(load_scores(path)) == 20


def test_rate_limiter_allows_a_burst_then_recovers():
    now = [0.0]
    limiter = RateLimiter(3, window=60, clock=lambda: now[0])
    assert [limiter.allow() for _ in range(4)] == [True, True, True, False]
    now[0] = 61
    assert limiter.allow()


class FakeResponse:
    def __init__(self, data=None, fail=False):
        self.data, self.fail = data, fail

    def raise_for_status(self):
        if self.fail:
            raise requests.HTTPError("500")

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, rows=None, fail=False):
        self.rows, self.fail, self.calls = rows or [], fail, []

    def get(self, url, params, headers, timeout):
        self.calls.append(("GET", url, params, headers))
        return FakeResponse(self.rows, self.fail)

    def post(self, url, json, headers, timeout):
        self.calls.append(("POST", url, json, headers))
        return FakeResponse(fail=self.fail)


def test_supabase_store_reads_ranked_rows_and_inserts_only_known_fields():
    row = make_entry("Ana", 300, 200, 5)
    http = FakeSession(rows=[row])
    store = SupabaseStore("https://abc.supabase.co/", "sb_publishable_x", session=http)
    assert store.load() == [row]
    store.add({**row, "extra": "ignored"})
    (_, url, params, headers), (_, _, sent, post_headers) = http.calls
    assert url == "https://abc.supabase.co/rest/v1/leaderboard"
    assert params["rounds"] == "gte.5" and params["order"].startswith("avg_points.desc")
    assert headers == {"apikey": "sb_publishable_x"}
    assert "extra" not in sent and sent["name"] == "Ana"
    assert post_headers["Prefer"] == "return=minimal"


def test_supabase_store_sends_a_legacy_key_as_a_bearer_token_too():
    store = SupabaseStore("https://abc.supabase.co", "eyJhbGciOi.legacy.jwt", session=FakeSession())
    assert store.headers["Authorization"] == "Bearer eyJhbGciOi.legacy.jwt"


def test_get_store_uses_supabase_only_when_configured():
    assert isinstance(get_store({}), FileStore)
    assert isinstance(get_store({"SUPABASE_URL": "https://abc.supabase.co"}), FileStore)
    assert isinstance(get_store({"SUPABASE_URL": "https://abc.supabase.co", "SUPABASE_KEY": "k"}), SupabaseStore)


def test_board_is_none_when_the_store_is_down():
    store = SupabaseStore("https://abc.supabase.co", "k", session=FakeSession(fail=True))
    assert board(store) is None


def test_save_reports_outages_and_rate_limits_as_leaderboard_errors(tmp_path):
    down = SupabaseStore("https://abc.supabase.co", "k", session=FakeSession(fail=True))
    with pytest.raises(LeaderboardError, match="can't be reached"):
        save(down, make_entry("A", 300, 200, 5), limiter=RateLimiter(5))
    store = FileStore(tmp_path / "board.json")
    limiter = RateLimiter(1)
    save(store, make_entry("A", 300, 200, 5), limiter=limiter)
    with pytest.raises(LeaderboardError, match="Try again in a minute"):
        save(store, make_entry("B", 300, 200, 5), limiter=limiter)
    assert [s["name"] for s in store.load()] == ["A"]
