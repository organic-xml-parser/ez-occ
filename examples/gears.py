import math

from ezocc.gears.gear_generator import InvoluteGearFactory, GearPairSpec
from ezocc.part_manager import PartFactory, PartCache


TITLE = "Gears"
DESCRIPTION = "Creating a Gear Pair"
FILENAME = "gears"


def build(cache: PartCache):
    factory = PartFactory(cache)
    gears = InvoluteGearFactory(cache).create_involute_gear_pair(
        GearPairSpec.matched_pair(2, 10, 5, clearance=0.5), height=10)

    gears = gears.do_on("pinion", consumer=lambda p: p.tr.rz(math.radians(35), offset=p.sp("center").xts.xyz_mid))

    result = factory.box_surrounding(gears, 3, 3, 1.5).align().by("zmax", gears).bool.cut(
        *[s.extrude.make_thick_solid(1) for s in gears.list_subpart("clearance")]
    )

    shaft = factory.cylinder(1, result.xts.z_span).align().by("zmin", result)

    bull = gears.sp("bull", "body").bool.cut(shaft.align().by("xmidymid", gears.sp("bull", "center")))
    pinion = gears.sp("pinion", "body").bool.cut(shaft.align().by("xmidymid", gears.sp("pinion", "center")))

    return result.add(bull, pinion)
