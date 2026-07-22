import shutil
from datetime import datetime, timezone

import pytest

from investsim.agent.claude_cli import ClaudeCliConfig, ClaudeCliEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot

pytestmark = pytest.mark.integration

_HAS_CLI = shutil.which("claude") is not None


@pytest.mark.skipif(not _HAS_CLI, reason="requiere el CLI 'claude' instalado y autenticado")
def test_real_recommendation_for_known_symbol():
    snapshot = MarketSnapshot(
        symbol="AAPL",
        price=230.5,
        day_change_pct=1.2,
        day_high=232.0,
        day_low=228.0,
        day_open=229.0,
        prev_close=227.8,
        as_of=datetime.now(timezone.utc),
    )
    engine = ClaudeCliEngine(ClaudeCliConfig())

    rec = engine.propose(snapshot)

    assert rec.symbol == "AAPL"
    assert rec.direction in (Direction.UP, Direction.DOWN)
    assert 0.05 <= rec.confidence <= 0.95
    assert rec.horizon is Horizon.ONE_DAY
    assert rec.suggested_amount > 0
    assert isinstance(rec.rationale, str) and len(rec.rationale) > 0
