import math
import typing

import OCC.Core.BOPAlgo
from OCC.Core import Precision
import OCC.Core.gp

from ezocc.occutils_python import WireSketcher
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import Part, PartCache, PartFactory


class HingeGenerator:

    def get_hinge(self,
                  cache: PartCache,
                  model_a: Part,
                  model_b: Part,
                  hinge_center: Part,
                  preload_angle: float):
        raise NotImplementedError()

class CircularHingeGenerator(HingeGenerator):

    def __init__(self, r0: float, r1: float):
        self.r0 = r0
        self.r1 = r1

    def get_hinge(self,
                  cache: PartCache,
                  model_a: Part,
                  model_b: Part, hinge_center: Part,
                  preload_angle: float):
        return PartFactory(cache).ring(r_outer=self.r1, r_inner=self.r0, height=model_a.xts.z_span - Precision.precision.Confusion() * 0.5)\
            .align().by("zmid", model_a)



class CapsuleHingeGenerator(HingeGenerator):
    """
    Creates a hinge which is a capsule with one center on the com of the models and another at the
    specified rotation point.
    """

    def __init__(self, r0: float, r1: float):
        self.r0 = r0
        self.r1 = r1

    def get_hinge(self,
                  cache: PartCache,
                  model_a: Part,
                  model_b: Part,
                  hinge_center: Part,
                  preload_angle: float):
        factory = PartFactory(cache)

        model_com = model_a.add(model_b).inspect.com()

        com_distance = model_com.cast.get_distance_to(hinge_center)

        result = factory.capsule(center_distance=com_distance, diameter=self.r1 * 2)\
            .bool.cut(factory.capsule(center_distance=com_distance, diameter=self.r0 * 2))\
            .align().by("xmaxymid", hinge_center)\
            .tr.mv(dx=self.r1 / 2)\
            .extrude.prism(dz=model_a.xts.z_span - Precision.precision.Confusion() * 0.5)\
            .make.solid()\
            .align().by("zmid", model_a)

        result_top = result.bool.common(factory.box_surrounding(result).align().by("yminmid", result))
        result_bottom = result.bool.common(factory.box_surrounding(result).align().by("ymaxmid", result))

        result_top = result_top.tr.rz(math.radians(-preload_angle / 2), offset=hinge_center.xts.xyz_mid)
        result_bottom = result_bottom.tr.rz(math.radians(preload_angle / 2), offset=hinge_center.xts.xyz_mid)

        result = result_top.bool.union(result_bottom)\
            .cleanup()\
            .tr.rz(
                math.atan2(hinge_center.xts.y_mid - model_com.xts.y_mid, hinge_center.xts.x_mid - model_com.xts.x_mid),
                offset=hinge_center.xts.xyz_mid)

        return result


class LivingHingeFactory:

    def __init__(self, cache: PartCache):
        self._cache = cache
        self._factory = PartFactory(cache)

    def create_living_hinge(self,
                            model_a: Part,
                            model_b: Part,
                            hinge_center_point: typing.Tuple[float, float, float],
                            preload_angle: float,
                            hinge_selector: typing.Callable[[Part], Part] = None,
                            hinge_generator: HingeGenerator = None):
        """
        Create a living hinge on two models in the xy plane. Models are assumed to have the same z min/max

        The hinge is cut by the models and the outer element selected via hinge_selector. If no hinge_selector
        is specified the default behavior is to pick the hinge furthest from the com of the models. This is usually
        the expected placement for a hinge

        @param hinge_selector:
        @param model_a:
        @param model_b:
        @param hinge_center_point:
        @param preload_angle:
        @param hinge_generator
        @return:
        """
        if not model_a.inspect.is_solid() or not model_b.inspect.is_solid():
            raise ValueError("Input models must be solids")

        if hinge_selector is None:
            com = model_a.add(model_b).inspect.com()
            hinge_selector = lambda p: p.explore.solid.get_max(lambda s: s.cast.get_distance_to(com))

        hinge_center = self._factory.vertex(*hinge_center_point)

        model_a.cleanup.build_curves_3d()
        model_b.cleanup.build_curves_3d()

        # precision confusion hack is a bit annoying but is a workaround for cutting complex objects
        hinge = hinge_generator.get_hinge(self._cache, model_a, model_b, hinge_center, preload_angle)

        # apply the preload rotation to the models
        model_a = model_a.tr.rz(math.radians(-preload_angle / 2), offset=hinge_center.xts.xyz_mid)\
            .cleanup(fix_small_face=True, concat_b_splines=True)\
            .cleanup.fix_solid()
        model_b = model_b.tr.rz(math.radians(preload_angle / 2), offset=hinge_center.xts.xyz_mid)\
            .cleanup(fix_small_face=True, concat_b_splines=True)\
            .cleanup.fix_solid()

        hinge = hinge.cleanup.build_curves_3d().bool.cut(model_a, model_b).cleanup()
        hinge = hinge_selector(hinge)

        return self._factory.compound(
            model_a.name("model_a"),
            model_b.name("model_b"),
            hinge.name("hinge"))
