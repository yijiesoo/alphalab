"""
tests/test_app.py — unit tests for the Flask app's caching logic and API endpoints.

Run with:
    pytest tests/test_app.py -v
"""

import time

import pytest

# ---------------------------------------------------------------------------
# Import the Flask app (all external I/O is monkeypatched below)
# ---------------------------------------------------------------------------
from flask_app.app import _cache, _valid_ticker, app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_cache():
    """Wipe the in-memory cache before every test."""
    _cache.clear()
    yield
    _cache.clear()


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# _valid_ticker helper
# ---------------------------------------------------------------------------

class TestValidTicker:
    def test_valid_single_letter(self):
        assert _valid_ticker("A") is True

    def test_valid_five_letters(self):
        assert _valid_ticker("NVDA") is True

    def test_invalid_too_long(self):
        assert _valid_ticker("TOOLONG") is False

    def test_invalid_digits(self):
        assert _valid_ticker("NV1A") is False

    def test_invalid_empty(self):
        assert _valid_ticker("") is False

    def test_lowercase_accepted(self):
        # _valid_ticker uppercases internally
        assert _valid_ticker("nvda") is True

    def test_hyphen_suffix_accepted(self):
        # BRK-B, BRK-A are real tickers
        assert _valid_ticker("BRK-B") is True

    def test_dot_suffix_accepted(self):
        # BF.B, BRK.B are alternate formats
        assert _valid_ticker("BF-B") is True

    def test_invalid_underscore_rejected(self):
        assert _valid_ticker("BRK_B") is False

    def test_invalid_double_suffix_rejected(self):
        assert _valid_ticker("TOO_LONG_TICKER") is False


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------

class TestApiHealth:
    def test_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_cached_tickers_zero_when_empty(self, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["cached_tickers"] == 0

    def test_cached_tickers_counts_valid_entries(self, client):
        # Manually inject a valid cache entry
        _cache["AAPL"] = {"data": {"ticker": "AAPL"}, "expires_at": time.time() + 100}
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["cached_tickers"] == 1

    def test_expired_entries_not_counted(self, client):
        # Inject an already-expired entry
        _cache["MSFT"] = {"data": {"ticker": "MSFT"}, "expires_at": time.time() - 1}
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["cached_tickers"] == 0


# ---------------------------------------------------------------------------
# /api/cache
# ---------------------------------------------------------------------------

class TestApiCache:
    def test_empty_cache(self, client):
        resp = client.get("/api/cache")
        assert resp.status_code == 200
        assert resp.get_json() == {"cached_tickers": {}}

    def test_valid_entry_appears(self, client):
        future = time.time() + 500
        _cache["NVDA"] = {"data": {}, "expires_at": future}
        resp = client.get("/api/cache")
        data = resp.get_json()
        assert "NVDA" in data["cached_tickers"]
        assert data["cached_tickers"]["NVDA"]["ttl_seconds"] > 0

    def test_expired_entry_hidden(self, client):
        _cache["GOOG"] = {"data": {}, "expires_at": time.time() - 1}
        data = client.get("/api/cache").get_json()
        assert "GOOG" not in data["cached_tickers"]


# ---------------------------------------------------------------------------
# /api/analyze — cache behavior (no real network calls)
# ---------------------------------------------------------------------------

class TestApiAnalyzeCache:
    """
    We monkeypatch src.scorer.analyze_ticker so these tests never hit the
    network.  We import it lazily inside the route, so we patch the module
    attribute directly.
    """

    FAKE_DATA = {
        "ticker": "FAKE",
        "in_universe": True,
        "latest_price": 123.45,
        "note": "stub",
    }

    def _patch_scorer(self, monkeypatch):
        """Inject a fake scorer module and factor_delay module so the route's
        lazy imports work without network access."""
        import sys
        import types

        fake_scorer = types.ModuleType("src.scorer")
        fake_scorer.analyze_ticker = lambda ticker: {**self.FAKE_DATA, "ticker": ticker}
        monkeypatch.setitem(sys.modules, "src.scorer", fake_scorer)

        fake_delay = types.ModuleType("src.factor_delay")
        fake_delay.add_factor_delay_context = lambda data: data  # identity stub
        monkeypatch.setitem(sys.modules, "src.factor_delay", fake_delay)

        # Also make sure 'src' package is present
        if "src" not in sys.modules:
            fake_src = types.ModuleType("src")
            monkeypatch.setitem(sys.modules, "src", fake_src)

    @pytest.fixture()
    def auth_client(self):
        """A test client with a valid user session already established."""
        app.config["TESTING"] = True
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["user_email"] = "test@example.com"
                sess["firebase_uid"] = "test-uid"
            yield c

    def test_cache_miss_on_first_request(self, auth_client, monkeypatch):
        self._patch_scorer(monkeypatch)
        resp = auth_client.get("/api/analyze?ticker=FAKE")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["_cache"]["hit"] is False

    def test_cache_hit_on_second_request(self, auth_client, monkeypatch):
        self._patch_scorer(monkeypatch)
        auth_client.get("/api/analyze?ticker=FAKE")  # prime the cache
        resp = auth_client.get("/api/analyze?ticker=FAKE")
        data = resp.get_json()
        assert data["_cache"]["hit"] is True

    def test_refresh_busts_cache(self, auth_client, monkeypatch):
        self._patch_scorer(monkeypatch)
        # Prime the cache
        auth_client.get("/api/analyze?ticker=FAKE")
        # Bust it
        resp = auth_client.get("/api/analyze?ticker=FAKE&refresh=true")
        data = resp.get_json()
        assert data["_cache"]["hit"] is False

    def test_ttl_expiry_simulated(self, auth_client, monkeypatch):
        """Simulate expiry by backdating the cache entry's expires_at."""
        self._patch_scorer(monkeypatch)
        auth_client.get("/api/analyze?ticker=FAKE")  # prime
        # Backdate the expiry so the entry looks stale
        _cache["FAKE"]["expires_at"] = time.time() - 1
        resp = auth_client.get("/api/analyze?ticker=FAKE")
        data = resp.get_json()
        assert data["_cache"]["hit"] is False

    def test_missing_ticker_param(self, auth_client):
        resp = auth_client.get("/api/analyze")
        assert resp.status_code == 400

    def test_invalid_ticker_rejected(self, auth_client):
        resp = auth_client.get("/api/analyze?ticker=TOO_LONG_TICKER")
        assert resp.status_code == 400
