from __future__ import annotations

from PIL import Image, ImageDraw

from ui_bench.types import (
    BACKGROUND_COLOR,
    CANVAS_SIZE,
    FOREGROUND_COLOR,
    IMAGE_MODE,
    Circle,
    FilledCircle,
    FilledSquare,
    Scene,
    Square,
    shape_bounds,
)


def render_scene(scene: Scene) -> Image.Image:
    image = Image.new(IMAGE_MODE, (CANVAS_SIZE, CANVAS_SIZE), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)

    for shape in scene.shapes:
        bounds = shape_bounds(shape)
        if isinstance(shape, FilledCircle):
            draw.ellipse(bounds, fill=FOREGROUND_COLOR)
        elif isinstance(shape, Circle):
            draw.ellipse(bounds, outline=FOREGROUND_COLOR, width=shape.stroke)
        elif isinstance(shape, FilledSquare):
            draw.rectangle(bounds, fill=FOREGROUND_COLOR)
        elif isinstance(shape, Square):
            draw.rectangle(bounds, outline=FOREGROUND_COLOR, width=shape.stroke)
        else:
            raise TypeError(f"Unsupported shape type: {type(shape)!r}")

    return image

