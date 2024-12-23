from ezocc import enclosures
from ezocc.alg import joinery
from ezocc.cad.gui.rendering_specifications.rendering_annotation_values import RenderingAnnotationValues
from ezocc.gears import gear_generator
from ezocc.occutils_python import WireSketcher
from ezocc.part_manager import Part, PartFactory
from ezocc.workplane.surface_mapping import SurfaceMapper
from ezocc.gcs_solver.system import System
from ezocc.workplane.workplane import WorkPlane


class PartAnnotationAPI:
    rendering_annotation_values = RenderingAnnotationValues


class API:

    common_part_annotations = PartAnnotationAPI

    """
    Utility class for navigating the api, exposing different tools/packages.
    """
    @staticmethod
    def part(*args, **kwargs) -> Part:
        """
        Core "shape" wrapper component manipulated by other elements of the API.
        """
        return Part(*args, **kwargs)

    @staticmethod
    def part_factory(*args, **kwargs):
        """
        Factory utility class for generating common primitives
        """
        return PartFactory(*args, **kwargs)

    @staticmethod
    def wire_sketcher(*args):
        """
        Sketching tool for laying out edges to form wires and faces.
        """
        return WireSketcher(*args)

    @staticmethod
    def surface_mapper(*args, **kwargs):
        """
        Utility for mapping edges between 2d coordinate systems.
        """
        return SurfaceMapper(*args, **kwargs)

    @staticmethod
    def gcs_system():
        """
        Utility for defining sketch objects and solving their positions based on geometric constraints.
        """
        return System()

    @staticmethod
    def gears() -> gear_generator:
        """
        Package for generation of gear Parts.
        """
        return gear_generator

    @staticmethod
    def enclosures() -> enclosures:
        """
        Package for creation of enclosures (boxes) containing objects.
        """
        return enclosures

    @staticmethod
    def joinery() -> joinery:
        """
        Package for the connection of unconnected faces using lofts etc.
        """
        return joinery

    @staticmethod
    def workplane(*args, **kwargs):
        """
        Class for translation between coordinate systems based on working planes (xy coordinates)
        """
        return WorkPlane(*args, **kwargs)

    @staticmethod
    def svg_parser(*args, **kwargs):
        """
        Class for parsing and conversion of SVG documents to Parts
        """
        return WorkPlane(*args, **kwargs)
