import numpy as np
import pandas as pd
import pytest

from ktfigure.gpu_preview import prepare_points


def test_prepare_points_keeps_finite_pairs_and_original_precision():
    points, dropped = prepare_points(
        pd.Series([1_000_000_000.0, 1_000_000_000.25, None, np.inf]),
        pd.Series([1.0, 2.0, 3.0, 4.0]),
    )
    np.testing.assert_array_equal(
        points, [[1_000_000_000.0, 1.0], [1_000_000_000.25, 2.0]]
    )
    assert dropped == 2


def test_prepare_points_rejects_non_numeric_or_empty_data():
    with pytest.raises(ValueError):
        prepare_points(pd.Series(["invalid"]), pd.Series([1]))
    with pytest.raises(ValueError, match="no finite numeric pairs"):
        prepare_points(pd.Series([None]), pd.Series([1]))
