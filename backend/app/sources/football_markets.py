from __future__ import annotations

from decimal import Decimal

from app.sources.markets import MarketDefinition, normalize_text


# ---------------------------------------------------------------------------
# Altenar typeIds for event-level ("markets" array) football markets.
# These are standard across Altenar operators but can vary; text-based
# fallback matching is always applied when a typeId is not recognised.
# ---------------------------------------------------------------------------
ALTENAR_MATCH_RESULT_TYPE_ID = 1          # 1X2 / Match Result
ALTENAR_TOTAL_GOALS_TYPE_ID = 18          # Total Goals O/U
ALTENAR_BTTS_TYPE_ID = 29                 # Both Teams to Score
ALTENAR_CLEAN_SHEET_HOME_TYPE_ID = 31     # Home Team Clean Sheet
ALTENAR_CLEAN_SHEET_AWAY_TYPE_ID = 32     # Away Team Clean Sheet
ALTENAR_TEAM_GOALS_HOME_TYPE_ID = 146     # Home Team Goals O/U (operator-specific)
ALTENAR_TEAM_GOALS_AWAY_TYPE_ID = 147     # Away Team Goals O/U (operator-specific)

# Selection typeIds within the Match Result market
ALTENAR_HOME_WIN_SELECTION_TYPE_ID = 1
ALTENAR_DRAW_SELECTION_TYPE_ID = 2
ALTENAR_AWAY_WIN_SELECTION_TYPE_ID = 3

# Selection typeIds for generic Over/Under markets
ALTENAR_OVER_SELECTION_TYPE_ID = 12
ALTENAR_UNDER_SELECTION_TYPE_ID = 13

# ---------------------------------------------------------------------------
# Altenar typeIds for player-level ("childMarkets" array) football markets.
# These vary more between operators; text aliases serve as robust fallback.
# ---------------------------------------------------------------------------
ALTENAR_ANYTIME_SCORER_TYPE_IDS: frozenset[int] = frozenset({45, 6694, 92})
ALTENAR_FIRST_SCORER_TYPE_IDS: frozenset[int] = frozenset({44, 6693, 28})

# Combined "Goalscorer" childMarket on this Altenar instance.
# Each entry bundles three odd selections whose typeIds determine the variant.
ALTENAR_COMBINED_GOALSCORER_TYPE_ID = 21001
ALTENAR_GOALSCORER_FIRST_SELECTION_ID = 2090   # First Goalscorer selection
ALTENAR_GOALSCORER_LAST_SELECTION_ID = 2091    # Last Goalscorer (skip)
ALTENAR_GOALSCORER_ANYTIME_SELECTION_ID = 2092  # Anytime Goalscorer selection
ALTENAR_LAST_SCORER_TYPE_IDS: frozenset[int] = frozenset({63, 6695})
ALTENAR_SHOTS_ON_TARGET_TYPE_IDS: frozenset[int] = frozenset({6723, 6724, 6730})
ALTENAR_PLAYER_ASSISTS_TYPE_IDS: frozenset[int] = frozenset({6710, 6712})
ALTENAR_CARDS_TYPE_IDS: frozenset[int] = frozenset({6700, 6701, 73})

