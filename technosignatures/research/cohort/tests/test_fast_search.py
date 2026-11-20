from dataclasses import replace
import numpy as np
import pytest

from research.conventional.search import search, SearchConfig
from research.cohort.fast_search import search as fast
from test_evaluation import background


@pytest.mark.parametrize('batch', [1, 3, 16, 100])
@pytest.mark.parametrize('tile', [7, 256])
def test_vectorized_scores_hits_masks_and_coverage_match_reference(batch, tile):
    scan = background().scans[0]
    mask = scan.usable.copy(); mask[2, 50] = False; mask[7, 85] = False
    data = scan.power.copy(); data += 30*np.exp(-.5*((np.arange(128)[None,:]-40-.1*scan.time_s[:,None])/.8)**2)
    scan = replace(scan, power=data, usable=mask)
    config = SearchConfig(max_abs_drift_hz_per_s=.25, tile_core_channels=tile)
    actual, expected = fast(scan, config, batch), search(scan, config)
    np.testing.assert_array_equal(actual.scores, expected.scores)
    assert actual.hits == expected.hits and actual.coverage == expected.coverage and actual.tiles == expected.tiles
