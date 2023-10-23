import OCC.Core.TopoDS
import OCC.Core.gp
import OCC.Core.BRepPrimAPI
import occutils

import occutils_python


class ScrewHeadFactory:

    def get_shape(self):
        raise NotImplementedError()


class CounterboreScrewHeadFactory(ScrewHeadFactory):

    def __init__(self, head_diameter: float, head_length: float, clearance: float, recess_depth: float = 0):
        self.head_diameter = head_diameter
        self.head_length = head_length
        self.clearance = clearance
        self.recess_depth = recess_depth

    def get_shape(self) -> OCC.Core.TopoDS.TopoDS_Shape:
        ws = occutils.WireSketcher(OCC.Core.gp.gp_Pnt(-self.recess_depth, 0, 0))
        ws.lineToY(self.head_diameter / 2 + self.clearance)
        ws.lineToX(self.head_length + self.clearance)
        ws.lineToY(0)
        ws.close()

        return OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeRevol(ws.getFace(), OCC.Core.gp.gp_OX(), True).Shape()


class ScrewShankFactory:

    def __init__(self, shank_diameter: float, shank_length: float, clearance: float):
        self.shank_diameter = shank_diameter
        self.shank_length = shank_length
        self.clearance = clearance

    def get_shape(self) -> OCC.Core.TopoDS.TopoDS_Shape:
        ws = occutils.WireSketcher(OCC.Core.gp.gp_Pnt(0, 0, 0))
        ws.lineToY(self.shank_diameter / 2 + self.clearance)
        ws.lineToX(self.shank_length)
        ws.lineToY(0)
        ws.close()

        return OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeRevol(ws.getFace(), OCC.Core.gp.gp_OX(), True).Shape()


class ScrewFactory:

    def __init__(self):
        self.head_profiles = []
        self.shank_profiles = []

    def add_head_profile(self, head_factory: ScrewHeadFactory):
        self.head_profiles.append(head_factory)
        return self

    def add_shank_profile(self, shank_factory: ScrewShankFactory):
        self.shank_profiles.append(shank_factory)
        return self

    def get_shape(self, should_cleanup: bool = True) -> OCC.Core.TopoDS.TopoDS_Shape:
        if len(self.shank_profiles) == 0:
            raise ValueError("Must specify at least one shank profile.")

        result = occutils_python.BoolUtils.incremental_fuse([s.get_shape() for s in self.shank_profiles])

        if len(self.head_profiles) > 0:
            head = occutils_python.BoolUtils.incremental_fuse([s.get_shape() for s in self.head_profiles])
            result = occutils_python.BoolUtils.incremental_fuse([ result, head ])

        if should_cleanup:
            result = occutils_python.Cleanup.simplify_domain(result)

        return result
