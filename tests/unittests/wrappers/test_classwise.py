import pytest
import torch
from torchmetrics import MetricCollection
from torchmetrics.classification import MulticlassAccuracy, MulticlassRecall
from torchmetrics.wrappers import ClasswiseWrapper


def test_raises_error_on_wrong_input():
    """Test that errors are raised on wrong input."""
    with pytest.raises(ValueError, match="Expected argument `metric` to be an instance of `torchmetrics.Metric` but.*"):
        ClasswiseWrapper([])

    with pytest.raises(ValueError, match="Expected argument `labels` to either be `None` or a list of strings.*"):
        ClasswiseWrapper(MulticlassAccuracy(num_classes=3), "hest")


def test_output_no_labels():
    """Test that wrapper works with no label input."""
    base = MulticlassAccuracy(num_classes=3, average=None)
    metric = ClasswiseWrapper(MulticlassAccuracy(num_classes=3, average=None))
    for _ in range(2):
        preds = torch.randn(20, 3).softmax(dim=-1)
        target = torch.randint(3, (20,))
        val = metric(preds, target)
        val_base = base(preds, target)
        assert isinstance(val, dict)
        assert len(val) == 3
        for i in range(3):
            assert f"multiclassaccuracy_{i}" in val
            assert val[f"multiclassaccuracy_{i}"] == val_base[i]


def test_output_with_labels():
    """Test that wrapper works with label input."""
    labels = ["horse", "fish", "cat"]
    base = MulticlassAccuracy(num_classes=3, average=None)
    metric = ClasswiseWrapper(MulticlassAccuracy(num_classes=3, average=None), labels=labels)
    for _ in range(2):
        preds = torch.randn(20, 3).softmax(dim=-1)
        target = torch.randint(3, (20,))
        val = metric(preds, target)
        val_base = base(preds, target)
        assert isinstance(val, dict)
        assert len(val) == 3
        for i, lab in enumerate(labels):
            assert f"multiclassaccuracy_{lab}" in val
            assert val[f"multiclassaccuracy_{lab}"] == val_base[i]
        val = metric.compute()
        val_base = base.compute()
        assert isinstance(val, dict)
        assert len(val) == 3
        for i, lab in enumerate(labels):
            assert f"multiclassaccuracy_{lab}" in val
            assert val[f"multiclassaccuracy_{lab}"] == val_base[i]


@pytest.mark.parametrize("prefix", [None, "pre_"])
@pytest.mark.parametrize("postfix", [None, "_post"])
def test_using_metriccollection(prefix, postfix):
    """Test wrapper in combination with metric collection."""
    labels = ["horse", "fish", "cat"]
    metric = MetricCollection(
        {
            "accuracy": ClasswiseWrapper(MulticlassAccuracy(num_classes=3, average=None), labels=labels),
            "recall": ClasswiseWrapper(MulticlassRecall(num_classes=3, average=None), labels=labels),
        },
        prefix=prefix,
        postfix=postfix,
    )
    preds = torch.randn(10, 3).softmax(dim=-1)
    target = torch.randint(3, (10,))
    val = metric(preds, target)
    assert isinstance(val, dict)
    assert len(val) == 6

    def _get_correct_name(base):
        name = base if prefix is None else prefix + base
        return name if postfix is None else name + postfix

    for lab in labels:
        name = _get_correct_name(f"multiclassaccuracy_{lab}")
        assert name in val
        name = _get_correct_name(f"multiclassrecall_{lab}")
        assert name in val
