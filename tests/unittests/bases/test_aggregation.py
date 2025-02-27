import numpy as np
import pytest
import torch
from torchmetrics.aggregation import CatMetric, MaxMetric, MeanMetric, MinMetric, SumMetric

from unittests import BATCH_SIZE, NUM_BATCHES
from unittests.helpers.testers import MetricTester


def compare_mean(values, weights):
    """Baseline implementation for mean aggregation."""
    return np.average(values.numpy(), weights=weights)


def compare_sum(values, weights):
    """Baseline implementation for sum aggregation."""
    return np.sum(values.numpy())


def compare_min(values, weights):
    """Baseline implementation for min aggregation."""
    return np.min(values.numpy())


def compare_max(values, weights):
    """Baseline implementation for max aggregation."""
    return np.max(values.numpy())


# wrap all other than mean metric to take an additional argument
# this lets them fit into the testing framework
class WrappedMinMetric(MinMetric):
    """Wrapped min metric."""

    def update(self, values, weights):
        """Only pass values on."""
        super().update(values)


class WrappedMaxMetric(MaxMetric):
    """Wrapped max metric."""

    def update(self, values, weights):
        """Only pass values on."""
        super().update(values)


class WrappedSumMetric(SumMetric):
    """Wrapped min metric."""

    def update(self, values, weights):
        """Only pass values on."""
        super().update(values)


class WrappedCatMetric(CatMetric):
    """Wrapped cat metric."""

    def update(self, values, weights):
        """Only pass values on."""
        super().update(values)


@pytest.mark.parametrize(
    "values, weights",
    [
        (torch.rand(NUM_BATCHES, BATCH_SIZE), torch.ones(NUM_BATCHES, BATCH_SIZE)),
        (torch.rand(NUM_BATCHES, BATCH_SIZE), torch.rand(NUM_BATCHES, BATCH_SIZE) > 0.5),
        (torch.rand(NUM_BATCHES, BATCH_SIZE, 2), torch.rand(NUM_BATCHES, BATCH_SIZE, 2) > 0.5),
    ],
)
@pytest.mark.parametrize(
    "metric_class, compare_fn",
    [
        (WrappedMinMetric, compare_min),
        (WrappedMaxMetric, compare_max),
        (WrappedSumMetric, compare_sum),
        (MeanMetric, compare_mean),
    ],
)
class TestAggregation(MetricTester):
    """Test aggregation metrics."""

    @pytest.mark.parametrize("ddp", [False, True])
    def test_aggreagation(self, ddp, metric_class, compare_fn, values, weights):
        """Test modular implementation."""
        self.run_class_metric_test(
            ddp=ddp,
            metric_class=metric_class,
            reference_metric=compare_fn,
            check_scriptable=True,
            # Abuse of names here
            preds=values,
            target=weights,
        )


_case1 = float("nan") * torch.ones(5)
_case2 = torch.tensor([1.0, 2.0, float("nan"), 4.0, 5.0])


@pytest.mark.parametrize("value", [_case1, _case2])
@pytest.mark.parametrize("nan_strategy", ["error", "warn"])
@pytest.mark.parametrize("metric_class", [MinMetric, MaxMetric, SumMetric, MeanMetric, CatMetric])
def test_nan_error(value, nan_strategy, metric_class):
    """Test correct errors are raised."""
    metric = metric_class(nan_strategy=nan_strategy)
    if nan_strategy == "error":
        with pytest.raises(RuntimeError, match="Encounted `nan` values in tensor"):
            metric(value.clone())
    elif nan_strategy == "warn":
        with pytest.warns(UserWarning, match="Encounted `nan` values in tensor"):
            metric(value.clone())


@pytest.mark.parametrize(
    ("metric_class", "nan_strategy", "value", "expected"),
    [
        (MinMetric, "ignore", _case1, torch.tensor(float("inf"))),
        (MinMetric, 2.0, _case1, 2.0),
        (MinMetric, "ignore", _case2, 1.0),
        (MinMetric, 2.0, _case2, 1.0),
        (MaxMetric, "ignore", _case1, -torch.tensor(float("inf"))),
        (MaxMetric, 2.0, _case1, 2.0),
        (MaxMetric, "ignore", _case2, 5.0),
        (MaxMetric, 2.0, _case2, 5.0),
        (SumMetric, "ignore", _case1, 0.0),
        (SumMetric, 2.0, _case1, 10.0),
        (SumMetric, "ignore", _case2, 12.0),
        (SumMetric, 2.0, _case2, 14.0),
        (MeanMetric, "ignore", _case1, torch.tensor([float("nan")])),
        (MeanMetric, 2.0, _case1, 2.0),
        (MeanMetric, "ignore", _case2, 3.0),
        (MeanMetric, 2.0, _case2, 2.8),
        (CatMetric, "ignore", _case1, []),
        (CatMetric, 2.0, _case1, torch.tensor([2.0, 2.0, 2.0, 2.0, 2.0])),
        (CatMetric, "ignore", _case2, torch.tensor([1.0, 2.0, 4.0, 5.0])),
        (CatMetric, 2.0, _case2, torch.tensor([1.0, 2.0, 2.0, 4.0, 5.0])),
        (CatMetric, "ignore", torch.zeros(5), torch.zeros(5)),
    ],
)
def test_nan_expected(metric_class, nan_strategy, value, expected):
    """Test that nan values are handled correctly."""
    metric = metric_class(nan_strategy=nan_strategy)
    metric.update(value.clone())
    out = metric.compute()
    assert np.allclose(out, expected, equal_nan=True)


@pytest.mark.parametrize("metric_class", [MinMetric, MaxMetric, SumMetric, MeanMetric, CatMetric])
def test_error_on_wrong_nan_strategy(metric_class):
    """Test error raised on wrong nan_strategy argument."""
    with pytest.raises(ValueError, match="Arg `nan_strategy` should either .*"):
        metric_class(nan_strategy=[])


@pytest.mark.skipif(not hasattr(torch, "broadcast_to"), reason="PyTorch <1.8 does not have broadcast_to")
@pytest.mark.parametrize(
    ("weights", "expected"), [(1, 11.5), (torch.ones(2, 1, 1), 11.5), (torch.tensor([1, 2]).reshape(2, 1, 1), 13.5)]
)
def test_mean_metric_broadcasting(weights, expected):
    """Check that weight broadcasting works for mean metric."""
    values = torch.arange(24).reshape(2, 3, 4)
    avg = MeanMetric()

    assert avg(values, weights) == expected
