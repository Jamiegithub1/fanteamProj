from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MarketDefinition:
    key: str
    name: str
    stat_key: str
    scoring_weight: Decimal
    aliases: tuple[str, ...]


MARKETS: tuple[MarketDefinition, ...] = (
    MarketDefinition("points", "Points", "points", Decimal("1.000"), ("points", "player points")),
    MarketDefinition(
        "threes_made",
        "3PT Made",
        "threes_made",
        Decimal("0.500"),
        ("3pm", "3pt made", "3 pointers made", "three pointers made", "player threes"),
    ),
    MarketDefinition("rebounds", "Rebounds", "rebounds", Decimal("1.250"), ("rebounds", "player rebounds")),
    MarketDefinition("assists", "Assists", "assists", Decimal("1.500"), ("assists", "player assists")),
    MarketDefinition("steals", "Steals", "steals", Decimal("2.000"), ("steals", "player steals")),
    MarketDefinition("blocks", "Blocks", "blocks", Decimal("2.000"), ("blocks", "player blocks")),
    MarketDefinition(
        "turnovers", "Turnovers", "turnovers", Decimal("-0.500"), ("turnovers", "player turnovers")
    ),
    MarketDefinition(
        "double_double",
        "Double-Double",
        "double_double_probability",
        Decimal("1.500"),
        ("double double", "double-double"),
    ),
    MarketDefinition(
        "triple_double",
        "Triple-Double",
        "triple_double_probability",
        Decimal("3.000"),
        ("triple double", "triple-double"),
    ),
)


def normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def identify_market(name: str) -> MarketDefinition | None:
    normalized = normalize_text(name)
    for market in MARKETS:
        if any(alias in normalized for alias in market.aliases):
            return market
    return None
