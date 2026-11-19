"""PostgreSQL connection reuse: chat turns must not reopen TLS links per read."""
from types import SimpleNamespace

from psycopg.pq import TransactionStatus

from app.database import postgres


class FakeRawConnection:
    def __init__(self):
        self.closed = False
        self.rollbacks = 0
        self.close_calls = 0
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)

    def rollback(self):
        self.rollbacks += 1
        self.info.transaction_status = TransactionStatus.IDLE

    def close(self):
        self.closed = True
        self.close_calls += 1


def _patch_pool(monkeypatch, raws):
    monkeypatch.setattr(postgres, "_POOL", [])
    monkeypatch.setattr(postgres, "_POOL_SIZE", 2)
    monkeypatch.setattr(postgres, "_initialise", lambda: None)

    def fake_raw_connect():
        raw = FakeRawConnection()
        raws.append(raw)
        return raw

    monkeypatch.setattr(postgres, "_raw_connect", fake_raw_connect)


def test_connections_are_reused_after_close(monkeypatch):
    raws = []
    _patch_pool(monkeypatch, raws)

    first = postgres.connect()
    first.close()
    second = postgres.connect()
    second.close()

    assert len(raws) == 1
    assert first.raw is second.raw
    assert raws[0].close_calls == 0


def test_dirty_transaction_is_rolled_back_before_reuse(monkeypatch):
    raws = []
    _patch_pool(monkeypatch, raws)

    first = postgres.connect()
    first.raw.info.transaction_status = TransactionStatus.INTRANS
    first.close()

    assert raws[0].rollbacks == 1
    again = postgres.connect()
    assert again.raw is raws[0]
    assert again.raw.info.transaction_status == TransactionStatus.IDLE


def test_closed_connection_is_discarded(monkeypatch):
    raws = []
    _patch_pool(monkeypatch, raws)

    first = postgres.connect()
    first.raw.closed = True
    first.close()
    second = postgres.connect()

    assert len(raws) == 2
    assert second.raw is raws[1]


def test_pool_respects_size_limit(monkeypatch):
    raws = []
    _patch_pool(monkeypatch, raws)

    held = [postgres.connect() for _ in range(3)]
    for connection in held:
        connection.close()
    assert len(postgres._POOL) == 2
    assert sum(1 for raw in raws if raw.close_calls) == 1
