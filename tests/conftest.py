"""
Shared pytest fixtures for ktfigure tests.
"""
import os
import sys
import pytest
import pandas as pd

# ---------------------------------------------------------------------------
# Ensure the src layout is importable
# ---------------------------------------------------------------------------
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


# ---------------------------------------------------------------------------
# Sample DataFrames used across tests
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_df():
    """A small DataFrame suitable for most plot types."""
    return pd.DataFrame(
        {
            "x": [1, 2, 3, 4, 5, 6, 7, 8],
            "y": [10, 20, 15, 25, 30, 20, 35, 40],
            "category": ["A", "B", "A", "B", "A", "B", "A", "B"],
            "size": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )


@pytest.fixture
def heatmap_df():
    """DataFrame for heatmap testing."""
    return pd.DataFrame(
        {
            "x": ["A", "B", "A", "B", "C", "C"],
            "y": ["X", "X", "Y", "Y", "X", "Y"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        }
    )


@pytest.fixture
def count_df():
    """DataFrame for count/bar plot testing."""
    return pd.DataFrame(
        {
            "category": ["A", "B", "A", "C", "B", "A"],
            "value": [1, 2, 3, 4, 5, 6],
        }
    )