# ---------------------------------------------------------------------------
# Football WM market definitions.
#
# fanteam_scoring_weight for team-level markets is 0 because these
# are not used in a fantasy-points formula; they are informational.
# Player markets carry FanTeam-Football-aligned weights for future use.
#
# Aliases MUST NOT overlap with NBA markets in markets.py because
# identify_football_market() is a separate function scoped to this tuple.
# ---------------------------------------------------------------------------
FOOTBALL_WM_MARKETS: tuple[MarketDefinition, ...] = (
    # --- team / match level ------------------------------------------------
    MarketDefinition(
        key="wm_team_win",
        name="WM Team Win",
        stat_key="wm_team_win",
        scoring_weight=Decimal("0"),
        # Not text-matched; assigned programmatically from Match Result selections
        aliases=(),
    ),
    MarketDefinition(
        key="wm_match_draw",
        name="WM Match Draw",
        stat_key="wm_match_draw",
        scoring_weight=Decimal("0"),
        aliases=(),  # assigned programmatically
    ),
    MarketDefinition(
        key="wm_total_goals",
        name="WM Total Goals",
        stat_key="wm_total_goals",
        scoring_weight=Decimal("0"),
        aliases=(
            "total goals",
            "total match goals",
            "goals over under",
            "match goals",
            "over under goals",
        ),
    ),
    MarketDefinition(
        key="wm_team_goals",
        name="WM Team Goals",
        stat_key="wm_team_goals",
        scoring_weight=Decimal("0"),
        aliases=(
            "team total goals",
            "team goals over under",
            "goals scored team",
        ),
    ),
    MarketDefinition(
        key="wm_btts",
        name="WM Both Teams to Score",
        stat_key="wm_btts",
        scoring_weight=Decimal("0"),
        aliases=(
            "both teams to score",
            "btts",
            "both teams score",
            "both to score",
            "gg ng",
            "gg/ng",
        ),
    ),
    MarketDefinition(
        key="wm_clean_sheet",
        name="WM Clean Sheet",
        stat_key="wm_clean_sheet",
        scoring_weight=Decimal("0"),
        aliases=("clean sheet",),
    ),
    # --- player level -------------------------------------------------------
    MarketDefinition(
        key="wm_anytime_scorer",
        name="WM Anytime Scorer",
        stat_key="wm_anytime_scorer",
        scoring_weight=Decimal("4.0"),
        aliases=(
            "anytime scorer",
            "anytime goalscorer",
            "to score anytime",
            "goalscorer anytime",
            "scorer anytime",
            "to score",
            "goalscorer",
        ),
    ),
    MarketDefinition(
        key="wm_first_scorer",
        name="WM First Goalscorer",
        stat_key="wm_first_scorer",
        scoring_weight=Decimal("6.0"),
        aliases=(
            "first goalscorer",
            "first scorer",
            "to score first",
            "first goal scorer",
        ),
    ),
    MarketDefinition(
        key="wm_shots_on_target",
        name="WM Shots on Target",
        stat_key="wm_shots_on_target",
        scoring_weight=Decimal("0"),
        aliases=(
            "shots on target",
            "player shots on target",
            "total shots on target",
        ),
    ),
    MarketDefinition(
        key="wm_player_assists",
        name="WM Player Assists",
        stat_key="wm_player_assists",
        scoring_weight=Decimal("3.0"),
        aliases=(
            "player to assist",
            "to assist",
            "goalscorer assist",
            "to provide assist",
        ),
    ),
    MarketDefinition(
        key="wm_cards",
        name="WM Cards",
        stat_key="wm_cards",
        scoring_weight=Decimal("-1.0"),
        aliases=(
            "player to be carded",
            "to be booked",
            "player yellow card",
            "to receive a card",
        ),
    ),
)

# Set of market keys that are team-level (not attached to a specific player)
TEAM_LEVEL_MARKET_KEYS: frozenset[str] = frozenset(
    {
        "wm_team_win",
        "wm_match_draw",
        "wm_total_goals",
        "wm_team_goals",
        "wm_btts",
        "wm_clean_sheet",
    }
)

# Set of market keys that represent individual player props
PLAYER_LEVEL_MARKET_KEYS: frozenset[str] = frozenset(
    {
        "wm_anytime_scorer",
        "wm_first_scorer",
        "wm_shots_on_target",
        "wm_player_assists",
        "wm_cards",
    }
)


def identify_football_market(name: str) -> MarketDefinition | None:
    """Match a market name string against FOOTBALL_WM_MARKETS aliases."""
    normalized = normalize_text(name)
    for market in FOOTBALL_WM_MARKETS:
        if any(alias in normalized for alias in market.aliases):
            return market
    return None
