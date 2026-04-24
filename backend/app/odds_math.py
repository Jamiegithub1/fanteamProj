from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

Number = Decimal | int | float | str

FOUR_PLACES = Decimal("0.0001")
SIX_PLACES = Decimal("0.000001")


@dataclass(frozen=True)
class OverUnderMarket:
    line: Decimal
    over_probability: Decimal
    under_probability: Decimal


@dataclass(frozen=True)
class AggregationResult:
    mean: Decimal
    median: Decimal
    values: tuple[Decimal, ...]
    outliers: tuple[Decimal, ...]
    confidence_score: Decimal


def to_decimal(value: Number) -> Decimal:
    return Decimal(str(value))


def quantize(value: Decimal, places: Decimal = FOUR_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def american_to_probability(odds: int) -> Decimal:
    if odds == 0:
        raise ValueError("American odds cannot be zero")

    odds_decimal = Decimal(abs(odds))
    if odds > 0:
        probability = Decimal(100) / (odds_decimal + Decimal(100))
    else:
        probability = odds_decimal / (odds_decimal + Decimal(100))

    return quantize(probability, SIX_PLACES)


def decimal_to_probability(odds: Number) -> Decimal:
    odds_decimal = to_decimal(odds)
    if odds_decimal <= Decimal(1):
        raise ValueError("Decimal odds must be greater than 1")

    return quantize(Decimal(1) / odds_decimal, SIX_PLACES)


def remove_vig(*probabilities: Number) -> tuple[Decimal, ...]:
    raw_probabilities = tuple(to_decimal(probability) for probability in probabilities)
    total = sum(raw_probabilities, Decimal(0))
    if not raw_probabilities or total <= 0:
        raise ValueError("Probabilities must sum to a positive value")

    return tuple(quantize(probability / total, SIX_PLACES) for probability in raw_probabilities)


def over_under_probabilities(over_odds: Number, under_odds: Number, odds_format: str = "american") -> tuple[Decimal, Decimal]:
    if odds_format == "american":
        over_probability = american_to_probability(int(over_odds))
        under_probability = american_to_probability(int(under_odds))
    elif odds_format == "decimal":
        over_probability = decimal_to_probability(over_odds)
        under_probability = decimal_to_probability(under_odds)
    else:
        raise ValueError("odds_format must be 'american' or 'decimal'")

    normalized = remove_vig(over_probability, under_probability)
    return normalized[0], normalized[1]


def expected_value_from_over_under(
    line: Number,
    over_probability: Number,
    under_probability: Number | None = None,
    half_point_step: Number = Decimal("0.5"),
) -> Decimal:
    line_decimal = to_decimal(line)
    over = to_decimal(over_probability)
    under = Decimal(1) - over if under_probability is None else to_decimal(under_probability)
    normalized_over, _ = remove_vig(over, under)
    step = to_decimal(half_point_step)
    if step <= 0:
        raise ValueError("half_point_step must be positive")

    edge = (normalized_over - Decimal("0.5")) * Decimal(2)
    return quantize(line_decimal + (edge * step), FOUR_PLACES)


def expected_value_from_market(market: OverUnderMarket, half_point_step: Number = Decimal("0.5")) -> Decimal:
    return expected_value_from_over_under(
        market.line,
        market.over_probability,
        market.under_probability,
        half_point_step=half_point_step,
    )


def mean(values: list[Number] | tuple[Number, ...]) -> Decimal:
    decimals = tuple(to_decimal(value) for value in values)
    if not decimals:
        raise ValueError("Cannot calculate mean for empty values")

    return quantize(sum(decimals, Decimal(0)) / Decimal(len(decimals)), FOUR_PLACES)


def median_decimal(values: list[Number] | tuple[Number, ...]) -> Decimal:
    decimals = tuple(to_decimal(value) for value in values)
    if not decimals:
        raise ValueError("Cannot calculate median for empty values")

    return quantize(Decimal(str(median(decimals))), FOUR_PLACES)


def detect_outliers(values: list[Number] | tuple[Number, ...], threshold: Number = Decimal("3")) -> tuple[Decimal, ...]:
    decimals = tuple(to_decimal(value) for value in values)
    if len(decimals) < 4:
        return ()

    center = Decimal(str(median(decimals)))
    deviations = tuple(abs(value - center) for value in decimals)
    mad = Decimal(str(median(deviations)))
    if mad == 0:
        non_center = tuple(value for value in decimals if value != center)
        return non_center if len(non_center) == 1 else ()

    cutoff = to_decimal(threshold) * mad
    return tuple(value for value in decimals if abs(value - center) > cutoff)


def confidence_score(source_count: int, outlier_count: int, dispersion: Number) -> Decimal:
    if source_count <= 0:
        return Decimal("0.0000")

    source_component = min(Decimal(source_count) / Decimal(5), Decimal(1))
    outlier_penalty = min(Decimal(outlier_count) * Decimal("0.12"), Decimal("0.6"))
    dispersion_penalty = min(to_decimal(dispersion) * Decimal("0.08"), Decimal("0.5"))
    score = max(Decimal("0"), source_component - outlier_penalty - dispersion_penalty)
    return quantize(score, FOUR_PLACES)


def aggregate_values(values: list[Number] | tuple[Number, ...]) -> AggregationResult:
    decimals = tuple(to_decimal(value) for value in values)
    if not decimals:
        raise ValueError("Cannot aggregate empty values")

    outliers = detect_outliers(decimals)
    clean_values = tuple(value for value in decimals if value not in outliers)
    if not clean_values:
        clean_values = decimals

    center = Decimal(str(median(clean_values)))
    dispersion = mean(tuple(abs(value - center) for value in clean_values))

    return AggregationResult(
        mean=mean(clean_values),
        median=median_decimal(clean_values),
        values=clean_values,
        outliers=outliers,
        confidence_score=confidence_score(len(decimals), len(outliers), dispersion),
    )
