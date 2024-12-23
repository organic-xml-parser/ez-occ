#!/usr/bin/env python3
import argparse
import inspect
import os.path
import typing

import mistletoe

import logging
import math

import OCC.Core.TopAbs
from OCC.Core.gp import gp_Vec
from mistletoe.block_token import Heading
from mistletoe.markdown_renderer import MarkdownRenderer

from examples import bolt, enclosure, chess_piece, gears, dish

from ezocc.part_cache import InMemoryPartCache, FileBasedPartCache
from ezocc.part_manager import PartCache

DEFAULT_RESOLUTION = (1024, 768)

logger = logging.getLogger(__name__)


def process_example_module(cache: PartCache,
                           example_module,
                           screenshot_angles: typing.List[typing.Tuple[float, float, float]],
                           inserted_elements):
    title = example_module.TITLE
    description = example_module.DESCRIPTION
    filename = example_module.FILENAME

    inserted_elements.append(mistletoe.Document('### ' + title))

    logger.warning(f"Building part: {title}")
    part = example_module.build(cache)

    logger.warning("Setting Up Rendering...")
    sf = part.preview_offscreen(resolution=DEFAULT_RESOLUTION)
    sf.session_frame.render_target_policy.set_shape_type_renderable(OCC.Core.TopAbs.TopAbs_VERTEX, False)
    sf.session_frame.camera.SetViewUp(0, 0, 1)

    dist = math.hypot(part.xts.x_span, part.xts.y_span, part.xts.z_span)

    for i in range(0, len(screenshot_angles)):
        vec = gp_Vec(*screenshot_angles[i]).Normalized()
        sf.session_frame.camera.SetPosition(vec.X() * dist, vec.Y() * dist, vec.Z() * dist)
        sf.session_frame.camera.SetFocalPoint(part.xts.xyz_mid)

        inserted_elements.append(mistletoe.Document(f"![screenshot](resources/{filename}_{i}.png)"))

        file_path = f"/wsp/resources/{filename}_{i}.png"

        logger.warning(f"Rendering... to file: {file_path}")
        sf.render(file_path)

    inserted_elements.append(mistletoe.Document(description))

    inserted_elements.append(mistletoe.Document(
        "```python\n" +
        inspect.getsource(example_module.build) +
        "\n```"
    ))



def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("readme_path")

    args = parser.parse_args()
    if not os.path.isabs(args.readme_path):
        raise ValueError(f"Readme path must be absolute: {args.readme_path}")

    if not os.path.isfile(args.readme_path):
        raise ValueError(f"Readme path is not a file: {args.readme_path}")

    cache = FileBasedPartCache("/wsp/cache")

    with open(args.readme_path, "r") as f:
        document = mistletoe.Document(f)

    lvl2_headings = \
        [(i, c) for i, c in enumerate(document.children) if isinstance(c, mistletoe.block_token.Heading) and c.level == 2]

    example_heading = [(i, c) for i, c in lvl2_headings if len(c.children) == 1 and c.children[0].content == "Examples"]
    example_heading_index = example_heading[0][0]

    # remove everything currently in the examples section
    next_heading = [(i, c) for i, c in lvl2_headings if i > example_heading[0][0]]
    if len(next_heading) == 0:
        next_index = example_heading_index + 1
    else:
        next_index = next_heading[0][0]

    inserted_elements = []

    to_process = {
        gears: [(1, -1, 2)],
        bolt: [(1, -1, 2)],
        enclosure: [(-1, 1, 2)],
        chess_piece: [(1, 1, 1)],
        dish: [(1, 0, -4), (1, 1, 2)],
    }

    for p, dirs in to_process.items():
        process_example_module(cache, p, dirs, inserted_elements)

    document.children = (document.children[0:example_heading_index + 1] +
                         inserted_elements +
                         document.children[next_index:])

    with MarkdownRenderer() as renderer:
        with open(args.readme_path, "w") as f:
            f.write(renderer.render(document))


if __name__ == '__main__':
    main()
