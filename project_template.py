#!/usr/bin/env python3

import logging

from ezocc.part_cache import FileBasedPartCache
from ezocc.part_manager import Part, PartCache, PartFactory
from ezocc.stock_parts.misc import StockParts
from OCC.Core.gp import gp

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)

    cache = FileBasedPartCache("/wsp/cache")
    factory = PartFactory(cache)
    stock_parts = StockParts(cache)

    # put code here


if __name__ == '__main__':
    main()
