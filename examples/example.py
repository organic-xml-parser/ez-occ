import typing
from dataclasses import dataclass


@dataclass
class ScreenshotParams:

    camera_origin: typing.Tuple[float, float, float]
    camera_dir: typing.Tuple[float, float, float]


@dataclass
class Example:

    title: str
    description: str
    source: str
    screenshot_params: ScreenshotParams
