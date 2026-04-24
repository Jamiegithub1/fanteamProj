from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol


OddSide = Literal["over", "under", "yes", "no"]


@dataclass(frozen=True)
class SourceOdd:
    source_key: str
    player_name: str
    market_key: str
    market_name: str
    side: OddSide
    collected_at: datetime
    line: Decimal | None = None
    american_odds: int | None = None
    decimal_odds: Decimal | None = None
    event_id: str | None = None
    event_name: str | None = None


@dataclass(frozen=True)
class SourceResult:
    source_key: str
    odds: tuple[SourceOdd, ...] = ()
    status: Literal["success", "degraded", "failed"] = "success"
    latency_ms: int | None = None
    message: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class SourceAdapter(Protocol):
    source_key: str
    source_name: str
    requires_browser: bool
    refresh_interval_seconds: int

    def fetch(self) -> SourceResult:
        pass
