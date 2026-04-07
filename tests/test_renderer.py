from __future__ import annotations

import hashlib

import numpy as np

from ui_bench.renderer import render_scene
from ui_bench.types import Circle, FilledCircle, FilledSquare, Scene, Square


def test_renderer_snapshots() -> None:
    cases = {
        "filled_circle": Scene((FilledCircle(cx=256, cy=256, radius=40),)),
        "circle": Scene((Circle(cx=300, cy=220, radius=60, stroke=4),)),
        "filled_square_odd": Scene((FilledSquare(cx=220, cy=360, size=81),)),
        "square_even": Scene((Square(cx=380, cy=120, size=80, stroke=3),)),
        "clip_left": Scene((FilledCircle(cx=10, cy=256, radius=40),)),
        "clip_top": Scene((FilledSquare(cx=256, cy=12, size=81),)),
        "clip_right": Scene((Circle(cx=500, cy=256, radius=40, stroke=6),)),
        "clip_bottom": Scene((Square(cx=256, cy=500, size=100, stroke=5),)),
        "overlap_order_a": Scene(
            (
                FilledSquare(cx=256, cy=256, size=180),
                Circle(cx=256, cy=256, radius=80, stroke=18),
            )
        ),
        "overlap_order_b": Scene(
            (
                Circle(cx=256, cy=256, radius=80, stroke=18),
                FilledSquare(cx=256, cy=256, size=180),
            )
        ),
    }
    expected_hashes = {
        "filled_circle": "6fbded64ac0fbfdf0cc3328bf2baf4b1ddb7e20a3562272b9f4988f33553083f",
        "circle": "92f84c834865aa8764a32075658f904ee1529c62a5315faa14b5418c0f3ab5c8",
        "filled_square_odd": "15e4e5238931e7e5810317dc5bf6ef6400073bdbec3abd294b8c01253c09c37b",
        "square_even": "d974a40e4f8b9517ad6f5936861b3bacdbd52221c8133f6e3d593cdca6bfdbaf",
        "clip_left": "2deba69e47b9a16d1b91589e3453bd9bc29f276dbf3e7c3f8d0ec565e5f69720",
        "clip_top": "a834cebb2b6a64556e0a9f7238f919e49149d6d828295f37ca15b629702e5894",
        "clip_right": "23685a684e0ac06997219992e270ef1d00479f225d8f16b2f07b263f29d0acd5",
        "clip_bottom": "978ff8e1fa75408ddc41ca4168972aa4808fea860d00b58e4f3abac68d2a872b",
        "overlap_order_a": "736191f8438a426fa9d1fc8de17b2660575d140d2b203c40eaed261d9f965132",
        "overlap_order_b": "736191f8438a426fa9d1fc8de17b2660575d140d2b203c40eaed261d9f965132",
    }

    actual_hashes = {name: _render_hash(scene) for name, scene in cases.items()}

    assert actual_hashes == expected_hashes
    assert actual_hashes["overlap_order_a"] == actual_hashes["overlap_order_b"]


def _render_hash(scene: Scene) -> str:
    image = render_scene(scene)
    array = np.asarray(image, dtype=np.uint8)
    return hashlib.sha256(array.tobytes()).hexdigest()
