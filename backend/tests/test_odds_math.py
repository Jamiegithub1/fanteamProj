from decimal import Decimal

import pytest

from app.odds_math import (
    OverUnderMarket,
    aggregate_values,
    american_to_probability,
    decimal_to_probability,
    detect_outliers,
    expected_value_from_market,
    expected_value_from_over_under,
    mean,
    median_decimal,
    over_under_probabilities,
    remove_vig,
)


def test_american_to_probability_positive_odds() -> None:
    assert american_to_probability(150) == Decimal("0.400000")


def test_american_to_probability_negative_odds() -> None:
    assert american_to_probability(-120) == Decimal("0.545455")


def test_american_odds_reject_zero() -> None:
    with pytest.raises(ValueError, match="cannot be zero"):
        american_to_probability(0)


def test_decimal_to_probability() -> None:
    assert decimal_to_probability("2.50") == Decimal("0.400000")


def test_decimal_odds_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="greater than 1"):
        decimal_to_probability("1.00")


def test_remove_vig_normalizes_probabilities() -> None:
    over, under = remove_vig(Decimal("0.55"), Decimal("0.55"))

    assert over == Decimal("0.500000")
    assert under == Decimal("0.500000")


def test_over_under_probabilities_from_american_odds() -> None:
    over, under = over_under_probabilities(-110, -110)

    assert over == Decimal("0.500000")
    assert under == Decimal("0.500000")


def test_expected_value_from_over_under_moves_above_line_when_over_is_favored() -> None:
    expected = expected_value_from_over_under(
        line=Decimal("24.5"),
        over_probability=Decimal("0.56"),
        under_probability=Decimal("0.44"),
    )

    assert expected == Decimal("24.5600")


def test_expected_value_from_market() -> None:
    market = OverUnderMarket(
        line=Decimal("7.5"),
        over_probability=Decimal("0.48"),
        under_probability=Decimal("0.52"),
    )

    assert expected_value_from_market(market) == Decimal("7.4800")


def test_mean_and_median() -> None:
    values = [Decimal("10.0"), Decimal("12.0"), Decimal("14.0")]

    assert mean(values) == Decimal("12.0000")
    assert median_decimal(values) == Decimal("12.0000")


def test_outlier_detection_with_mad() -> None:
    assert detect_outliers([20, 21, 22, 100]) == (Decimal("100"),)


def test_aggregate_values_excludes_outliers_and_scores_confidence() -> None:
    result = aggregate_values([20, 21, 22, 100])

    assert result.values == (Decimal("20"), Decimal("21"), Decimal("22"))
    assert result.outliers == (Decimal("100"),)
    assert result.mean == Decimal("21.0000")
    assert result.median == Decimal("21.0000")
    assert result.confidence_score == Decimal("0.6267")


def test_aggregate_values_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="empty values"):
        aggregate_values([])
