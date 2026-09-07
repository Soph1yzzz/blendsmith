from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from blendsmith.errors import IntegrityError
from blendsmith.evidence import materialize_evidence


def _image(path: Path, size: tuple[int, int]) -> None:
    Image.new("RGB", size).save(path)


def test_default_evidence_minimum_accepts_portrait_with_same_long_short_edges(tmp_path: Path) -> None:
    source = tmp_path / "portrait.png"
    _image(source, (900, 1600))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    _, bundle = materialize_evidence(
        run_dir,
        candidate_id="candidate-1",
        views={"front": source},
        minimum_width=1600,
        minimum_height=900,
    )
    record = bundle["views"][0]
    assert record["width"] == 900
    assert record["height"] == 1600


def test_evidence_profile_enforces_view_specific_orientation(tmp_path: Path) -> None:
    source = tmp_path / "portrait.png"
    _image(source, (900, 1600))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with pytest.raises(IntegrityError, match="landscape"):
        materialize_evidence(
            run_dir,
            candidate_id="candidate-1",
            views={"hero": source},
            evidence_profiles={
                "hero": {
                    "minimum_width": 900,
                    "minimum_height": 900,
                    "orientation": "LANDSCAPE",
                }
            },
        )
