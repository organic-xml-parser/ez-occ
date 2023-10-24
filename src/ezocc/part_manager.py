from __future__ import annotations

import copy
import inspect
import json
import math
import pdb
import re
import traceback
import typing
import os

import OCC
import OCC.Core.Addons
import OCC.Core.BOPAlgo
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepCheck
import OCC.Core.BRepFilletAPI
import OCC.Core.BRepOffset
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepExtrema
import OCC.Core.BRepPrimAPI
import OCC.Core.BRepLib
import OCC.Core.BOPAlgo
import OCC.Core.BRep
import OCC.Core.BRepTools as BRepTools
import OCC.Core.GeomAbs
import OCC.Core.GC
import OCC.Core.GCE2d
import OCC.Core.Geom
import OCC.Core.Geom2d
import OCC.Core.GeomAPI
import OCC.Core.ShapeAnalysis
import OCC.Core.ShapeFix
import OCC.Core.ShapeUpgrade
import OCC.Core.TopAbs as ta
import OCC.Core.TopOpeBRepBuild
import OCC.Core.TopTools
import OCC.Core.TopoDS
import OCC.Core.gp
import OCC.Core.gp as gp
import parsimonious
from OCC.Core import Precision
from OCC.Core.Geom import Geom_Surface, Geom_CylindricalSurface, Geom_ConicalSurface
from OCC.Core.Message import Message_Gravity, Message_ProgressIndicator
from OCC.Core._TopAbs import TopAbs_WIRE, TopAbs_EDGE
from parsimonious import Grammar
import importlib

import ezocc.occutils_python as op

import logging
import io
import pickle
import uuid
import copyreg

from ezocc.humanization import Humanize
from ezocc.subshape_mapping import SubshapeMap, T_MKS, AnnotatedShape

import ocaf_wrapper_swig
from util_wrapper_swig import UtilWrapper

from ezocc.type_utils import TypeValidator

logger = logging.getLogger(__name__)


class CacheToken:

    def compute_uuid(self) -> str:
        raise NotImplementedError()

    def mutated(self, *args, **kwargs) -> CacheToken:
        raise NotImplementedError()

    def get_cache(self) -> PartCache:
        """
        @return: The cache associated with this token.
        """
        raise NotImplementedError()


class NoOpCacheToken(CacheToken):

    def __init__(self, cache = None):
        if cache is None:
            cache = NoOpPartCache.instance()

        self._cache = cache

    def compute_uuid(self) -> str:
        raise NotImplementedError("This cache token is NoOp. It does not support computing UUIDS. "
                                  "This is intended to be used with a NoOp part cache.")

    def mutated(self, *args, **kwargs) -> CacheToken:
        return NoOpCacheToken(self._cache)

    def get_cache(self) -> PartCache:
        return self._cache


class PartCache:

    def create_token(self, *args, **kwargs):
        """
        Request a new token from the cache, representing the given parameters.
        """
        raise NotImplementedError()

    def ensure_exists(self, cache_token: CacheToken, factory_method: typing.Callable[[], Part]) -> Part:
        """
        @return: either a loaded part from storage, or the part provided by the given factory method.
        UUID consistency from input cache_token and part cache token is checked.
        """
        raise NotImplementedError()


class NoOpPartCache(PartCache):
    """
    NoOp implementation that performs no persistence operations. ensure_exists is guaranteed to generate a new part
    every time
    """

    __instance = None

    __init_key = object()

    @staticmethod
    def instance() -> NoOpPartCache:
        if NoOpPartCache.__instance is None:
            NoOpPartCache.__instance = NoOpPartCache(NoOpPartCache.__init_key)

        return NoOpPartCache.__instance

    def __init__(self, init_key=None):
        if init_key != NoOpPartCache.__init_key:
            raise ValueError("Use static instance() method instead")

    def create_token(self, *args, **kwargs):
        return NoOpCacheToken(self)

    def ensure_exists(self, cache_token: CacheToken, factory_method: typing.Callable[[], Part]) -> Part:
        return factory_method()


class PartDriver:

    def __init__(self, part: Part):
        self._part = part

    @property
    def part(self) -> Part:
        return self._part


class PartPredicate:
    """
    Shorthand to indicate a boolean part filter.
    """

    def __call__(self, part: Part) -> bool:
        raise NotImplementedError()


class Part:

    @staticmethod
    def of_shape(shape: OCC.Core.TopoDS.TopoDS_Shape):
        return Part(NoOpCacheToken(), SubshapeMap(AnnotatedShape(shape)))

    def __init__(self, cache_token: CacheToken, subshape_map: SubshapeMap):
        if not isinstance(cache_token, CacheToken):
            raise ValueError("Cache token missing")

        if not isinstance(subshape_map, SubshapeMap):
            raise ValueError("Subshape map expected")

        self._extents = None
        self._driver: typing.Optional[PartDriver] = None
        self._cache_token = cache_token
        self._subshapes = subshape_map.clone().pruned()

    TDriver = typing.TypeVar("TDriver")

    def driver(self, expected_driver_cls: TDriver.__class__) -> TDriver:
        """
        Instantiates the driver attached to this part, and verifies that it matches the expected driver class.
        """

        if self._driver is not None:
            return self._driver

        if "driver" not in self.annotations:
            raise ValueError("This Part does not have an associated driver")

        driver_module, driver_cls = json.loads(self.annotation("driver"))
        module = importlib.import_module(driver_module)

        actual_driver_cls = module
        for substr in driver_cls.split('.'):
            actual_driver_cls = getattr(actual_driver_cls, substr)

        if expected_driver_cls != actual_driver_cls:
            raise ValueError("Expected driver class does not match actual")

        driver = actual_driver_cls(self)

        if not isinstance(driver, PartDriver):
            raise ValueError("Instantiated Driver is not a subclass of PartDriver")

        self._driver = driver

        return self._driver

    def with_driver(self, driver_cls) -> Part:
        if not issubclass(driver_cls, PartDriver):
            raise ValueError("Drivers should subclass PartDriver")

        return self.annotate(
            "driver",
            json.dumps((inspect.getmodule(driver_cls).__name__, driver_cls.__qualname__)))

    @property
    def annotations(self) -> typing.Dict[str, str]:
        return self._subshapes.root_shape.attributes.values

    def annotate(self, attribute_name: str, attribute_value: str) -> Part:
        """
        @return: a new part with this part's root shape annotated with the specified annotation. Existing annotations
        are overwritten.
        """
        return Part(
            self._cache_token.mutated("part", "annotated", attribute_name, attribute_value),
            self._subshapes.with_updated_root_shape(
                self._subshapes.root_shape.with_updated_attribute(attribute_name, attribute_value)))

    def clear_annotations(self):
        new_map = SubshapeMap(AnnotatedShape(self.shape), self._subshapes.map)

        return Part(
            self._cache_token.mutated("part", "clear_annotations"),
            new_map)

    def annotate_subshape(self, subshape_name: str, attribute: typing.Tuple[str, str]):
        new_subshape_map = self._subshapes.clone()
        new_subshape_map.annotate_subshape(subshape_name, *attribute)

        return Part(
            self._cache_token.mutated("part", "annotate_subshape", subshape_name, attribute),
            new_subshape_map)

    def annotate_subshapes(self, subshape_name: str, attribute: typing.Tuple[str, str]):
        new_subshape_map = self._subshapes.clone()
        new_subshape_map.annotate_subshapes(subshape_name, *attribute)

        return Part(
            self._cache_token.mutated("part", "annotate_subshape", subshape_name, attribute),
            new_subshape_map)

    def annotation(self, attribute_name: str) -> str:
        return self._subshapes.root_shape.attributes.get(attribute_name)

    def pruned(self) -> Part:
        """
        :return: A Part with identical root shape, and subshape map with any parts that are not
        in the object hierarchy of the root shape removed. e.g. orphaned faces/edges that no longer
        belong to the root shape.
        """

        return Part(self.cache_token.mutated("pruned"), self._subshapes.pruned())

    @property
    def cache_token(self) -> CacheToken:
        return self._cache_token

    def with_cache_token(self, new_cache_token: CacheToken):
        """
        Returns a new part with the specified cache token value. Prefer this over setting _cache_token directly.
        """
        return Part(new_cache_token, self._subshapes)

    def map_subshape_changes(
            self,
            new_cache_token: CacheToken,
            new_shape: OCC.Core.TopoDS.TopoDS_Shape,
            mks: T_MKS,
            map_is_partner: bool = False,
            map_is_same: bool = False) -> Part:

        if new_shape is None:
            raise ValueError("Shape must be non-null")

        return Part(new_cache_token,
                    self._subshapes.map_subshape_changes(
                        self._subshapes.root_shape.with_updated_shape(new_shape),
                        mks,
                        map_is_partner,
                        map_is_same))

    def raise_exception(self) -> Part:
        """
        This method never returns. Instead, it raises a RuntimeError. This can be used to halt project execution without
        having to comment out large chunks of code.
        """
        raise RuntimeError("Run cancelled")

    @property
    def validate(self):
        return PartValidate(self)

    def preview(self, *preview_with: Part, **kwargs) -> Part:
        Part.visualize(self, *preview_with, **kwargs)
        return self

    def print_recursive(self) -> Part:

        def print_subshapes(shape, indent_level = 0):
            shape_rep: str = str(shape)

            if shape.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE:
                shape_rep += f" ({Humanize.curve_type(op.InterrogateUtils.curve_type(shape))})"

            print("    " * indent_level, shape_rep + " " + str(id(shape)))
            for s in op.InterrogateUtils.traverse_direct_subshapes(shape):
                print_subshapes(s, indent_level + 1)

        print_subshapes(self._subshapes.root_shape.shape)

        return self

    def __repr__(self):
        return f"({self._cache_token} {self.shape})"

    def __str__(self):
        root_shape = self._subshapes.root_shape

        result = (str(root_shape) + "\n    ")
        result += f"token {self._cache_token}\n    "
        result += '\n    '.join(str(op.SetPlaceableShape(s)) + " " + str(id(s))
                                for s in op.InterrogateUtils.traverse_direct_subshapes(root_shape.set_placeable_shape.shape))

        result += "    \n"

        result += ''.join("\n    " + str(n) + ": " + str(s) for n, s in self.subshapes.map.items())

        result += f"\nBBox: xyz_span{self.extents.xyz_span} xyz_min:{self.extents.xyz_min} - xyz_max{self.extents.xyz_max}\n"

        return result

    def print(self, title: str = None) -> Part:
        """
        Print a debug description of the part/partmap
        """
        if title is not None:
            print(title + ':')

        print(str(self))
        print()

        return self

    def name(self, name: str) -> Part:
        """
        Returns a new Part with this Part's root shape, and the subshape map containing the root shape
        Renamed to name. Note that the existing name will be removed, if it exists.
        :param name:
        :return:
        """
        new_subshapes = self._subshapes.clone()

        root_shape = new_subshapes.root_shape

        if new_subshapes.contains_shape(root_shape):
            new_subshapes.remove(root_shape)

        new_subshapes.place(name, root_shape)

        return Part(self._cache_token.mutated("name", name), new_subshapes)

    def name_subshape(self, subshape_part: Part, name: str) -> Part:
        # todo: how should we handle attributes here? perhaps not accept a part but TopoDS_Shape

        if not isinstance(subshape_part, Part):
            raise ValueError("Expected Part")

        if not any(op.SetPlaceableShape(s) == subshape_part.subshapes.root_shape.set_placeable_shape
                   for s in op.InterrogateUtils.traverse_all_subshapes(self._subshapes.root_shape.set_placeable_shape.shape)):
            raise ValueError("Subshape does not belong to part. Consider add() instead.")

        new_subshapes = self._subshapes.clone()
        new_subshapes.place(name, AnnotatedShape(subshape_part._subshapes.root_shape.set_placeable_shape))

        return Part(self._cache_token.mutated("name_subshape", subshape_part), new_subshapes)

    def name_recurse(self,
                     name: str,
                     subshape_filter: typing.Callable[[OCC.Core.TopoDS.TopoDS_Shape], bool] = None) -> Part:
        """
        Adds a subshape name for all shapes accepted by filter
        :param name: new name for the shape tree
        :param subshape_filter: filter to e.g. decide which types to include
        :return:
        """

        new_subshape_map = self._subshapes.clone()
        new_subshape_map.remove(self._subshapes.root_shape)

        if subshape_filter is None:
            subshape_filter = lambda _: True

        if subshape_filter(new_subshape_map.root_shape.shape):
            new_subshape_map.place(name, self._subshapes.root_shape)

        for s in op.InterrogateUtils.traverse_all_subshapes(self.shape):
            if subshape_filter(s):
                new_subshape_map.place(name, AnnotatedShape(s))

        return Part(self._cache_token.mutated("name_recurse", name, inspect.getsource(subshape_filter)), new_subshape_map)

    def remove(self, *subparts: Part):
        """
        Removes the specified subparts from the part tree.
        Requires that all subpart are direct child element of this part.
        """
        if self.shape.ShapeType() != OCC.Core.TopAbs.TopAbs_COMPOUND:
            raise ValueError("Only works on direct child elements of compounds")

        direct_subshapes = [op.SetPlaceableShape(s) for s in
                            op.InterrogateUtils.traverse_direct_subshapes(self.shape)]

        for subpart in subparts:
            if op.SetPlaceableShape(subpart.shape) not in direct_subshapes:
                raise ValueError("Subpart does not appear to belong to this compound. Perhaps it is at a deeper "
                                 f"level in the hierarchy:"
                                 f"\n"
                                 f"THIS:\n"
                                 f"{self}"
                                 f"\n"
                                 f"SUBPART\n"
                                 f" {subpart}")

        # the direct subshapes that will be kept
        direct_subshapes = [s for s in direct_subshapes if all(s != subpart for subpart in subparts)]
        new_subshape_maps = [self._subshapes.with_updated_root_shape(s.shape).pruned() for s in direct_subshapes]

        builder = OCC.Core.BRep.BRep_Builder()
        result_shape = OCC.Core.TopoDS.TopoDS_Compound()

        builder.MakeCompound(result_shape)
        for s in direct_subshapes:
            builder.Add(result_shape, s.shape)

        result = self._subshapes.root_shape.with_updated_shape(result_shape)

        new_subshapes = SubshapeMap(result)
        for subshape_map in new_subshape_maps:
            new_subshapes.merge(subshape_map)

        if self._subshapes.contains_shape(self._subshapes.root_shape):
            new_subshapes.place(
                self._subshapes.name_for_shape(self._subshapes.root_shape), result)

        # reconstruct this shape as a compound minus 1 element
        return Part(
            self._cache_token.mutated("remove", *subparts),
            self._subshapes.with_updated_root_shape(result))

    def do_on(self,
              *names: str,
              consumer: typing.Callable[[Part], Part] = None,
              part_filter: PartPredicate = None) -> Part:
        if len(names) == 0:
            raise ValueError("At least one name required")

        if consumer is None:
            raise ValueError("A consumer must be specified")

        if len(names) == 1:
            name = names[0]
            subpart = self.single_subpart(name, part_filter=part_filter)
            modified_subpart = consumer(subpart)

            return self.remove(subpart).insert(modified_subpart.name(name))
        else:
            return self.do_on(names[0],
                              part_filter=part_filter,
                              consumer=lambda p: p.do_on(*names[1:], consumer=consumer, part_filter=part_filter))

    def do(self, consumer: typing.Callable[[Part], Part]) -> Part:
        """
        Applies the consumer to this part and returns the result.
        :param consumer:
        :return:
        """
        return consumer(self)

    def do_and_add(self, part_modifier: typing.Callable[[Part], Part]) -> Part:
        """
        Applies the consumer to this part, and adds the result using the add method.
        :param part_modifier:
        :return:
        """
        return self.add(part_modifier(self))

    def insert(self, *others) -> Part:
        """
        Only supported on compound parts. Will add the supplied parts to this part directly. The result will be the same
        compound, with the supplied parts added as direct subshapes.
        :return:
        """

        if not self.inspect.is_compound():
            raise ValueError("Can only insert subparts to compound")

        builder = OCC.Core.BRep.BRep_Builder()

        result_shape = OCC.Core.TopoDS.TopoDS_Compound()
        builder.MakeCompound(result_shape)

        for s in op.InterrogateUtils.traverse_direct_subshapes(self.shape):
            builder.Add(result_shape, s)

        for other in others:
            builder.Add(result_shape, other.shape)

        result = self._subshapes.root_shape.with_updated_shape(result_shape)

        new_subshape_list = self._subshapes.with_updated_root_shape(result)

        for other in others:
            for name, shapes in other.subshapes.map.items():
                for s in shapes:
                    new_subshape_list.place(name, s)

        return Part(self._cache_token.mutated("insert", *others), new_subshape_list)

    def add(self, *others) -> Part:
        """
        Creates a new part equal to this one, with the other parts added also.
        Subshape maps are merged, and the root shapes are combined using a compound.
        :param others:
        :param sublabel:
        :return:
        """

        builder = OCC.Core.BRep.BRep_Builder()
        result_shape = OCC.Core.TopoDS.TopoDS_Compound()

        builder.MakeCompound(result_shape)
        builder.Add(result_shape, self._subshapes.root_shape.set_placeable_shape.shape)

        for other in others:
            builder.Add(result_shape, other.shape)

        result = AnnotatedShape(result_shape)
        new_subshape_list = self._subshapes.with_updated_root_shape(result)

        for other in others:
            for name, shapes in other.subshapes.map.items():
                for s in shapes:
                    new_subshape_list.place(name, s)

        return Part(self._cache_token.mutated("add", *others), new_subshape_list)

    def pattern(self, range_supplier: typing.Iterable[int], part_modifier: typing.Callable[[int, Part], Part]) -> Part:
        """
        Iterates over the supplied range, adding the result parts.
        part_modifier is provided with this part instance.
        :param range_supplier: provides indices.
        :param part_modifier: modifies the original part according to the index.
        :return: this Part modified according to modifier and i for all i in range
        """
        results = []
        for i in range_supplier:
            results.append(part_modifier(i, self))

        return PartFactory(self._cache_token.get_cache()).compound(*results)

    def incremental_pattern(self, range_supplier: typing.Iterable[int], part_modifier: typing.Callable[[Part], Part]) -> Part:
        result = [self]

        for i in range_supplier:
            result.append(part_modifier(result[-1]))

        return PartFactory.compound(*result)

    @staticmethod
    def visualize(*parts):
        if len(parts) == 0:
            raise ValueError("No arguments. Did you mean to call non-static method preview()?")

        import ezocc.cad.gui.visualization as pv

        pv.visualize_parts(*parts)

    def align(self, *subshape_names: str) -> PartAligner:
        return PartAligner(self, *subshape_names)

    @property
    def extents(self) -> op.Extents:
        """
        :return: the occutils_python.Extents for this Part's root shape.
        """

        if self._extents is None:
            self._extents = op.Extents(self._subshapes.root_shape.set_placeable_shape.shape)

        return self._extents

    @property
    def xts(self) -> op.Extents:
        return self.extents

    @property
    def shape(self) -> OCC.Core.TopoDS.TopoDS_Shape:
        """
        :return: this Parts root shape
        """
        return self._subshapes.root_shape.set_placeable_shape.shape

    @property
    def set_placeable_shape(self) -> op.SetPlaceableShape:
        """
        :return: this Parts root shape
        """
        return self._subshapes.root_shape.set_placeable_shape

    @property
    def array(self) -> PartArray:
        return PartArray(self)

    @property
    def save(self) -> PartSave:
        return PartSave(self)

    @property
    def explore(self) -> PartExplore:
        return PartExplore(self)

    @property
    def query(self) -> PartQuery:
        return PartQuery(self, True)

    @property
    def query_shapes(self) -> PartQuery:
        return PartQuery(self, False)

    @property
    def transform(self) -> PartTransformer:
        return PartTransformer(self)

    @property
    def tr(self) -> PartTransformer:
        return self.transform

    @property
    def bool(self):
        return PartBool(self)

    @property
    def mirror(self) -> PartMirror:
        return PartMirror(self)

    @property
    def extrude(self):
        return PartExtruder(self)

    @property
    def loft(self):
        return PartLoft(self)

    @property
    def revol(self):
        return PartRevol(self)

    @property
    def make(self):
        return PartMake(self)

    @property
    def pick(self):
        return PartPick(self)

    @property
    def cast(self):
        return PartCast(self)

    @property
    def subshapes(self) -> SubshapeMap:
        """
        :return: All the named subshapes for this Part. Note that named subshapes may not necessarily
        belong to the root shape, in terms of the OCC data structures. Use the #prune method to remove
        orphaned subshapes.
        """

        # clone takes a performance hit but is safer
        return self._subshapes.clone()

    def compound_subpart(self, name: str, part_filter: PartPredicate = None) -> Part:
        """
        :return: A new Part, with root shape as a compound of all subshapes that have the specified name.
        Note that the subshape map is unaltered.
        """
        subshapes = self._subshapes.get(name)
        subshapes = [Part.of_shape(s.shape).name(name) for s in subshapes]

        if part_filter is not None:
            subshapes = [s for s in subshapes if part_filter(s)]

        subshape = PartFactory(self._cache_token.get_cache()).compound(*[s for s in subshapes]).shape

        return Part(self._cache_token.mutated("compound_subpart", name),
                    self._subshapes.with_updated_root_shape(subshape))

    def list_subpart(self, name: str) -> typing.List[Part]:
        subshapes = self._subshapes.get(name)
        return [Part(self._cache_token.mutated(s), self._subshapes.with_updated_root_shape(s)) for s in subshapes]

    def sp(self, *names, part_filter: PartPredicate = None) -> Part:
        return self.single_subpart(*names, part_filter=part_filter)

    def single_subpart(self, *names: str, part_filter: PartPredicate = None) -> Part:
        """
        Ensures that a single subshape exists with given name, and returns a Part with it as the root shape.
        subshape map is unaltered.

        Note the one subshape returned may be a compound. However this method ensures that no more than one shape
        with the specified name is present in the subshape map.

        @param part_filter an optional filter to e.g. restrict the type of part returned
        """
        if len(names) == 0:
            raise ValueError("At least one name must be specified")

        name = names[0]

        subshapes = self._subshapes.get(name)

        if part_filter is not None:
            subshapes = [s for s in subshapes if part_filter(
                Part(self.cache_token.mutated(s.shape), self.subshapes.with_updated_root_shape(s.shape))
            )]

        if len(subshapes) != 1:
            raise ValueError(f"Could not reduce the subshape query {names}, with part_filter={part_filter} to a single element "
                             f"(got {len(subshapes)})")

        subshape = next(s for s in subshapes)

        new_subshape_map = self.subshapes.with_updated_root_shape(subshape)

        result = Part(self._cache_token.mutated("single_subpart", name), new_subshape_map)

        if len(names) > 1:
            return result.single_subpart(*names[1:])
        else:
            return result

    def prefixed_subparts(self, prefix: str, trim_prefix: bool = True) -> Part:
        """
        Returns a new Part consisting of a compound of all shapes with the specified prefix. If trim_prefix is true, the
        prefix will be removed from all parts in the shape map.
        """
        def get_new_label(label: str):
            if label.startswith(prefix) and trim_prefix:
                return label[len(prefix):]
            else:
                return label

        prefixed_parts = []
        new_subshape_map: typing.Dict[str, typing.Set[AnnotatedShape]] = dict()
        for s_label, s_set in self.subshapes.map.items():
            if s_label.startswith(prefix):
                prefixed_parts += [s for s in s_set]
                new_subshape_map[get_new_label(s_label)] = s_set
            else:
                new_subshape_map[s_label] = s_set

        new_shape = AnnotatedShape(op.GeomUtils.make_compound(*[s.set_placeable_shape.shape for s in prefixed_parts]))

        return Part(self._cache_token.mutated("prefixed_subparts", prefix, trim_prefix),
                    SubshapeMap(new_shape, new_subshape_map))

    def subpart(self, prefix: str, trim_prefix: bool = True) -> Part:
        """
        __Deprecated!__ use "prefixed_subpart" instead

        Returns a new Part, whith the same root shape, however the subshape map is culled according to prefix.
        Only entries in the subshape map with the specified prefix are preserved.
        :trim_prefix: if True (default) the prefixes are removed from the subshapes in the result part.
        """

        new_subshapes: typing.Dict[str, typing.Set[op.SetPlaceableShape]] = dict()
        for subshape_label, subshapes in self.subshapes.map.items():
            if subshape_label.startswith(prefix):
                trimmed_subshape_label = subshape_label[len(prefix):] if trim_prefix else subshape_label

                new_subshapes[trimmed_subshape_label] = subshapes

        return Part(self._cache_token.mutated("subpart", prefix, trim_prefix),
                    self._shape,
                    SubshapeMap(self._shape, new_subshapes))

    @property
    def sew(self):
        return PartSew(self)

    @property
    def fillet(self):
        return PartFilleter(self)

    @property
    def cleanup(self) -> PartCleanup:
        return PartCleanup(self)

    @property
    def inspect(self) -> PartInspect:
        return PartInspect(self)

    def rename_subshape(self, src_name: str, dst_name: str):
        """
        Checks that the dst_name is free, and renames all subshapes with src_name to dst_name
        :return: a new Part with updated subshape map
        """

        updated_subshapes = self._subshapes.clone()
        updated_subshapes.rename(src_name, dst_name)

        return Part(self._cache_token.mutated("rename_subshape", "src_name", "dst_name"), self.shape, updated_subshapes)

    def perform_make_shape(self,
                           new_cache_token: CacheToken,
                           mks: typing.Union[
                               OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeShape,
                               OCC.Core.BRepOffset.BRepOffset_MakeOffset],
                           **kwargs) -> Part:
        """
        Applies a generic makeshape/offset to this Part and returns a new one with updated subshape maps.
        """

        if not mks.IsDone():
            if isinstance(mks, OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeShape):
                mks.Check()
                raise ValueError("Make Shape error.")
            else:
                raise ValueError("Make Offset error: " + OCC.Core.BRepOffset.BRepOffset_Error(mks.Error()).name)

        shape = mks.Shape()

        if shape is None:
            raise ValueError("MakeShape result is None")

        return self.map_subshape_changes(new_cache_token, shape, mks)


class LazyLoadedPart(Part):

    # noinspection PyMissingConstructor
    def __init__(self, cache_token: CacheToken, load_method: typing.Callable[[], Part]):
        self._cache_token = cache_token
        self._load_method = load_method
        self._part = None

    @property
    def cache_token(self) -> CacheToken:
        return self._cache_token

    def __getattr__(self, item):
        if item == "cache_token":
            return self._cache_token

        if self._part is None:
            logger.info(f"Loading lazy part: {self._cache_token.compute_uuid()} for attribute {item}")
            self._part = self._load_method()

        return getattr(self._part, item)


class PartSew:

    def __init__(self, part: Part):
        self._part = part

    def __call__(self, *args, **kwargs):
        token = self._part.cache_token.mutated("sew", "all")

        sew = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_Sewing()
        sew.Add(self._part.shape)

        sew.Perform()

        sewed_shape = sew.SewedShape()

        return self._part.map_subshape_changes(token, sewed_shape, mks=sew.GetContext().History())

    def faces(self) -> Part:
        token = self._part.cache_token.mutated("sew", "faces")

        sew = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_Sewing()
        for f in self._part.explore.face.get():
            sew.Add(f.shape)

        sew.Perform()

        sewed_shape = sew.SewedShape()

        return self._part.map_subshape_changes(token, sewed_shape, mks=sew.GetContext().History())

    def edges(self) -> Part:
        token = self._part.cache_token.mutated("sew", "edges")

        sew = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_Sewing()
        for f in self._part.explore.edge.get():
            sew.Add(f.shape)

        sew.Perform()

        return self._part.map_subshape_changes(token, sew.SewedShape(), mks=sew.GetContext().History())


class PartValidate:

    def __init__(self, part: Part):
        self._part = part

    def __call__(self, preview_invalid: bool = True) -> Part:
        analyzer = OCC.Core.BRepCheck.BRepCheck_Analyzer(self._part.shape)
        analyzer.Init(self._part.shape)

        invalid_shapes = {}

        if not analyzer.IsValid():
            for subshape in op.InterrogateUtils.traverse_all_subshapes(self._part.shape):
                statuses = [s for s in op.ListUtils.consume_ncollst(analyzer.Result(subshape).Status())]
                statuses = [s for s in statuses if s != OCC.Core.BRepCheck.BRepCheck_Status.BRepCheck_NoError]
                statuses = [OCC.Core.BRepCheck.BRepCheck_Status(s).name for s in statuses]

                if len(statuses) != 0:
                    invalid_shapes[op.SetPlaceableShape(subshape)] = statuses

            error_str = "Part shape is not valid:\n" + \
                        '\n'.join([str(k.shape) + ": " + str(s) for k, s in invalid_shapes.items()])

            if preview_invalid:
                invalid = Part(op.GeomUtils.make_compound(*[s.shape for s in invalid_shapes.keys()]))

                logger.error(error_str)

                invalid.align().x_min_to_max(self._part).add(self._part).preview()

            raise ValueError(error_str)

        return self._part


class PartInspect:

    def __init__(self, part: Part):
        self._part = part

    def is_face(self) -> bool:
        return self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE

    def is_compound(self) -> bool:
        return self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_COMPOUND

    def is_compsolid(self) -> bool:
        return self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_COMPSOLID

    def is_solid(self) -> bool:
        return self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_SOLID

    def is_shell(self) -> bool:
        return self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_SHELL

    def is_wire(self) -> bool:
        return self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_WIRE

    def is_edge(self) -> bool:
        return self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE

    def is_vertex(self) -> bool:
        return self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_VERTEX

    def contains(self, other: typing.Union[Part, OCC.Core.TopoDS.TopoDS_Shape]) -> bool:
        if isinstance(other, Part):
            other = other.shape

        other = op.SetPlaceableShape(other)

        for s in op.InterrogateUtils.traverse_all_subshapes(self._part.shape):
            if op.SetPlaceableShape(s) == other:
                return True

        return False

    def face_normal(self, **kwargs) -> typing.Tuple[
            typing.Tuple[float, float, float],
            typing.Tuple[float, float, float]]:

        point, direction = op.InterrogateUtils.face_normal(self._part.make.face().shape, **kwargs)

        return (
            (point.X(), point.Y(), point.Z()),
            (direction.X(), direction.Y(), direction.Z())
        )

    def outer_wire(self) -> Part:
        if self._part.inspect.is_face():
            return self._part.explore.wire.get()[0].inspect.outer_wire()

        shape = op.InterrogateUtils.outer_wire(self._part.shape)

        return Part(self._part.cache_token.mutated("inspect", "outer_wire"),
                    self._part.subshapes.with_updated_root_shape(shape))

    def com(self) -> Part:
        com = op.InterrogateUtils.center_of_mass(self._part.shape)

        return PartFactory(self._part.cache_token.get_cache())\
            .vertex(*com)\
            .with_cache_token(self._part.cache_token.mutated("inspect", "com"))


class PartSave:

    def __init__(self, part: Part):
        self._part = part

    def step(self, name: str, **kwargs) -> Part:
        filename = f"{name}.step"
        op.IOUtils.save_shape_step(self._part.shape, filename, **kwargs)

    def single_stl(self, name: str, **kwargs) -> Part:
        filename = f"{name}.stl"
        logger.debug(f"Writing {filename}")
        op.IOUtils.save_shape_stl(self._part.shape, filename, **kwargs)
        return self._part

    def stl_solids(self, name: str, **kwargs) -> Part:
        for i, s in enumerate(self._part.explore.solid.get()):
            filename = f"{name}-{i}.stl"
            logger.debug(f"Writing {filename}")
            op.IOUtils.save_shape_stl(s.shape, filename, **kwargs)

        return self._part

    @staticmethod
    def _validate_ocaf_path(path: str):
        if os.path.splitext(path)[1] != '':
            raise ValueError("Supplied path should not contain an extension")

    def ocaf(self, path: str) -> None:
        PartSave._validate_ocaf_path(path)
        path = path + ".part"

        part = self._part

        w = ocaf_wrapper_swig.OcafWrapper(path)

        w.setUUID(self._part.cache_token.compute_uuid())

        w.setRootShape(part._subshapes.root_shape.set_placeable_shape.shape,
                       json.dumps(part._subshapes.root_shape.attributes.values))

        for name, subshapes in part.subshapes.items():
            for s in subshapes:
                w.appendShape(name, s.set_placeable_shape.shape, json.dumps(s.attributes.values))

        w.save()

    @staticmethod
    def load_ocaf(path: str, part_cache: PartCache) -> Part:
        PartSave._validate_ocaf_path(path)

        w = ocaf_wrapper_swig.OcafWrapper(path + ".part.cbf")

        w.load()

        root_shape = w.getRootShape()

        root_shape_shape = PartSave._downcast_shape(root_shape.shape)
        root_shape_attributes = json.loads(root_shape.annotationString)

        shape_names = w.getShapeNames()

        subshapes: typing.Dict[str, typing.List[AnnotatedShape]] = dict()

        for name in shape_names:
            subshapes[name] = []
            for subshape in w.getShapesForName(name):
                subshape_shape = PartSave._downcast_shape(subshape.shape)
                subshape_attributes = json.loads(subshape.annotationString)
                subshapes[name].append(AnnotatedShape(subshape_shape, subshape_attributes))

        uuid = w.getUUID()

        from ezocc.part_cache import DefaultCacheToken

        return Part(DefaultCacheToken.with_uuid(uuid, part_cache), SubshapeMap(
            AnnotatedShape(root_shape_shape, root_shape_attributes),
            subshapes))

    @staticmethod
    def _downcast_shape(shape: OCC.Core.TopoDS.TopoDS_Shape):
        if shape.ShapeType() == OCC.Core.TopAbs.TopAbs_SHAPE:
            return shape
        elif shape.ShapeType() == OCC.Core.TopAbs.TopAbs_COMPOUND:
            return OCC.Core.TopoDS.topods.Compound(shape)
        elif shape.ShapeType() == OCC.Core.TopAbs.TopAbs_COMPSOLID:
            return OCC.Core.TopoDS.topods.CompSolid(shape)
        elif shape.ShapeType() == OCC.Core.TopAbs.TopAbs_SOLID:
            return OCC.Core.TopoDS.topods.Solid(shape)
        elif shape.ShapeType() == OCC.Core.TopAbs.TopAbs_SHELL:
            return OCC.Core.TopoDS.topods.Shell(shape)
        elif shape.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE:
            return OCC.Core.TopoDS.topods.Face(shape)
        elif shape.ShapeType() == OCC.Core.TopAbs.TopAbs_WIRE:
            return OCC.Core.TopoDS.topods.Wire(shape)
        elif shape.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE:
            return OCC.Core.TopoDS.topods.Edge(shape)
        elif shape.ShapeType() == OCC.Core.TopAbs.TopAbs_VERTEX:
            return OCC.Core.TopoDS.topods.Vertex(shape)
        else:
            raise ValueError()


class PartArray:

    def __init__(self, part: Part):
        self._part = part
        self._factory = PartFactory(self._part.cache_token.get_cache())

    def on_solids_of(self, other: Part) -> Part:
        result = [
            self._part.align().xyz_mid_to_mid(p) for p in other.explore.solid.get()]
        return self._factory.compound(*result)

    def on_faces_of(self, other: Part) -> Part:
        return self._factory.compound(*[
            self._part.align().xyz_mid_to_mid(p) for p in other.explore.face.get()
        ])

    def on_verts_of(self, other: Part) -> Part:
        result = []

        for v in other.explore.vertex.get():
            x, y, z = op.InterrogateUtils.vertex_to_xyz(v.shape)
            result.append(self._part.transform.translate(x, y, z))

        return self._factory.compound(*result)


class PartMake:

    def __init__(self, part: Part):
        self._part = part

    # reduce a compound of compounds to a single compound
    def collapse_compound(self) -> Part:
        raise NotImplementedError()

        if self._part.shape.ShapeType() != OCC.Core.TopAbs.TopAbs_COMPOUND:
            raise ValueError("Not a compound shape")

        if op.InterrogateUtils.is_compound_of(self._part.shape, OCC.Core.TopAbs.TopAbs_COMPOUND):
            subshapes = []
            for c in op.InterrogateUtils.traverse_direct_subshapes(self._part.shape):
                for ss in op.InterrogateUtils.traverse_direct_subshapes(c):
                    subshapes.append(Part(ss, self._part.subshapes))

            return PartFactory.compound(*subshapes)

        raise ValueError("Not a compound of compounds")

    def solid(self) -> Part:
        if self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_SOLID:
            # nothing to do
            return self._part

        if op.InterrogateUtils.is_singleton_compound(self._part.shape) and \
                op.InterrogateUtils.is_compound_of(self._part.shape, OCC.Core.TopAbs.TopAbs_SOLID):
            return self._part.explore.solid.get()[0]

        return self._part.do(lambda p:
                             p.perform_make_shape(
                                 p.cache_token.mutated("make", "solid"),
                                 OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeSolid(p.shape),
                                 map_is_partner=True))

    def shell(self) -> Part:
        if self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_SHELL:
            # nothing to do
            return self._part

        if op.InterrogateUtils.is_singleton_compound(self._part.shape) and \
                op.InterrogateUtils.is_compound_of(self._part.shape, OCC.Core.TopAbs.TopAbs_SHELL):
            return self._part.explore.shell.get()[0]

        if op.InterrogateUtils.is_compound_of(self._part.shape, OCC.Core.TopAbs.TopAbs_FACE):
            return PartFactory(self._part.cache_token.get_cache()).shell(*self._part.explore.face.get())

        return self._part.do(lambda p:
                             p.perform_make_shape(
                                 p.cache_token.mutated("make", "shell"),
                                 OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeShell(p.shape),
                                 map_is_partner=True))

    def face(self) -> Part:

        if self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE:
            #nothing to do
            return self._part
        elif self._part.inspect.is_shell():
            faces = self._part.explore.face.get()
            if len(faces) == 1:
                return faces[0]
            else:
                raise ValueError("Part is a shell consisting of != 1 face. Cannot reduce to a single face.")
        elif op.InterrogateUtils.is_compound_of(self._part.shape, OCC.Core.TopAbs.TopAbs_EDGE):
            return op.WireSketcher.from_edges(*set(op.Explorer.edge_explorer(self._part.shape).get()), tolerance=0.001)\
                .close()\
                .get_face_part()
        elif op.InterrogateUtils.is_singleton_compound(self._part.shape) and \
            op.InterrogateUtils.is_compound_of(self._part.shape, OCC.Core.TopAbs.TopAbs_FACE):
            return self._part.explore.face.get()[0]
        else:
            TypeValidator.assert_is_shape_type_or_simpler(self._part.shape, OCC.Core.TopAbs.TopAbs_FACE)

        return self._part.do(lambda p:
                             p.perform_make_shape(
                                p.cache_token.mutated("make", "face"),
                                OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(p.shape),
                                map_is_partner=True))

    def wire(self) -> Part:

        if self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_WIRE:
            # no action needed
            return self._part
        elif self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE:
            return self._part.do(lambda p:
                                 p.perform_make_shape(
                                    p.cache_token.mutated("make", "wire"),
                                    OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(p.shape),
                                    map_is_partner=True))
        elif self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_COMPOUND:
            #if any(e.ShapeType() != OCC.Core.TopAbs.TopAbs_EDGE for e in edges):
            #    raise ValueError("Can only create a wire from a compound of edges")

            mkw = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire()
            mkw.Add(op.ListUtils.list([s for s in op.InterrogateUtils.traverse_all_subshapes(self._part.shape) if s.ShapeType() == TopAbs_EDGE]))
            mkw.Build()

            return self._part.perform_make_shape(self._part.cache_token.mutated("make", "wire"), mkw)

        wires = self._part.explore.wire.get()

        if len(wires) == 1:
            return wires[0]

        raise RuntimeError(f"Cannot convert part shape {self._part.shape} to wire.")


class PartCleanup:

    def __init__(self, part: Part):
        self._part = part

    def build_curves_3d(self) -> Part:
        op.GeomUtils.build_curves_3d(self._part.shape)
        return self._part

    # note: general cleanup probably required after this as wires may not be connected
    def fuse_wires(self) -> Part:
        if self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_WIRE:
            # nothing to do
            return self._part

        if self._part.shape.ShapeType() != OCC.Core.TopAbs.TopAbs_COMPOUND:
            raise ValueError("Wire fuse can only be performed on a compound of wires")

        wires = [w for w in op.ExploreUtils.iterate_compound(self._part.shape)]

        if any(w.ShapeType() != OCC.Core.TopAbs.TopAbs_WIRE for w in wires):
            raise ValueError("Only wires can be fused")

        mkw = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire()

        edges_to_add = []
        for w in wires:
            edges_to_add += op.Explorer.edge_explorer(w).get()

        mkw.Add(op.ListUtils.list(edges_to_add))

        return self._part.map_subshape_changes(
            self._part.cache_token.mutated("cleanup", "fuse_wires"),
            new_shape=mkw.Shape(), mks=mkw, map_is_partner=True, map_is_same=True)


    def fix_small_face(self):
        sf = OCC.Core.ShapeFix.ShapeFix_FixSmallFace()
        sf.SetMaxTolerance(0.001)
        sf.Init(self._part.shape)
        sf.Perform()

        return self._part.map_subshape_changes(
            self._part.cache_token.mutated("cleanup", "fix_small_face"),
            sf.Shape(),
            mks=sf.Context().History())


    def fix_solid(self):
        if not self._part.inspect.is_solid():
            raise ValueError(f"Part is not a solid {self._part}")

        sf = OCC.Core.ShapeFix.ShapeFix_Solid()
        sf.SetMaxTolerance(0.001)
        sf.Init(self._part.shape)
        sf.Perform()

        return self._part.map_subshape_changes(
            self._part.cache_token.mutated("cleanup", "fix_solid"),
            sf.Shape(),
            mks=sf.Context().History())

    def __call__(self,
                 unify_edges: bool = True,
                 unify_faces: bool = True,
                 concat_b_splines: bool = False,
                 fix_small_face: bool = False) -> Part:
        unif = OCC.Core.ShapeUpgrade.ShapeUpgrade_UnifySameDomain()
        unif.Initialize(self._part.shape, unify_edges, unify_faces, concat_b_splines)
        unif.AllowInternalEdges(True)
        unif.Build()

        return self._part.map_subshape_changes(
            self._part.cache_token.mutated("cleanup", unify_edges, unify_faces, concat_b_splines, fix_small_face),
            unif.Shape(),
            mks=unif.History())


class PartExplorer:
    """
    Tried to find a more elegant wrapping of op.Explorer. but it turned out to be easier
    to just re-implement it here.
    """

    def __init__(self, part: Part, shape_type: typing.Optional[OCC.Core.TopAbs.TopAbs_ShapeEnum]):
        self._part = part
        self._shape_type = shape_type
        self._predicate: typing.Callable[[Part], bool] = lambda p: True
        self._key: typing.Callable[[Part], float] = lambda p: 0.0

    def get_max(self, key: typing.Callable[[Part], float]) -> Part:
        return self.order_by(key).get()[-1]

    def get_min(self, key: typing.Callable[[Part], float]) -> Part:
        return self.order_by(key).get()[0]

    def filter_by(self, predicate: typing.Callable[[Part], bool]):
        old_pred = self._predicate

        self._predicate = lambda e: (old_pred(e) and predicate(e))
        return self

    def order_by(self, key: typing.Callable[[Part], float]):
        self._key = key
        return self

    def get(self) -> typing.List[Part]:
        result = [Part(
            self._part.cache_token.mutated("explore", self._shape_type, i),
            self._part.subshapes.with_updated_root_shape(s)) for i, s in
                  enumerate(op.ExploreUtils.explore_iterate(self._part.shape, self._shape_type))]
        result = [p for p in result if self._predicate(p)]
        result.sort(key=self._key)
        return result

    def get_single(self) -> Part:
        result = self.get()

        if len(result) != 1:
            raise ValueError(f"Expected result of explore to be a single element, was instead {len(result)}")

        return result[0]

    @staticmethod
    def solid_explorer(part: Part):
        return PartExplorer(part, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_SOLID)

    @staticmethod
    def shell_explorer(part: Part):
        return PartExplorer(part, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_SHELL)

    @staticmethod
    def face_explorer(part: Part):
        return PartExplorer(part, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_FACE)

    @staticmethod
    def vertex_explorer(part: Part):
        return PartExplorer(part, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_VERTEX)

    @staticmethod
    def edge_explorer(part: Part):
        return PartExplorer(part, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_EDGE)

    @staticmethod
    def wire_explorer(part: Part):
        return PartExplorer(part, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_WIRE)

    @staticmethod
    def shape_explorer(part: Part):
        return PartExplorer(part, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_SHAPE)

    @staticmethod
    def compound_explorer(part: Part):
        return PartExplorer(part, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_COMPOUND)


class PartExplore:

    def __init__(self, part: Part):
        self._part = part

    def __getattr__(self, item) -> PartExplorer:
        explore_method = getattr(PartExplorer, f"{item}_explorer")

        return explore_method(self._part)


class PartExtruder:

    def __init__(self, part: Part):
        self._part = part

    @staticmethod
    def _solidify_face(face: OCC.Core.TopoDS.TopoDS_Face,
                       amount: float):

        mko = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakeOffsetShape()
        mko.PerformBySimple(face, amount / 2)

        offset_surface0 = op.Explorer.face_explorer(mko.Shape()).get()[0]

        reversed_face = face.Reversed()
        mko = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakeOffsetShape()
        mko.PerformBySimple(reversed_face, amount / 2)

        offset_surface1 = op.Explorer.face_explorer(mko.Shape()).get()[0]

        return PartFactory.loft([
            op.InterrogateUtils.outer_wire(offset_surface0),
            op.InterrogateUtils.outer_wire(face),
            op.InterrogateUtils.outer_wire(offset_surface1)
        ]).cleanup()

    def solidify_edges(self, amount: float):
        as_wire = self._part.make.wire()

        edges = [PartExtruder._solidify_edge(e.shape, amount) for e in as_wire.explore.edge.get()]

        verts = [PartFactory.sphere(amount / 2).tr.translate(*v.extents.xyz_mid) for v in as_wire.explore.vertex.get()]

        return PartFactory.union(*edges, *verts).cleanup()

    @staticmethod
    def _solidify_edge(edge: OCC.Core.TopoDS.TopoDS_Edge, amount: float):
        lp = op.InterrogateUtils.line_points(edge)
        tp = op.InterrogateUtils.line_tangent_points(edge)
        circ = gp.gp_Circ(
            gp.gp_Ax2(lp[0], gp.gp_Dir(tp[0])),
            amount / 2)

        pipe_wire = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(
            OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(circ).Edge()).Shape()

        spine_wire = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(edge).Wire()

        op.GeomUtils.build_curves_3d(pipe_wire)
        op.GeomUtils.build_curves_3d(spine_wire)

        pipe = Part(pipe_wire)

        pipe = pipe.loft.pipe(
            spine_wire,
            transition_mode=OCC.Core.BRepBuilderAPI.BRepBuilderAPI_TransitionMode.BRepBuilderAPI_RoundCorner) \
            .cleanup.fix_solid() \
            .validate()

        return pipe

    @staticmethod
    def _inflate_faces(shell: OCC.Core.TopoDS.TopoDS_Shape,
                       amount: float,
                       union: bool = True):

        verts = [v for v in op.Explorer.vertex_explorer(shell).get()]
        edges = [e for e in op.Explorer.edge_explorer(shell).get()]
        faces = [f for f in op.Explorer.face_explorer(shell).get()]

        # duplicate a sphere on each vertex
        solid_verts = [PartFactory.sphere(amount / 2)
                    .transform.translate(*op.InterrogateUtils.vertex_to_xyz(v)) for v in verts]

        solid_faces = [PartExtruder._solidify_face(f, amount) for f in faces]

        solid_edges = [PartExtruder._solidify_edge(e, amount) for e in edges]

        if not union:
            return PartFactory.compound(*solid_verts, *solid_edges, *solid_faces)

        result = solid_faces[0]

        for i, sf in enumerate(solid_faces[1:]):
            logger.debug(f"Fusing with bool face {i + 1}/{len(solid_faces)}")
            result = result.bool.union(sf)

        for i, sf in enumerate(solid_edges):
            logger.debug(f"Fusing with bool edge {i + 1}/{len(solid_edges)}")
            try:
                result = result.bool.union(sf)
            except RuntimeError:
                result.bool.union(sf).preview()
                raise

        for i, sf in enumerate(solid_verts):
            logger.debug(f"Fusing with bool vert {i + 1}/{len(solid_verts)}")
            result = result.bool.union(sf)

        return result

    def make_thick_solid(self,
                         amount: float,
                         closing_faces: typing.List[typing.Union[OCC.Core.TopoDS.TopoDS_Face, Part]] = None,
                         tolerance: float = 0.001,
                         join_type: OCC.Core.GeomAbs.GeomAbs_JoinType = OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Arc,
                         remake_solid: bool = True) -> Part:
        """

        @param amount: offset distance
        @param closing_faces: optional list of faces to form the opening of a "hollowed out" solid.
        @param tolerance:
        @param join_type: arc, tangent etc.
        @param remake_solid: if the input shape is a solid, attempt to recreate a solid as the result (often the result
        is of type SHELL)
        """

        if closing_faces is None:
            closing_faces = []

        closing_faces_filtered = [f if isinstance(f, OCC.Core.TopoDS.TopoDS_Shape) else f.shape for f in closing_faces]

        new_token = self._part.cache_token.mutated("extrude",
                                                   "make_thick_solid",
                                                   amount,
                                                   closing_faces,
                                                   tolerance,
                                                   join_type,
                                                   remake_solid)

        def _do() -> Part:
            mks = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakeThickSolid()

            mks.MakeThickSolidByJoin(
                self._part.shape,
                op.ListUtils.list(closing_faces_filtered),
                amount,
                tolerance,
                OCC.Core.BRepOffset.BRepOffset_Mode.BRepOffset_Skin,
                False,
                False,
                join_type,
                False)

            result = self._part.perform_make_shape(new_token, mks)

            if len(closing_faces_filtered) == 0 and amount > 0:
                new_shape = result.shape.Reversed()
                result = Part(new_token, result.subshapes.with_updated_root_shape(new_shape))


            if remake_solid and self._part.inspect.is_solid():
                result = result.make.solid()

            return result

        return self._part.cache_token.get_cache().ensure_exists(
            new_token,
            _do)

    def inflate_faces(self, amount: float, union: bool = True):
        """
        Can be thought of as a 3D version of a 2D offset.
        i.e. Minkowski sum
        e.g. a straight line would become a cylinder with hemisphere
        end caps. The diameter of the cylinder would be equal to amount

        @param union if true, the result will have a bool.union() applied to it. Otherwise, the returned result will
        consist of solids representing the input faces.

        """

        return Part(self._inflate_faces(self._part.shape, amount, union).shape, self._part.subshapes)

    def square_offset(self,
                      amount: float,
                      join_type: OCC.Core.GeomAbs.GeomAbs_JoinType = OCC.Core.GeomAbs.GeomAbs_Tangent,
                      spine: typing.Union[OCC.Core.TopoDS.TopoDS_Face, gp.gp_Ax2] = None,
                      flip_endpoints: bool = False) -> Part:

        if self._part.shape.ShapeType() != OCC.Core.TopAbs.TopAbs_WIRE:
            raise ValueError("Part must be Wire to perform square offset.")

        w1 = self._part.extrude.offset(
            amount=amount,
            join_type=join_type,
            spine=spine,
            is_open_result=True)

        # connect end of w1 to beginning of w
        # connect end of w to beginning of w1
        w_start, w_end = op.InterrogateUtils.wire_points(self._part.shape)
        if flip_endpoints:
            w_end, w_start = w_start, w_end

        w1_start, w1_end = op.InterrogateUtils.wire_points(w1.shape)

        mkw = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire()

        edges = [
            OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(w1_end, w_start).Shape(),
            OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(w_end, w1_start).Shape()
        ]

        for e in op.Explorer.edge_explorer(self._part.shape).get():
            edges.append(e)

        for e in op.Explorer.edge_explorer(w1.shape).get():
            edges.append(e)

        return PartFactory.compound(*[Part(p) for p in edges])\
            .sew.edges()\
            .make.wire()

    def offset(self,
               amount: float,
               join_type: OCC.Core.GeomAbs.GeomAbs_JoinType = OCC.Core.GeomAbs.GeomAbs_Arc,
               is_open_result: bool = False,
               spine: typing.Union[OCC.Core.TopoDS.TopoDS_Face, gp.gp_Ax2] = None) -> Part:

        if isinstance(spine, gp.gp_Ax2):
            spine_pln = gp.gp_Pln(gp.gp_Pnt(*self._part.extents.xyz_mid), spine.Direction())
            spine = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(spine_pln).Shape()

        token = self._part.cache_token.mutated("offset", amount, join_type, is_open_result,
                                               spine if spine is None else UtilWrapper.shape_to_string(spine))

        result: typing.Optional[Part] = None

        for w in op.Explorer.wire_explorer(self._part.shape).get():
            if spine is None:
                mko = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakeOffset(w, join_type, is_open_result)
            else:
                mko = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakeOffset(spine, join_type, is_open_result)
                mko.AddWire(w)

            mko.Perform(amount)

            if result is None:
                result = self._part.perform_make_shape(NoOpCacheToken(),  mko)
            else:
                result = result.add(self._part.perform_make_shape(NoOpCacheToken(), mko))

        if result is None:
            raise ValueError("Could not compute result (does the input shape contain any wires?)")

        return result.with_cache_token(token)

    def normal_symmetric_prism(self,
                     length: float,
                     first_shape_name: str = None,
                     last_shape_name: str = None,
                     loft_profile_name: str = None) -> Part:

        norm_dir = op.InterrogateUtils.face_normal(self._part.make.face().shape)[1]
        dx = length * norm_dir.X()
        dy = length * norm_dir.Y()
        dz = length * norm_dir.Z()

        return self.symmetric_prism(dx=dx,
                                    dy=dy,
                                    dz=dz,
                                    first_shape_name=first_shape_name,
                                    last_shape_name=last_shape_name,
                                    loft_profile_name=loft_profile_name)

    def symmetric_prism(self, dx: float = 0, dy: float = 0, dz: float = 0,
                        first_shape_name: str = None,
                        last_shape_name: str = None,
                        loft_profile_name: str = None) -> Part:

        p0 = self.prism(dx=dx, dy=dy, dz=dz, first_shape_name=first_shape_name, last_shape_name=last_shape_name, loft_profile_name=loft_profile_name)
        p1 = self.prism(dx=-dx, dy=-dy, dz=-dz, first_shape_name=first_shape_name, last_shape_name=last_shape_name, loft_profile_name=loft_profile_name)

        return p0.bool.union(p1).with_cache_token(
            self._part.cache_token.mutated("symmetric_prism", dx, dy, dz, first_shape_name, last_shape_name, loft_profile_name))

    def normal_prism(self,
                     length: float,
                     first_shape_name: str = None,
                     last_shape_name: str = None,
                     loft_profile_name: str = None) -> Part:

        norm_dir = op.InterrogateUtils.face_normal(self._part.make.face().shape)[1]
        dx = length * norm_dir.X()
        dy = length * norm_dir.Y()
        dz = length * norm_dir.Z()

        return self.prism(dx=dx,
                          dy=dy,
                          dz=dz,
                          first_shape_name=first_shape_name,
                          last_shape_name=last_shape_name,
                          loft_profile_name=loft_profile_name)

    def prism(self, dx: float = 0, dy: float = 0, dz: float = 0,
              first_shape_name: str = None,
              last_shape_name: str = None,
              loft_profile_name: str = None) -> Part:
        if dx == 0 and dy == 0 and dz == 0:
            raise ValueError("All parameters are zero, no prism operation can be performed.")

        mkp = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakePrism(self._part.shape, OCC.Core.gp.gp_Vec(dx, dy, dz), True)
        mkp.Build()

        if not mkp.IsDone():
            raise RuntimeError("Prism operation failed.")

        token = self._part.cache_token.mutated("prism", dx, dy, dz, first_shape_name, last_shape_name, loft_profile_name)
        result = self._part.perform_make_shape(token, mkp)

        extra_shapes: typing.Dict[str, typing.Set[AnnotatedShape]] = dict()

        if first_shape_name is not None:
            extra_shapes[first_shape_name] = extra_shapes.get(first_shape_name, set()).union({AnnotatedShape(mkp.FirstShape())})

        if last_shape_name is not None:
            extra_shapes[last_shape_name] = extra_shapes.get(last_shape_name, set()).union({AnnotatedShape(mkp.LastShape())})

        if loft_profile_name is not None:
            extra_shapes[loft_profile_name] = extra_shapes.get(loft_profile_name, {})

            for s in op.InterrogateUtils.traverse_all_subshapes(self._part.shape):
                for ss in op.ListUtils.iterate_list(mkp.Generated(s)):
                    if AnnotatedShape(ss) not in extra_shapes[loft_profile_name]:
                        extra_shapes[loft_profile_name].append(AnnotatedShape(ss))

        new_subshapes = result.subshapes
        for name, shapes in extra_shapes.items():
            for s in shapes:
                new_subshapes.place(name, s)

        return Part(token, new_subshapes)


class PartTransformer:

    def __init__(self, part):
        self._part = part

    def __call__(self, trsf_configurer: typing.Union[OCC.Core.gp.gp_Trsf, typing.Callable[[OCC.Core.gp.gp_Trsf], None]]) -> Part:
        if isinstance(trsf_configurer, OCC.Core.gp.gp_Trsf):
            trsf = trsf_configurer
        else:
            trsf = OCC.Core.gp.gp_Trsf()
            trsf_configurer(trsf)

        trsf_values = [trsf.Value(int(i / 4) + 1, i % 4 + 1) for i in range(0, 12)]
        token = self._part.cache_token.mutated("trsf", *trsf_values)

        def _do():
            # copy to prevent underlying geom modification
            transformer = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_Transform(self._part.shape, trsf, True)
            return self._part.perform_make_shape(
                token,
                transformer)

        return self._part.cache_token.get_cache().ensure_exists(token, _do)

    def mv(self, dx: float = 0, dy: float = 0, dz: float = 0) -> Part:
        return self.translate(dx, dy, dz)

    def translate(self, dx: float = 0, dy: float = 0, dz: float = 0) -> Part:
        return self(lambda t: t.SetTranslation(gp.gp_Vec(dx, dy, dz)))

    def rx(self, angle: float, offset: typing.Tuple[float, float, float] = None) -> Part:
        return self.rotate(gp.gp.OX(), angle, offset)

    def ry(self, angle: float, offset: typing.Tuple[float, float, float] = None) -> Part:
        return self.rotate(gp.gp.OY(), angle, offset)

    def rz(self, angle: float, offset: typing.Tuple[float, float, float] = None) -> Part:
        return self.rotate(gp.gp.OZ(), angle, offset)

    def rotate(self, ax1: OCC.Core.gp.gp_Ax1, angle: float, offset: typing.Tuple[float, float, float] = None) -> Part:
        if offset is not None:
            ax1 = ax1.Translated(gp.gp_Vec(*offset))

        return self(lambda t: t.SetRotation(ax1, angle))

    def scale(self, factor: float, ox: float = 0, oy: float = 0, oz: float = 0) -> Part:
        return self(lambda t: t.SetScale(gp.gp_Pnt(ox, oy, oz), factor))

    def scale_axis(self, fx: float = 1, fy: float = 1, fz: float = 1) -> Part:
        return self.g_transform_fields(r0c0=fx, r1c1=fy, r2c2=fz)

    def g_transform(self, *trsf: OCC.Core.gp.gp_GTrsf) -> Part:
        result = self._part
        for t in trsf:
            transformer = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_GTransform(result.shape, t, True)
            trsf_values = [t.Value(int(i / 4) + 1, i % 4 + 1) for i in range(0, 12)]

            result = result.perform_make_shape(result.cache_token.mutated("g_trsf", trsf_values), transformer)

        return result

    def g_transform_fields(self,
                    r0c0: float = 1, r0c1: float = 0, r0c2: float = 0,
                    r1c0: float = 0, r1c1: float = 1, r1c2: float = 0,
                    r2c0: float = 0, r2c1: float = 0, r2c2: float = 1):
        trsf = OCC.Core.gp.gp_GTrsf()
        trsf.SetVectorialPart(OCC.Core.gp.gp_Mat(r0c0, r0c1, r0c2, r1c0, r1c1, r1c2, r2c0, r2c1, r2c2))

        transformer = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_GTransform(self._part.shape, trsf, True)

        return self._part.perform_make_shape(
            self._part.cache_token.mutated("trsf_matrix", r0c0, r0c1, r0c2, r1c0, r1c1, r1c2, r2c0, r2c1, r2c2),
            transformer)

    def scale_to_x_span(self, desired_x_span: typing.Union[float, Part], scale_other_axes: bool = False) -> Part:
        if isinstance(desired_x_span, Part):
            desired_x_span = desired_x_span.xts.z_span

        x_scale_factor = desired_x_span / self._part.extents.x_span
        other_axes_val = x_scale_factor if scale_other_axes else 1

        return self.g_transform_fields(r0c0=x_scale_factor, r1c1=other_axes_val, r2c2=other_axes_val)

    def scale_to_y_span(self, desired_y_span: typing.Union[float, Part], scale_other_axes: bool = False) -> Part:
        if isinstance(desired_y_span, Part):
            desired_y_span = desired_y_span.xts.z_span

        y_scale_factor = desired_y_span / self._part.extents.y_span
        other_axes_val = y_scale_factor if scale_other_axes else 1

        return self.g_transform_fields(r0c0=other_axes_val, r1c1=y_scale_factor, r2c2=other_axes_val)

    def scale_to_z_span(self, desired_z_span: typing.Union[float, Part], scale_other_axes: bool = False) -> Part:
        if isinstance(desired_z_span, Part):
            desired_z_span = desired_z_span.xts.z_span

        z_scale_factor = desired_z_span / self._part.extents.z_span
        other_axes_val = z_scale_factor if scale_other_axes else 1

        return self.g_transform_fields(r0c0=other_axes_val, r1c1=other_axes_val, r2c2=z_scale_factor)


class PartBool:

    def __init__(self, part: Part, auto_extract_singleton_compound: bool=True):
        """
        @param part:
        @param auto_extract_singleton_compound: if True (default) and input shape is non-compound, a result which is a
        compound of a single element will be converted to that element directly.
        """

        self._part = part
        self._auto_extract_singleton_compound = auto_extract_singleton_compound

        # resulting part is a union of shapes from both parts

    def union(self, *others: Part,
                glue: typing.Optional[OCC.Core.BOPAlgo.BOPAlgo_GlueEnum] = None) -> Part:
        fuse = OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Fuse()

        if len(others) == 0:
            if self._part.shape.ShapeType() != OCC.Core.TopAbs.TopAbs_COMPOUND:
                raise ValueError("Argumentless bool can only be performed on compound shapes, "
                                 f"this shape has type {self._part.shape}")

            tools = [Part(self._part.cache_token.mutated("boolop", "union", s),
                          self._part.subshapes.with_updated_root_shape(s)) for s in op.InterrogateUtils.traverse_direct_subshapes(self._part.shape)]

            return self._boolop(self._part.cache_token.mutated("boolop", "union_single", tools[0:1], tools[1:], glue, str(fuse)),
                                fuse,
                                tools[0:1],
                                tools[1:],
                                glue)

        return self._boolop(
            self._part.cache_token.mutated("boolop", "union", [self._part], others, str(fuse)), fuse, [self._part], [p for p in others], glue)

    def cut(self, *others: Part,
                glue: typing.Optional[OCC.Core.BOPAlgo.BOPAlgo_GlueEnum] = None) -> Part:
        if len(others) == 0:
            raise ValueError("No other parts specified")

        return self._boolop(self._part.cache_token.mutated("boolop", "cut", [self._part], others, glue),
                            OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Cut(),
                            [self._part],
                            [p for p in others],
                            glue)

    def common(self, *others: Part,
                glue: typing.Optional[OCC.Core.BOPAlgo.BOPAlgo_GlueEnum] = None) -> Part:
        if len(others) == 0:
            raise ValueError("No other parts specified")

        return self._boolop(self._part.cache_token.mutated("boolop", "common", [self._part], others, glue),
                            OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Common(),
                            [self._part],
                            [p for p in others],
                            glue)

    def section(self, *others: Part,
                glue: typing.Optional[OCC.Core.BOPAlgo.BOPAlgo_GlueEnum] = None):
        if len(others) == 0:
            raise ValueError("No other parts specified")

        return self._boolop(self._part.cache_token.mutated("boolop", "section", [self._part], others, glue),
                            OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Section(),
                            [self._part],
                            [p for p in others],
                            glue)

    def _boolop(self,
                cache_token: CacheToken,
                algo: OCC.Core.BRepAlgoAPI.BRepAlgoAPI_BooleanOperation,
                args : typing.List[Part],
                tools : typing.List[Part],
                glue: typing.Optional[OCC.Core.BOPAlgo.BOPAlgo_GlueEnum] = None) -> Part:

        def _do():
            algo.SetRunParallel(True)
            algo.SetUseOBB(True)
            algo.SetNonDestructive(True)
            algo.SetArguments(op.ListUtils.list([p.shape for p in args]))
            algo.SetTools(op.ListUtils.list([p.shape for p in tools]))

            if glue is not None:
                algo.SetGlue(glue)

            algo.Build()

            if algo.HasErrors():
                report = algo.GetReport()

                alerts = report.GetAlerts(Message_Gravity.Message_Fail)

                alert_values = []
                while alerts.Size() != 0:
                    alert_values.append(alerts.First())
                    alerts.RemoveFirst()

                alert_values = [a.GetMessageKey() for a in alert_values]

                arg_str = '\n'.join(str(p) for p in args)
                tools_str = '\n'.join(str(p) for p in tools)

                logger.error(f"Bool op failed with following alerts: {alert_values}\n\nArgs:\n{arg_str}\n\nTools\n\n{tools_str}\n\n")

                raise RuntimeError(f"bool op failed with the following alerts: {alert_values} "
                                   f"(operation was performed with args {arg_str}, tools: {tools_str})")

            shape = algo.Shape()

            union_subshapes = self._part.subshapes.with_updated_root_shape(shape)
            for p in args:
                union_subshapes.merge(p.subshapes.map_subshape_changes(union_subshapes.root_shape, mks=algo))

            for p in tools:
                union_subshapes.merge(p.subshapes.map_subshape_changes(union_subshapes.root_shape, mks=algo))

            result = Part(cache_token, union_subshapes)

            if self._auto_extract_singleton_compound and not self._part.inspect.is_compound() \
                and op.InterrogateUtils.is_singleton_compound(shape):

                direct_subshape = next(s for s in op.InterrogateUtils.traverse_direct_subshapes(result.shape))

                logger.info(f"Boolop output is compound of single part of type {Humanize.shape_type(direct_subshape.ShapeType())}, "
                            f"and input shape is not a compound. Reducing output to a single shape for simplicity.")

                result = Part(cache_token, union_subshapes.with_updated_root_shape(direct_subshape))

            return result

        return cache_token.get_cache().ensure_exists(cache_token, _do)

class PartMirror:

    def __init__(self, part: Part):
        self._part = part

    def x(self, union: bool = False, center_x: float = 0):
        result = PartTransformer(self._part)(
            lambda t: t.SetMirror(gp.gp.YOZ().Translated(gp.gp_Vec(center_x, 0, 0))))

        if union:
            return PartBool(self._part).union(result)
        else:
            return result

    def y(self, union: bool = False, center_y: float = 0):
        result = PartTransformer(self._part)(
            lambda t: t.SetMirror(gp.gp.ZOX().Translated(gp.gp_Vec(0, center_y, 0))))

        if union:
            return PartBool(self._part).union(result)
        else:
            return result

    def z(self, union: bool = False, center_z: float = 0):
        result = PartTransformer(self._part)(
            lambda t: t.SetMirror(gp.gp.XOY().Translated(gp.gp_Vec(0, 0, center_z))))

        if union:
            return PartBool(self._part).union(result)
        else:
            return result


class Fillet2dDefaultVertSelector:

    def __init__(self,
                 source_edges: typing.List[OCC.Core.TopoDS.TopoDS_Edge],
                 allowed_edges: typing.List[OCC.Core.TopoDS.TopoDS_Edge]):
        self._source_edges = source_edges
        self._allowed_edges = allowed_edges
        self._default_added_verts = []

    def __call__(self, vert: OCC.Core.TopoDS.TopoDS_Vertex) -> bool:
        # determine number of edges for vert, if 2, then a fillet can be performed

        owner_edges = [e for e in self._allowed_edges if any(v.IsSame(vert) for v in op.Explorer.vertex_explorer(e).get())]

        if len(owner_edges) == 0:
            # vertex not owned by any edge allowed to be filleted
            return False

        connected_edge_count = 0
        for edge in self._source_edges:
            for v in op.Explorer.vertex_explorer(edge).get():
                if v.IsSame(vert):
                    connected_edge_count += 1
                    if connected_edge_count > 1 and not any(v1.IsSame(vert) for v1 in self._default_added_verts):
                        self._default_added_verts.append(vert)
                        return True

        return False


T = typing.TypeVar("T")
class PartFilleter:

    EDGE_SELECTOR_TYPE = typing.Optional[typing.Union[
        typing.Callable[[OCC.Core.TopoDS.TopoDS_Edge], bool],
        typing.Set[typing.Union[OCC.Core.TopoDS.TopoDS_Edge, Part]]
    ]]

    FACE_SELECTOR_TYPE = typing.Optional[typing.Union[
        typing.Callable[[OCC.Core.TopoDS.TopoDS_Face], bool],
        typing.Set[typing.Union[OCC.Core.TopoDS.TopoDS_Face, Part]]
    ]]

    @staticmethod
    def _create_selector(selector: typing.Optional[typing.Union[
                            typing.Callable[[T], bool],
                            typing.Set[T]
                         ]] = None) -> typing.Callable[[T], bool]:

        print(selector)

        def select_on_part(shape):
            s0 = op.SetPlaceableShape(shape)
            s1 = op.SetPlaceableShape(selector.shape)

            return s0 == s1

        if selector is None:
            return lambda s: True
        elif isinstance(selector, Part):
            return select_on_part
        elif isinstance(selector, list) or isinstance(selector, set):
            selector_collection = {s.shape if isinstance(s, Part) else s for s in selector}
            return lambda s: s in selector_collection
        else:
            return selector

    def __init__(self, part: Part):
        self._part = part

    @staticmethod
    def _guard_mkf2d_fail(mkf: OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeFillet2d):
        if not mkf.IsDone():
            status = mkf.Status()
            import OCC.Core.ChFi2d

            raise RuntimeError("ChFi2d_ConstructionError raised during makefillet: " +
                               OCC.Core.ChFi2d.ChFi2d_ConstructionError(status).name)

    def fillet_edges(self,
                     radius: float,
                     edge_selector: EDGE_SELECTOR_TYPE = None) -> Part:
        edge_selector = PartFilleter._create_selector(edge_selector)

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeFillet(self._part.shape)

        edges = []
        for e in op.Explorer.edge_explorer(self._part.shape).filter_by(edge_selector).get():
            edges.append([radius, e])
            mkf.Add(radius, e)

        mkf.Build()

        return self._part.perform_make_shape(self._part.cache_token.mutated("fillet", "fillet_edges", radius, edges), mkf)

    def chamfer_edges(self,
                      radius: float,
                      edge_selector: EDGE_SELECTOR_TYPE = None) -> Part:
        edge_selector = PartFilleter._create_selector(edge_selector)
        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeChamfer(self._part.shape)

        edges = []
        for e in op.Explorer.edge_explorer(self._part.shape).filter_by(edge_selector).get():
            edges.append(e)
            mkf.Add(radius, e)

        mkf.Build()

        return self._part.perform_make_shape(self._part.cache_token.mutated("fillet", "chamfer_edges", radius, edges), mkf)

    def fillet2d_verts(self,
                       radius: float,
                       vert_selector: typing.Tuple[
                           str,
                           typing.Callable[[OCC.Core.TopoDS.TopoDS_Vertex], bool]] = None) -> Part:
        if isinstance(vert_selector, str):
            verts_to_allow = set(s.set_placeable_shape.shape for s in self._part.subshapes.get(vert_selector))

            def vert_selector(vert):
                return vert in verts_to_allow

        if vert_selector is None:
            all_edges = op.Explorer.edge_explorer(self._part.shape).get()
            vert_selector = Fillet2dDefaultVertSelector(all_edges, all_edges)

        if self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_WIRE:
            result = self._part.make.face()
        else:
            result = self._part

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeFillet2d(result.shape)

        verts_to_fillet = op.Explorer.vertex_explorer(result.shape).filter_by(vert_selector).get()

        # filter out duplicate vertices. this is ugly, no two ways about it
        filtered_verts: typing.Dict[typing.Tuple[float, float, float], OCC.Core.TopoDS.TopoDS_Shape] = {}
        for v in verts_to_fillet:
            v_part = Part.of_shape(v)

            c_mid = tuple(v_part.extents.xyz_mid)

            filtered_verts[c_mid] = v

        if len(verts_to_fillet) == 0:
            raise RuntimeError("No vertices were selected to fillet.")

        for c, v in filtered_verts.items():
            mkf.AddFillet(v, radius)

        mkf.Build()

        PartFilleter._guard_mkf2d_fail(mkf)

        # seems like BRepFilletAPI_MakeFillet2D:Modified does a cast of the supplied shape to TopoDS_Edge.
        # this fails when the input shape is a vertex, so strip out any labelled verts. Not ideal, but better
        # than a crash
        result_subshapes = {s:[e.set_placeable_shape.shape for e in ss
                               if e.set_placeable_shape.shape.ShapeType() != OCC.Core.TopAbs.TopAbs_VERTEX] for s,ss in result.subshapes.map.items()}
        result = Part(NoOpCacheToken(), SubshapeMap.from_unattributed_shapes(result.shape, result_subshapes))\
            .perform_make_shape(
                self._part.cache_token.mutated("fillet2d_verts", radius, [c for c, v in filtered_verts.items()]),
                    mkf)

        if self._part.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_WIRE:
            root_face = result.shape
            updated_subshapes = {n: [l1 for l1 in l if l1 != root_face] for n, l in result.subshapes.map.items()}
            wire = op.Explorer.wire_explorer(result.shape).get()[0]

            return Part(result.cache_token.mutated("extract_wire"),
                        SubshapeMap.from_unattributed_shapes(wire, updated_subshapes))
        else:

            return result

    def fillet_faces(self,
                     radius: float,
                     face_selector: FACE_SELECTOR_TYPE = None) -> Part:
        face_selector = PartFilleter._create_selector(face_selector)

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeFillet(self._part.shape)

        faces = []
        for f in op.Explorer.face_explorer(self._part.shape).filter_by(face_selector).get():
            faces.append(f)
            for e in op.Explorer.edge_explorer(f).get():
                mkf.Add(radius, e)

        mkf.Build()

        return self._part.perform_make_shape(self._part.cache_token.mutated("fillet", "fillet_faces", radius, faces), mkf)

    def chamfer_faces(self,
                      radius: float,
                      face_selector: FACE_SELECTOR_TYPE = None) -> Part:

        face_selector = PartFilleter._create_selector(face_selector)

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeChamfer(self._part.shape)

        faces = []
        for f in op.Explorer.face_explorer(self._part.shape).filter_by(face_selector).get():
            faces.append(f)
            for e in op.Explorer.edge_explorer(f).get():
                mkf.Add(radius, e)

        mkf.Build()

        return self._part.perform_make_shape(self._part.cache_token.mutated("fillet", "chamfer_faces", radius, faces), mkf)

    def fillet_by_name(self, radius: float, *names: str) -> Part:
        if len(names) == 0:
            raise ValueError("At least one name must be specified.")

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeFillet(self._part.shape)

        shapes = [s for n in names for s in self._part.subshapes.get(n)]
        for s in shapes:
            if isinstance(s.set_placeable_shape.shape, OCC.Core.TopoDS.TopoDS_Edge):
                mkf.Add(radius, s.set_placeable_shape.shape)
            else:
                for e in op.Explorer.edge_explorer(s.set_placeable_shape.shape).get():
                    mkf.Add(radius, e)

        mkf.Build()

        return self._part.perform_make_shape(self._part.cache_token.mutated("fillet", "by_name", radius, names), mkf)

    def fillet_edges_by_query(self, radius, query: str):
        to_fillet = set(op.Explorer.edge_explorer(self._part.query(query).shape).get())

        return self.fillet_edges(radius, lambda e: e in to_fillet)

    def fillet2d_by_name(self, radius: float, *names: str) -> Part:
        if len(names) == 0:
            raise ValueError("At least one name must be specified.")

        edge_list = []

        shapes = [s for n in names for s in self._part.get(n)] #[s for n in self._part.get(n) for n in names]
        for s in shapes:
            if s.ShapeType() != OCC.Core.TopAbs.TopAbs_EDGE:
                raise ValueError("Shape is not an edge")

            edge_list.append(s)

        return self.fillet2d_verts(radius, vert_selector=Fillet2dDefaultVertSelector(
            op.Explorer.edge_explorer(self._part.shape).get(),
            edge_list))

    def __call__(self, radius: float) -> Part:
        return self.fillet_edges(radius)


class PartAligner:

    align_re = re.compile("[xyz]+_(min|mid|max)_to(_(min|mid|max))?")

    command_re = re.compile("(x(min|max|mid)(min|max|mid)?)?\\.?"
                            "(y(min|max|mid)(min|max|mid)?)?\\.?"
                            "(z(min|max|mid)(min|max|mid)?)?")

    def __init__(self, part, *subshape_names: str):
        self._part = part
        self._subshape_names = subshape_names

    def com_to_origin(self) -> Part:
        com = op.InterrogateUtils.center_of_mass(self._part.shape)
        return self._part.transform.translate(-com[0], -com[1], -com[2])

    def com(self, other: Part):
        other_com = op.InterrogateUtils.center_of_mass(other.shape)
        return self.com_to_origin().transform.translate(*other_com)

    def stack_x0(self, part: Part, offset: float = 0):
        return self.x_max_to_min(part).transform.translate(dx=offset)

    def stack_x1(self, part: Part, offset: float = 0):
        return self.x_min_to_max(part).transform.translate(dx=offset)

    def stack_y0(self, part: Part, offset: float = 0):
        return self.y_max_to_min(part).transform.translate(dy=offset)

    def stack_y1(self, part: Part, offset: float = 0):
        return self.y_min_to_max(part).transform.translate(dy=offset)

    def stack_z0(self, part: Part, offset: float = 0):
        return self.z_max_to_min(part).transform.translate(dz=offset)

    def stack_z1(self, part: Part, offset: float = 0):
        return self.z_min_to_max(part).transform.translate(dz=offset)

    def by(self, command, other: Part) -> Part:
        token = self._part.cache_token.mutated(
            "part_aligner", "align_by",
            self._subshape_names, command, other)

        return self._part.cache_token.get_cache().ensure_exists(
            token,
            lambda cmd=command, o=other : self._by(cmd, o).with_cache_token(token))

    def _by(self, command: str, other: Part) -> Part:
        if not PartAligner.command_re.fullmatch(command):
            raise ValueError(f"Invalid alignment command: \"{command}\"")

        def pull_axis(input_str: str) -> typing.Tuple[typing.Optional[str], str]:
            if len(input_str) == 0 or not input_str[0] in ['x', 'y', 'z']:
                return None, input_str

            return input_str[0], input_str[1:]

        def pull_minmaxmid(input_str: str) -> typing.Tuple[typing.Optional[str], str]:
            if len(input_str) < 3 or not input_str[0:3] in ['min', 'max', 'mid']:
                return None, input_str

            return input_str[0:3], input_str[3:]

        def pull_separator(input_str: str) -> str:
            if input_str.startswith("."):
                return input_str[1:]
            else:
                return input_str

        result = self._part

        while len(command) != 0:
            axis, command = pull_axis(command)
            source_ext, command = pull_minmaxmid(command)
            dest_ext, command = pull_minmaxmid(command)

            if dest_ext is None:
                dest_ext = source_ext

            result = result.align(*self._subshape_names).__getattr__(f"{axis}_{source_ext}_to_{dest_ext}")(other)

            command = pull_separator(command)

        return result

    def __getattr__(self, item: str) -> typing.Callable[[typing.Union[Part, OCC.Core.TopoDS.TopoDS_Shape]], Part]:
        if not PartAligner.align_re.fullmatch(item):
            raise ValueError("Invalid attribute")

        align_args = item.split('_')

        axes = align_args[0]
        source_part = align_args[1]

        if len(self._subshape_names) == 0:
            source_extents = self._part.extents
        elif len(self._subshape_names) == 1:
            source_extents = self._part.compound_subpart(self._subshape_names[0]).extents
        else:
            source_extents = self._part.sp(*self._subshape_names).extents

        if len(align_args) < 4:
            def result_fn_coords(**kwargs) -> Part:
                align_source = getattr(source_extents, f"xyz_{source_part}")

                dest_x = kwargs.get("x", 0)
                dest_y = kwargs.get("y", 0)
                dest_z = kwargs.get("z", 0)

                dx = dest_x - align_source[0] if "x" in axes else 0
                dy = dest_y - align_source[1] if "y" in axes else 0
                dz = dest_z - align_source[2] if "z" in axes else 0

                return self._part.transform.translate(dx, dy, dz)

            return result_fn_coords

        dest_part = align_args[3]

        def result_fn(dest_shape: typing.Union[OCC.Core.TopoDS.TopoDS_Shape, Part]) -> Part:
            if not isinstance(dest_shape, OCC.Core.TopoDS.TopoDS_Shape):
                # must be a part
                dest_shape = dest_shape.shape

            align_source = getattr(source_extents, f"xyz_{source_part}")
            align_dest = getattr(op.Extents(dest_shape), f"xyz_{dest_part}")

            dx = align_dest[0] - align_source[0] if "x" in axes else 0
            dy = align_dest[1] - align_source[1] if "y" in axes else 0
            dz = align_dest[2] - align_source[2] if "z" in axes else 0

            return self._part.transform.translate(dx, dy, dz)

        return result_fn


class PartLoft:
    
    def __init__(self, part: Part):
        self._part = part

    def pipe(self,
             spine_part: Part,
             transition_mode: OCC.Core.BRepBuilderAPI.BRepBuilderAPI_TransitionMode =
                OCC.Core.BRepBuilderAPI.BRepBuilderAPI_TransitionMode.BRepBuilderAPI_RightCorner,
             bi_normal_mode: gp.gp_Dir = None,
             aux_spine: typing.Optional[Part] = None):

        if not isinstance(spine_part, Part):
            raise ValueError(f"Spine should be of type Part (was: {type(spine_part)})")

        if bi_normal_mode is not None and aux_spine is not None:
            raise ValueError("At most one of bi_normal_mode and aux_spine may be specified")

        binorm_cache = None if bi_normal_mode is None else (bi_normal_mode.X(), bi_normal_mode.Y(), bi_normal_mode.Z())

        token = self._part.cache_token.mutated("loft", "pipe", spine_part, aux_spine, transition_mode, binorm_cache)

        def _do():
            spine = spine_part.shape

            profile = self._part.make.wire().shape

            mps = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakePipeShell(spine)
            mps.Add(profile)
            mps.SetTransitionMode(transition_mode)

            if bi_normal_mode is not None:
                mps.SetMode(bi_normal_mode)

            if aux_spine is not None:
                mps.SetMode(aux_spine.shape, True)

            if not mps.IsReady():
                raise RuntimeError("PipeBuilder failure")

            try:
                mps.Build()
            except RuntimeError as e:
                raise RuntimeError("Exception during build, have you run BuildCurves3d ?", e)

            mps.MakeSolid()

            return self._part.perform_make_shape(token, mps)

        return self._part.cache_token.get_cache().ensure_exists(token, _do)

    def between(self, from_name: str, to_name: str, fix_small_faces: bool=True, **kwargs):
        from_shape = self._part.get_single(from_name)
        to_shape = self._part.get_single(to_name)

        result = PartFactory.loft([
            op.InterrogateUtils.get_outer_wire(from_shape),
            op.InterrogateUtils.get_outer_wire(to_shape)
        ], first_shape_name=from_name, last_shape_name=to_name, **kwargs)

        if fix_small_faces:
            fsf = OCC.Core.ShapeFix.ShapeFix_FixSmallFace()
            fsf.Init(result.shape)
            fsf.Perform()

            shape = fsf.Shape()

            result = result.map_subshape_changes(fsf.Shape(), mks=fsf.Context().History())

        return result


class PartRevol:

    def __init__(self, part):
        self._part = part

    def about(self,
              ax: gp.gp_Ax1,
              radians: float,
              offset: typing.Tuple[float, float, float] = None,
              symmetric: bool = False) -> Part:

        ax_params = ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()

        if offset is not None:
            ax = ax.Translated(gp.gp_Vec(*offset))

        token = self._part.cache_token.mutated("revol", "about", ax_params, radians, offset, symmetric)
        make_shape = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeRevol(self._part.shape, ax, radians)
        result = self._part.perform_make_shape(token, make_shape)

        if not symmetric:
            return result

        return result.transform.rotate(ax, -radians/2)

class ThreadSpec:

    METRIC_THREAD_TABLE = {
        "M1.6": (0.35, 1.6),
        "M1.8": (0.35, 1.8),
        "M2": (0.4, 2),
        "M2.2": (0.45, 2.2),
        "M2.5": (0.45, 2.5),
        "M3": (0.5, 3),
        "M3.5": (0.6, 3.5),
        "M4": (0.7, 4),
        "M4.5": (0.75, 4.5),
        "M5": (0.8, 5),
        "M6": (1, 6),
        "M7": (1, 7),
        "M8": (1.25, 8),
        "M10": (1.5, 10),
        "M12": (1.75, 12),
        "M14": (2, 14),
        "M16": (2, 16),
        "M18": (2.5, 18),
        "M20": (2.5, 20),
        "M22": (2.5, 22),
        "M24": (3, 24),
        "M27": (3, 27),
        "M30": (3.5, 30),
        "M33": (3.5, 33),
        "M36": (4, 36),
        "M39": (4, 39),
        "M42": (4.5, 42),
        "M45": (4.5, 45),
        "M48": (5, 48),
        "M52": (5, 52),
        "M56": (5.5, 56),
        "M60": (5.5, 60),
        "M64": (6, 64),
        "M68": (6, 68)
    }

    def __init__(self, pitch: float, basic_major_diameter: float):
        self.basic_major_diameter = basic_major_diameter
        self.pitch = pitch

        self.is_exterior = False
        self.fundamental_triangle_height = self.pitch * math.sqrt(3) / 2

        self.d1_basic_minor_diameter = self.basic_major_diameter - 1.25 * self.fundamental_triangle_height
        self.d2_basic_pitch_diameter = self.basic_major_diameter - 0.75 * self.fundamental_triangle_height

    @staticmethod
    def metric(name: str) -> ThreadSpec:
        name_upper = name.upper()

        if name_upper not in ThreadSpec.METRIC_THREAD_TABLE:
            raise ValueError(f"Cannot find thread profile {name} in thread table.")

        return ThreadSpec(*ThreadSpec.METRIC_THREAD_TABLE[name_upper])


class PartFactory:

    def __init__(self, cache: PartCache):
        self._cache = cache

    def parabola(self, focal_dist: float, a1: float, a2: float):
        parab = gp.gp_Parab(gp.gp_ZOX(), focal_dist)

        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(parab, a1, a2).Edge()
        op.GeomUtils.build_curves_3d(edge)

        focal_point = self.vertex(0, 0, focal_dist).name("focal_point")

        return self.compound(
            Part(self._cache.create_token("part_factory", "parabola", focal_dist, a1, a2), SubshapeMap.from_single_shape(edge)).name("curve"),
            focal_point)

    def angle_wire(self,
                   angle_radians: float,
                   length: float):
        """
        Generates an angle wire in xy with the center at origin
        @param angle_radians:
        @param length:
        @return:
        """

        half_angle = angle_radians / 2

        x0 = -length * math.sin(half_angle)
        y0 = length * math.cos(half_angle)

        x2 = -x0
        y2 = y0

        return op.WireSketcher(x0, y0, 0).line_to(0, 0, 0).line_to(x2, y2, 0).get_wire_part(self._cache)

    def arrange(self,
                *parts: Part,
                spacing: float = 0,
                snap_z: bool = False):
        part = parts[0]

        result = [part]

        x_max = part.extents.x_max

        for p in parts[1:]:
            p = p.align().x_min_to(x=x_max + spacing)

            if snap_z:
                p = p.align().z_min_to_min(result[-1])

            result.append(p)
            x_max = p.extents.x_max

        return self.compound(*result)

    def face(self,
             outer_wire: Part,
             *inner_wires: Part,
             surface: typing.Optional[OCC.Core.Geom.Geom_Surface] = None):

        mkf = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(outer_wire.shape)

        for w in inner_wires:
            mkf.Add(w.make.wire().shape.Reversed())

        return Part(self._cache.create_token("part_factory", "face", mkf.Face()),
                    SubshapeMap.from_single_shape(mkf.Face()))

    def thread(self,
               thread_spec: ThreadSpec,
               exterior: bool,
               length: float,
               h_clearance: float = 0,
               v_clearance: float = 0,
               separate_sections = True):

        token = self._cache.create_token(thread_spec, exterior, length, h_clearance, v_clearance, separate_sections)

        def _do():
            #overshoot and trim down excess thread
            build_length = length + 4 * thread_spec.pitch

            l2 = thread_spec.pitch * 1 / 16
            l1 = thread_spec.pitch * 1 / 8

            # first generate the fundamental triangle
            if exterior:
                tri = op.WireSketcher(0, 0, -l1) \
                    .line_to(z=-thread_spec.pitch + l1) \
                    .line_to(x=thread_spec.fundamental_triangle_height / 4, is_relative=True) \
                    .line_to(x=thread_spec.fundamental_triangle_height * 7/8, z=-thread_spec.pitch /2 - l2) \
                    .line_to(z=2 * l2, is_relative=True) \
                    .line_to(x=thread_spec.fundamental_triangle_height / 4, z=-l1) \
                    .close() \
                    .get_wire_part(self._cache)
            else:
                tri = op.WireSketcher(thread_spec.fundamental_triangle_height / 4, 0, l1) \
                    .line_to(z=-2 * l1, is_relative=True) \
                    .line_to(x=thread_spec.fundamental_triangle_height * 7 / 8, z=-thread_spec.pitch / 2 + l2) \
                    .line_to(x=thread_spec.fundamental_triangle_height / 8, is_relative=True) \
                    .line_to(z=thread_spec.pitch - 2 * l2, is_relative=True) \
                    .line_to(x=-thread_spec.fundamental_triangle_height / 8, is_relative=True) \
                    .close() \
                    .get_wire_part(self._cache)

            if v_clearance != 0:
                tri = tri.transform.scale_to_z_span(tri.extents.z_span - v_clearance) \
                    .align().z_mid_to_mid(tri)

            if h_clearance != 0:
                tri = tri.transform.scale_to_x_span(tri.extents.x_span - h_clearance) \
                    .align().x_min_to_min(tri)

            tri = tri \
                .transform.translate(dx=thread_spec.d1_basic_minor_diameter / 2 - thread_spec.fundamental_triangle_height / 4) \
                .transform.translate(dz=-thread_spec.pitch)

            n_turns = build_length / thread_spec.pitch

            if separate_sections:
                half_turn_helix = self.helix(height=0.5 * build_length / n_turns,
                                             radius=thread_spec.d2_basic_pitch_diameter / 2,
                                             n_turns=0.5)

                half_turn = tri.loft.pipe(half_turn_helix, bi_normal_mode=gp.gp.DZ())
                half_turns = []
                for i in range(0, round(n_turns) * 2):
                    z_offset = thread_spec.pitch * i / 2
                    if i % 2 != 0:
                        half_turns.append(half_turn.tr.rz(math.radians(180))
                                          .tr.mv(dz=z_offset))
                    else:
                        half_turns.append(half_turn.tr.mv(dz=z_offset))

                thread = self.compound(*half_turns)
            else:
                helix = self.helix(
                    height=build_length,
                    radius=thread_spec.d2_basic_pitch_diameter / 2,
                    n_turns=n_turns)

                thread = tri.loft.pipe(helix, bi_normal_mode=gp.gp.DZ())

            # use end caps to slice the thread start and end
            cut_box = self.box_surrounding(thread, 1, 1, 0)
            cut_bottom = cut_box \
                .transform.translate(dz=-cut_box.extents.z_max)

            cut_top = cut_box \
                .transform.translate(dz=-cut_box.extents.z_min + length)

            thread = thread.bool.cut(cut_bottom)
            thread = thread.bool.cut(cut_top)

            thread = thread.cleanup()

            return thread.with_cache_token(token)

        return self._cache.ensure_exists(token, _do)

    def trapezoid(self,
                  height: float, l_top: float, l_bottom: float):
        return op.WireSketcher(-l_bottom / 2, 0, 0) \
            .line_to(x=l_bottom / 2) \
            .line_to(x=l_top / 2, y=height) \
            .line_to(x=-l_top / 2) \
            .close() \
            .get_wire_part(self._cache)

    def helix_by_angle(self, height: float, radius: float, helix_angle: float):
        """
        Define a helix by the angle made to the plane normal to the helix height direction
        """

        sweep_distance = height * math.tan(helix_angle)
        sweep_angle = sweep_distance / radius
        sweep_n_turns = sweep_angle * 0.5 / math.pi

        return self.helix(height, radius, sweep_n_turns)

    def helix(self,
              height: float,
              radius: float,
              n_turns: float):

        token = self._cache.create_token("part_factory", "helix", height, radius, n_turns)

        def _do():

            end_angle = n_turns * 2.0 * math.pi

            pnt_start = OCC.Core.gp.gp_Pnt2d(0, 0)
            pnt_end = OCC.Core.gp.gp_Pnt2d(end_angle, height)

            lin = OCC.Core.GCE2d.GCE2d_MakeSegment(pnt_start, pnt_end).Value()

            surf = Geom_CylindricalSurface(gp.gp_Ax3(gp.gp.XOY()), radius)

            edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(lin, surf).Edge()
            op.GeomUtils.build_curves_3d(edge)

            return Part(token,
                        SubshapeMap.from_single_shape(OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(edge).Wire()))

        return self._cache.ensure_exists(token, _do)

    def conical_helix(self,
                      height: float,
                      radius_0: float,
                      radius_1: float,
                      n_turns: float):

        conical_angle = math.atan((radius_1 - radius_0) / height)

        end_u_angle = n_turns * 2.0 * math.pi
        end_v_height = -math.sqrt(height * height + (radius_1 - radius_0) * (radius_1 - radius_0))

        pnt_start = OCC.Core.gp.gp_Pnt2d(0, 0)
        pnt_end = OCC.Core.gp.gp_Pnt2d(end_u_angle, end_v_height)

        lin = OCC.Core.GCE2d.GCE2d_MakeSegment(pnt_start, pnt_end).Value()

        cone = gp.gp_Cone(gp.gp_Ax3(gp.gp.Origin(), gp.gp.DZ(), gp.gp.DX()), conical_angle, radius_1)

        surf = Geom_ConicalSurface(cone)

        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(lin, surf).Edge()
        op.GeomUtils.build_curves_3d(edge)

        return Part(
            self._cache.create_token("part_factory", "conical_helix", height, radius_0, radius_1, n_turns),
            SubshapeMap.from_unattributed_shapes(OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(edge).Wire())) \
            .align().z_min_to(z=0)

    def cone(self,
             r1: float, r2: float, height: float):
        return Part(self._cache.create_token("part_factory", "cone", r1, r2, height),
                    SubshapeMap.from_unattributed_shapes(
                        OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeCone(r1, r2, height).Shape()))

    class PolygonDriver(PartDriver):

        def __init__(self, part: Part):
            super().__init__(part)

        def set_flat_to_flat_dist(self, dist: float):
            n_segments = int(self.part.annotations["n_segments"])

            if n_segments % 2 != 0:
                raise ValueError("Cannot set flat-flat dist on an odd number of segments.")

            seg_0 = self.part.sp(f"segment_{0}")
            seg_half = self.part.sp(f"segment_{int(n_segments / 2)}")

            v_0 = seg_0.explore.vertex.get()[0]
            v_1 = seg_half.explore.vertex.get()[1]

            x0, y0, z0 = op.InterrogateUtils.vertex_to_xyz(v_0.shape)
            x1, y1, z1 = op.InterrogateUtils.vertex_to_xyz(v_1.shape)

            current_flat_flat_dist = math.sqrt((x1 - x0)**2 + (y1 - y0)**2 + (z1 - z0)**2)
            scale = dist / current_flat_flat_dist

            center = self.part.sp("center")
            cx, cy, cz = op.InterrogateUtils.vertex_to_xyz(center.shape)

            return self.part.tr.scale(scale, cx, cy, cz)

    def polygon(self,
                radius: float,
                segments: int,
                rotation_radians: float = None,
                offset: typing.Tuple[float, float, float] = None):
        d_theta = 2.0 * math.pi / segments

        ws = op.WireSketcher(
            radius * math.cos(0),
            radius * math.sin(0),
            0)

        for i in range(1, segments):
            ws.line_to(radius * math.cos(d_theta * i), radius * math.sin(d_theta * i), 0,
                       label=f"segment_{i - 1}")

        result = ws.close(label=f"segment_{segments - 1}").get_wire_part(self._cache)

        if rotation_radians is not None:
            result = result.tr.rz(rotation_radians)

        if offset is not None:
            result = result.tr.mv(*offset)

        return result.name("body") \
            .add(self.vertex(0, 0, 0).name("center"), self.circle(radius).name("bounding_circle")) \
            .annotate("n_segments", segments) \
            .with_driver(PartFactory.PolygonDriver)

    def capsule(self, center_distance: float, diameter: float) -> Part:
        return op.WireSketcher().line_to(x=center_distance, is_relative=True) \
            .circle_arc_to(0, -diameter, 0, radius=diameter / 2, is_relative=True, direction=gp.gp_Dir(0, 0, -1)) \
            .line_to(x=-center_distance, is_relative=True) \
            .circle_arc_to(0, diameter, 0, radius=diameter / 2, is_relative=True, direction=gp.gp_Dir(0, 0, -1)) \
            .close() \
            .get_face_part(self._cache) \
            .align().com_to_origin()

    def shell(self, *parts: Part):
        if len(parts) == 0:
            return parts[0].make.shell()

        builder = OCC.Core.BRep.BRep_Builder()
        result = OCC.Core.TopoDS.TopoDS_Shell()
        builder.MakeShell(result)

        subshape_map = parts[0].subshapes.clone()
        for i in range(1, len(parts)):
            subshape_map.merge(parts[i].subshapes)

        for p in parts:
            builder.Add(result, p.shape)

        token = self._cache.create_token("part_factory", "shell", *parts)
        return Part(token, subshape_map.with_updated_root_shape(result))

    def compound(self, *parts: Part) -> Part:
        if len(parts) == 0:
            builder = OCC.Core.BRep.BRep_Builder()
            result = OCC.Core.TopoDS.TopoDS_Compound()
            builder.MakeCompound(result)
            return Part(parts[0].cache_token.mutated("part_factory", "compound_of_single_element"), result)

        p = parts[0]

        if len(parts) == 1:
            return p

        return p.add(*parts[1:])

    def union(self, *parts: Part) -> Part:
        if len(parts) == 0:
            raise ValueError("At least one part required")

        start = parts[0]

        if len(parts) > 1:
            start = start.bool.union(*parts[1:])

        return start

    def section(self, *parts: Part) -> Part:
        if len(parts) == 0:
            raise ValueError("At least one part required")

        start = parts[0]

        if len(parts) > 1:
            start = start.bool.section(*parts[1:])

        return start

    def text(self,
             text: str,
             font_name: str,
             size: float,
             font_aspect: int = OCC.Core.Addons.Font_FontAspect_Regular,
             is_composite_curve: bool = False):

        token = self._cache.create_token("part_factory", "text", text, font_name, size, font_aspect, is_composite_curve)

        def _do():
            return Part(
                token,
                SubshapeMap.from_single_shape(OCC.Core.Addons.text_to_brep(text, font_name, font_aspect, size, is_composite_curve)))

        return self._cache.ensure_exists(token, _do)

    def hex_lattice(self,
                    rows: int,
                    cols: int,
                    hex_radius: float = 0.9,
                    grid_radius: float = 1,
                    truncate_odd_rows: bool = False,
                    cube_hex_effect_a: bool = False,
                    cube_hex_effect_b: bool = False,
                    cube_hex_line_thickness: float = None,
                    modifier_callback: typing.Optional[typing.Callable[[int, int, Part], Part]] = None) -> Part:

        token = self._cache.create_token("part_factory",
                                         "hex_lattice",
                                         rows,
                                         cols,
                                         hex_radius,
                                         grid_radius,
                                         truncate_odd_rows,
                                         cube_hex_effect_a,
                                         cube_hex_effect_b,
                                         cube_hex_line_thickness,
                                         inspect.getsource(modifier_callback) if modifier_callback is not None else None,
                                         inspect.getsource(PartFactory.hex_lattice))

        def _do():
            if modifier_callback is None:
                mc = lambda r, c, unit_part: unit_part

            base_polygon = self.polygon(hex_radius, 6)
            base_shape = Part.of_shape(base_polygon.sp("body").make.face().shape)

            if cube_hex_effect_a:
                top = base_polygon.sp("segment_0").explore.vertex.get()[0]
                br = base_polygon.sp("segment_2").explore.vertex.get()[0]
                bl = base_polygon.sp("segment_4").explore.vertex.get()[0]

                center = base_polygon.sp("center")

                cuts = [
                    op.WireSketcher(*center.xts.xyz_mid).line_to(*top.xts.xyz_mid).get_wire_part(self._cache),
                    op.WireSketcher(*center.xts.xyz_mid).line_to(*bl.xts.xyz_mid).get_wire_part(self._cache),
                    op.WireSketcher(*center.xts.xyz_mid).line_to(*br.xts.xyz_mid).get_wire_part(self._cache)]

                if cube_hex_line_thickness is None:
                    line_thickness = 2 * (grid_radius - hex_radius)
                else:
                    line_thickness = cube_hex_line_thickness

                cuts = [w.extrude.offset(line_thickness / 2, spine=gp.gp.XOY()).make.face() for w in cuts]
                base_shape = base_shape.bool.cut(*cuts)

            if cube_hex_effect_b:
                top = base_polygon.sp("segment_1").explore.vertex.get()[0]
                br = base_polygon.sp("segment_3").explore.vertex.get()[0]
                bl = base_polygon.sp("segment_5").explore.vertex.get()[0]

                center = base_polygon.sp("center")

                cuts = [
                    op.WireSketcher(*center.xts.xyz_mid).line_to(*top.xts.xyz_mid).get_wire_part(self._cache),
                    op.WireSketcher(*center.xts.xyz_mid).line_to(*bl.xts.xyz_mid).get_wire_part(self._cache),
                    op.WireSketcher(*center.xts.xyz_mid).line_to(*br.xts.xyz_mid).get_wire_part(self._cache)]

                if cube_hex_line_thickness is None:
                    line_thickness = 2 * (grid_radius - hex_radius)
                else:
                    line_thickness = cube_hex_line_thickness

                cuts = [w.extrude.offset(line_thickness / 2, spine=gp.gp.XOY()).make.face() for w in cuts]
                base_shape = base_shape.bool.cut(*cuts)

            col_spacing = grid_radius * 3
            row_spacing = math.sqrt(3) * 0.5 * grid_radius

            subparts = []
            for row in range(0, rows):
                y = row_spacing * row

                x_offs = 0 if row % 2 == 0 else 3 * grid_radius * 0.5
                for c in range(0, cols):
                    if row % 2 != 0 and c == cols - 1 and truncate_odd_rows:
                        continue

                    x = col_spacing * c + x_offs

                    subpart = base_shape.transform.translate(dx=x, dy=y)

                    subpart = mc(row, c, subpart)

                    subparts += subpart.explore.face.get()

            return self.compound(*subparts).with_cache_token(token)

        return self._cache.ensure_exists(token, _do)

    def lattice(self, rows: int, cols: int, diag_a: bool=False, diag_b: bool=False) -> Part:
        wires = []


        # create rows
        wires = wires + [ op.WireSketcher(0, y, 0).line_to(x=cols, is_relative=True).get_wire_part(self._cache) for y in range(0, rows + 1)]

        # create columns
        wires = wires + [ op.WireSketcher(x, 0, 0).line_to(y=rows, is_relative=True).get_wire_part(self._cache) for x in range(0, cols + 1)]

        # create diagonals
        if diag_a or diag_b:
            for row in range(-cols, rows):
                x0 = 0
                y0 = row

                x1 = cols
                y1 = row + rows

                if y0 < 0:
                    offset = -y0
                    y0 += offset
                    x0 += offset

                if y1 > rows:
                    offset = y1 - rows
                    y1 -= offset
                    x1 -= offset

                if x0 != x1 and y0 != y1:
                    if diag_a:
                        wires += [op.WireSketcher(x0, y0, 0).line_to(x1, y1).get_wire_part(self._cache)]

                    if diag_b:
                        wires += [op.WireSketcher(cols - x0, y0, 0).line_to(cols - x1, y1).get_wire_part(self._cache)]

        return self.compound(*wires)

    def sphere(self, radius: float) -> Part:
        return Part(
            self._cache.create_token("part_factory", "sphere", radius),
            SubshapeMap.from_unattributed_shapes(OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeSphere(radius).Shape()))

    def circle(self, radius: float) -> Part:
        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(gp.gp_Circ(gp.gp.XOY(), radius)).Edge()

        wire = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(edge).Wire()

        return Part(self._cache.create_token("part_factory", "circle", radius), SubshapeMap.from_unattributed_shapes(wire))

    def right_angle_triangle(
            self,
            hypot: float,
            angle: float,
            h_label: str = None,
            adj_label: str = None,
            op_label: str = None,
            pln: gp.gp_Ax2 = None) -> Part:

        if pln is None:
            pln = gp.gp.XOY()

        adj_length = hypot * math.cos(angle)
        op_length = hypot * math.sin(angle)

        xdir = pln.XDirection()
        ydir = pln.YDirection()

        da = gp.gp_Vec(xdir).Normalized().Scaled(adj_length)
        do = gp.gp_Vec(ydir).Normalized().Scaled(op_length)

        return op.WireSketcher() \
            .line_to(x=da.X(), y=da.Y(), z=da.Z(), label=adj_label) \
            .line_to(x=do.X(), y=do.Y(), z=do.Z(), label=op_label) \
            .close(label=h_label) \
            .get_wire_part(self._cache)

    def vertex(self, x: float = 0, y: float = 0, z: float = 0, name: str = None):
        shape = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(OCC.Core.gp.gp_Pnt(x, y, z)).Shape()

        token = self._cache.create_token("part_factory", "vertex", x, y, z, name)

        if name is None:
            return Part(token, SubshapeMap.from_unattributed_shapes(shape))
        else:
            return Part(token, SubshapeMap.from_unattributed_shapes(shape, {name: [shape]}))

    @staticmethod
    def x_line(length: float, symmetric: bool = False):
        return op.WireSketcher().line_to(x=length).get_wire_part() \
            .do(lambda p: p.align().x_mid_to((0, 0, 0)) if symmetric else p)

    @staticmethod
    def y_line(length: float, symmetric: bool = False):
        return op.WireSketcher().line_to(y=length).get_wire_part() \
            .do(lambda p: p.align().y_mid_to((0, 0, 0)) if symmetric else p)

    @staticmethod
    def z_line(length: float, symmetric: bool = False):
        return op.WireSketcher().line_to(z=length).get_wire_part() \
            .do(lambda p: p.align().z_mid_to((0, 0, 0)) if symmetric else p)

    def loft(self,
             wires_or_faces: typing.List[Part],
             is_solid: bool = True,
             is_ruled: bool = True,
             pres3d: bool = 1.0e-6,
             first_shape_name: str = None,
             last_shape_name: str = None,
             loft_profile_name: str = None):

        ts = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_ThruSections(is_solid, is_ruled, pres3d)

        if len(wires_or_faces) < 2:
            raise ValueError("Must specify at least 2 wires")

        for w in wires_or_faces:
            if w.inspect.is_vertex():
                ts.AddVertex(w.shape)
            else:
                ts.AddWire(op.InterrogateUtils.outer_wire(w.shape))

        ts.Build()

        named_subshapes = {}
        if first_shape_name is not None:
            named_subshapes[first_shape_name] = [ts.FirstShape()]

        if last_shape_name is not None:
            named_subshapes[last_shape_name] = [ts.LastShape()]

        if loft_profile_name is not None:
            named_subshapes[loft_profile_name] = []
            for w in wires_or_faces:
                for e in w.explore.edge.get():
                    for f in op.ListUtils.iterate_list(ts.Generated(e.shape)):
                        named_subshapes[loft_profile_name] += [f]

        token = self._cache.create_token(ts.Shape())
        return Part(token,
                    SubshapeMap.from_unattributed_shapes(ts.Shape(), named_subshapes)) \
            .perform_make_shape(token, ts)

    def rectangle(self,
                  x0: float,
                  y0: float,
                  x1: float,
                  y1: float,
                  x0_edge_name: typing.Optional[str] = None,
                  x1_edge_name: typing.Optional[str] = None,
                  y0_edge_name: typing.Optional[str] = None,
                  y1_edge_name: typing.Optional[str] = None):
        return op.WireSketcher(x0, y0, 0) \
            .line_to(x1, y0, label=y0_edge_name) \
            .line_to(x1, y1, label=x1_edge_name) \
            .line_to(x0, y1, label=y1_edge_name) \
            .close(label=x0_edge_name) \
            .get_face_part(self._cache)

    def square_centered(self,
                        dx: float,
                        dy: float,
                        x_min_name: typing.Optional[str] = None,
                        x_max_name: typing.Optional[str] = None,
                        y_min_name: typing.Optional[str] = None,
                        y_max_name: typing.Optional[str] = None,
                        fill_face: bool = True,
                        center_on: typing.Optional[Part] = None) -> Part:

        hdx = 0.5 * dx
        hdy = 0.5 * dy

        ws = op.WireSketcher(gp.gp_Pnt(-hdx, -hdy, 0)) \
            .line_to(x=hdx, y=-hdy, label=y_min_name, is_relative=False) \
            .line_to(x=hdx, y=hdy, label=x_max_name, is_relative=False) \
            .line_to(x=-hdx, y=hdy, label=y_max_name, is_relative=False) \
            .close(label=x_min_name)

        if fill_face:
            result = ws.get_face_part(self._cache)
        else:
            result = ws.get_wire_part(self._cache)

        if center_on is not None:
            result = result.align().by("xmidymidzmid", center_on)

        return result

    def ring(self,
             r_outer: float,
             r_inner: float,
             height: float,
             top_wire_inner_name: str = None,
             bottom_wire_inner_name: str = None,
             top_wire_outer_name: str = None,
             bottom_wire_outer_name: str = None):

        if r_outer <= 0 or r_inner <= 0:
            raise ValueError("r_outer / r_inner must be greater than zero")

        if r_outer <= r_inner:
            raise ValueError("Outer radius must be greater than inner radius")

        return self.cylinder(
            r_outer,
            height,
            top_wire_outer_name,
            bottom_wire_outer_name).bool.cut(
            self.cylinder(
                r_inner,
                height,
                top_wire_inner_name,
                bottom_wire_inner_name))

    def cylinder(self,
                 radius: float,
                 height: float,
                 top_wire_name: str = None,
                 bottom_wire_name: str = None) -> Part:

        height_abs = abs(height)

        cylinder = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeCylinder(radius, height_abs).Shape()
        wires = op.Explorer(cylinder, OCC.Core.TopAbs.TopAbs_WIRE) \
            .filter_by(lambda w: op.Extents(w).z_span < height_abs) \
            .order_by(lambda s: op.Extents(s).z_mid) \
            .get()

        named_subshapes = {}
        if top_wire_name is not None:
            named_subshapes[top_wire_name] = [wires[1]]

        if bottom_wire_name is not None:
            named_subshapes[bottom_wire_name] = [wires[0]]

        result = Part(NoOpCacheToken(), SubshapeMap.from_unattributed_shapes(cylinder, named_subshapes))

        if height < 0:
            result = result.transform.translate(dz=height)

        result = result.with_cache_token(
            self._cache.create_token("part_factory", "cylinder", radius, height, top_wire_name, bottom_wire_name))

        #print(f"CYLINDER UUID: {result.cache_token.compute_uuid()}")

        return result

    def box(self, dx: float, dy: float, dz: float,
            x_min_face_name: str = None,
            x_max_face_name: str = None,
            y_min_face_name: str = None,
            y_max_face_name: str = None,
            z_min_face_name: str = None,
            z_max_face_name: str = None) -> Part:

        mkbox = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(dx, dy, dz)

        named_parts = {}
        if x_min_face_name is not None:
            named_parts[x_min_face_name] = {mkbox.BackFace()}
        if x_max_face_name is not None:
            named_parts[x_max_face_name] = {mkbox.FrontFace()}

        if y_min_face_name is not None:
            named_parts[y_min_face_name] = {mkbox.LeftFace()}
        if y_max_face_name is not None:
            named_parts[y_max_face_name] = {mkbox.RightFace()}

        if z_min_face_name is not None:
            named_parts[z_min_face_name] = {mkbox.BottomFace()}
        if z_max_face_name is not None:
            named_parts[z_max_face_name] = {mkbox.TopFace()}

        try:
            shape = mkbox.Shape()
        except RuntimeError as e:
            print(f"Failure to create box with dimensions: {dx}, {dy}, {dz}")
            raise e

        shape = mkbox.Shape()
        return Part(self._cache.create_token(shape), SubshapeMap.from_unattributed_shapes(shape, named_parts))

    def box_centered(self,
                     dx: float, dy: float, dz: float,
                     x_min_face_name: str = None,
                     x_max_face_name: str = None,
                     y_min_face_name: str = None,
                     y_max_face_name: str = None,
                     z_min_face_name: str = None,
                     z_max_face_name: str = None) -> Part:

        result_part = self.box(dx, dy, dz,
                               x_min_face_name=x_min_face_name,
                               x_max_face_name=x_max_face_name,
                               y_min_face_name=y_min_face_name,
                               y_max_face_name=y_max_face_name,
                               z_min_face_name=z_min_face_name,
                               z_max_face_name=z_max_face_name)

        return result_part.transform.translate(-dx / 2, -dy / 2, -dz / 2)

    def box_surrounding(self,
                        part: Part,
                        x_clearance: float = 0,
                        y_clearance: float = 0,
                        z_clearance: float = 0) -> Part:

        return self.box(
            dx=part.extents.x_span + 2 * x_clearance,
            dy=part.extents.y_span + 2 * y_clearance,
            dz=part.extents.z_span + 2 * z_clearance) \
            .align().xyz_mid_to_mid(part)

    def box_centered_on(self, part: Part, dx: float, dy: float, dz: float,
                        x_min_face_name: str = None,
                        x_max_face_name: str = None,
                        y_min_face_name: str = None,
                        y_max_face_name: str = None,
                        z_min_face_name: str = None,
                        z_max_face_name: str = None):
        return self.box(dx, dy, dz,
                        x_min_face_name=x_min_face_name,
                        x_max_face_name=x_max_face_name,
                        y_min_face_name=y_min_face_name,
                        y_max_face_name=y_max_face_name,
                        z_min_face_name=z_min_face_name,
                        z_max_face_name=z_max_face_name).align().by("xmidymidzmid", part)


"""
=========================
Part query section
=========================
"""

Shape = OCC.Core.TopoDS.TopoDS_Shape
Edge = OCC.Core.TopoDS.TopoDS_Edge
Wire = OCC.Core.TopoDS.TopoDS_Wire
Shell = OCC.Core.TopoDS.TopoDS_Shell
Solid = OCC.Core.TopoDS.TopoDS_Solid
Compound = OCC.Core.TopoDS.TopoDS_Compound


class QuantityResolver:

    def get_quantity(self, *args: Shape) -> typing.List[Shape]:
        raise NotImplementedError()


class ExactQuantityResolver(QuantityResolver):

    def __init__(self, amount: int):
        self._amount = amount

    def get_quantity(self, *args: Shape) -> typing.List[Shape]:
        if len(args) != self._amount:
            raise ValueError(f"Unexpected args number (expected {self._amount}), was {len(args)}")

        return [s for s in args]


class SliceQuantityResolver(QuantityResolver):

    def __init__(self, index_from: typing.Optional[int], index_to: typing.Optional[int]):
        self._index_from = index_from
        self._index_to = index_to

    def get_quantity(self, *args: Shape) -> typing.List[Shape]:
        return [s for s in args[self._index_from:self._index_to]]


class AllQuantityResolver(QuantityResolver):

    def get_quantity(self, *args: Shape) -> typing.List[Shape]:
        return [s for s in args]


class ShapeSpecifier:

    SHAPE_TYPES = {
        "s": OCC.Core.TopAbs.TopAbs_SHAPE,
        "v": OCC.Core.TopAbs.TopAbs_VERTEX,
        "e": OCC.Core.TopAbs.TopAbs_EDGE,
        "w": OCC.Core.TopAbs.TopAbs_WIRE,
        "f": OCC.Core.TopAbs.TopAbs_FACE,
        "sh": OCC.Core.TopAbs.TopAbs_SHELL,
        "so": OCC.Core.TopAbs.TopAbs_SOLID,
        "c": OCC.Core.TopAbs.TopAbs_COMPOUND
    }

    def __init__(self, shape_name: str):
        if not shape_name in ShapeSpecifier.SHAPE_TYPES:
            raise ValueError("Unrecognized shape type")

        self._expected_shape_type = ShapeSpecifier.SHAPE_TYPES[shape_name]

    def get_shapes(self, part: Part) -> typing.List[Part]:
        """
        :return: The set of shapes to be considered for filtering
        """
        return PartExplorer(part, self._expected_shape_type).get()


class ShapeFilter:

    def filter(self, part: Part, filter_inputs: typing.Generator[Part, None, None]) -> \
            typing.Generator[Part, None, None]:
        raise NotImplementedError()


class ShapeLabelledFilter(ShapeFilter):

    def __init__(self, label: str):
        self._is_prefix = label.endswith("*")

        if self._is_prefix:
            self._label = label[:-1]
        else:
            self._label = label

    def filter(self, part: Part, filter_inputs: typing.Generator[Part, None, None]) -> \
            typing.Generator[Part, None, None]:

        candidate_shapes = set()

        # apply the label filter
        if self._is_prefix:
            part = part.prefixed_subparts(self._label)
            for l, subshapes in part.subshapes.map.items():
                for s in subshapes:
                    candidate_shapes.add(s)
        else:
            subshapes = part.subshapes

            if not self._label in subshapes.keys():
                raise ValueError(f"Label: \"{self._label}\" is not present in the part.")

            candidate_shapes = {s for s in subshapes[self._label]}

        fi = [s for s in filter_inputs]

        for s in fi:
            if s.subshapes.root_shape in candidate_shapes:
                yield s


class ShapeValidation:

    def __init__(self, quantity_resolver: QuantityResolver, shape_specifier: ShapeSpecifier):
        self._quantity_resolver = quantity_resolver
        self._shape_specifier = shape_specifier

    def get_shapes(self, part: Part) -> typing.List[Shape]:
        shapes = self._shape_specifier.get_shapes(part)
        return self._quantity_resolver.get_quantity(*shapes)


class SubshapeResolver:

    def __init__(self,
                 shape_speicifer: ShapeSpecifier,
                 quantity_resolver: QuantityResolver,
                 filters: typing.List[ShapeFilter]):
        self._shape_specifier = shape_speicifer
        self._quantity_resolver = quantity_resolver
        self._filters = [s for s in filters]

    def get_shapes(self, part: Part) -> typing.List[Part]:
        typed_shapes = self._shape_specifier.get_shapes(part)

        filtered_shapes = typed_shapes
        for shape_filter in self._filters:
            filtered_shapes = [s for s in shape_filter.filter(part, (fs for fs in filtered_shapes))]

        return self._quantity_resolver.get_quantity(*filtered_shapes)


# noinspection PyMethodMayBeStatic
class SubshapeResolverVisitor(parsimonious.NodeVisitor):

    def visit_subshape_resolver(self, node, visited_children):
        quantity_resolver, shape_specifier = visited_children[0]

        shape_filters = visited_children[1]

        return SubshapeResolver(shape_specifier, quantity_resolver, shape_filters)

    def visit_quantity_exact(self, node, visited_children):
        return ExactQuantityResolver(int(node.text))

    def visit_quantity_all(self, node, visited_children):
        return AllQuantityResolver()

    def visit_quantity_slice(self, node, visited_children):
        r0, r1 = node.children[1].text.split(":")
        return SliceQuantityResolver(
            int(r0) if r0.isdigit() else None,
            int(r1) if r1.isdigit() else None
        )

    def visit_quantity_resolver(self, node, visited_children):
        # can consist of multiple types, all implementing QuantityResolver
        return visited_children[0]

    def visit_shape_specifier(self, node, visited_children):
        return ShapeSpecifier(node.text)

    def visit_filter(self, node, visited_children):
        # can consist of multiple types, all implementing ShapeFilter
        return visited_children[0]

    def visit_filters(self, node, visited_children):
        return [f for c in visited_children for f in c if isinstance(f, ShapeFilter)]

    def visit_label_filter(self, node, visited_children):
        return ShapeLabelledFilter(node.children[1].text)

    def generic_visit(self, node, visited_children):
        """ The generic visit method. """
        return visited_children or node


class PartQuery:

    grammar = Grammar(
        """
        subshape_resolver               = validation_part filters

        validation_part                 = quantity_resolver shape_specifier

        filters                         = ("," filter)*
        filter                          = label_filter

        # p: modified in previous operation
        # l: has label
        label_filter                    = "l(" (label "*"?) ")"

        shape_specifier                 = "v" / "e" / "w" / "f" / "sh" / "so" / "c" / "s"

        quantity_resolver               = quantity_slice / quantity_exact / quantity_all

        quantity_slice                  = "[" ((integer ":" integer) / (":" integer) / (integer ":") / integer / ":") "]"
        quantity_exact                  = abs_integer / digit
        quantity_all                    = "*"

        label                           = ~"[a-z]"i (alphanum / "_" / "/")+
        alphanum                        = ~"[a-z 0-9]+"i
        integer                         = "-"? abs_integer
        abs_integer                     = ((~"[1-9]" digit+) / digit)
        digit                           = ~"[0-9]"
        """)

    def __init__(self, part: Part, to_subpart: bool):
        self._part = part
        self._to_subpart = to_subpart

    def __call__(self, query: str):
        syntax_tree = PartQuery.grammar.parse(query)

        visitor = SubshapeResolverVisitor()

        subshape_resolver: SubshapeResolver = visitor.visit(syntax_tree)

        shapes = subshape_resolver.get_shapes(self._part)

        if not self._to_subpart:
            return [s.shape for s in shapes]
        else:
            return PartFactory(self._part.cache_token.get_cache())\
                .compound(*shapes)\
                .with_cache_token(self._part.cache_token.mutated("part_query", query))


class PartSelectionResolver:

    SHAPE_TYPE_LOOKUP = {v: k for k, v in ShapeSpecifier.SHAPE_TYPES.items()}

    def __init__(self, part: Part, *selection: OCC.Core.TopoDS.TopoDS_Shape):
        self._part = part
        self._selection = {}

        # group the selections into types
        for s in selection:
            self._selection[s.ShapeType()] = self._selection.get(s.ShapeType(), []) + [s]

        # reverse lookup for shape labels
        self._label_cache = {}
        for label, shape_list in self._part.subshapes.items():
            for shape in shape_list:
                self._label_cache[shape] = label

    def get_suggested_selections(self) -> typing.Generator[str, None, None]:
        for shape_type, shapes in self._selection.items():
            shapes = set(shapes)

            shape_type_query = PartSelectionResolver.SHAPE_TYPE_LOOKUP[shape_type]

            all_shapes: typing.List[OCC.Core.TopoDS.TopoDS_Shape] = self._part.query_shapes(f"*{shape_type_query}")

            if set(all_shapes) == set(shapes):
                yield f"*{shape_type_query}"

            if shapes.issubset(all_shapes):
                for i0, i1 in PartSelectionResolver.get_index_ranges(shapes, all_shapes):
                    if i1 is not None:
                        yield f"{shape_type_query}[{i0}:{i1 + 1}]"
                    else:
                        yield f"{shape_type_query}[{i0}]"

            shape_labels = set(self._label_cache[s] for s in shapes if s in self._label_cache.keys())
            if len(shape_labels) == 1:
                yield f"{shape_type_query},l({shape_labels.pop()})"

    @staticmethod
    def get_index_ranges(sublist: typing.List,
                         superlist: typing.List) -> typing.Generator[typing.Tuple[int, typing.Optional[int]], None, None]:
        indices = [superlist.index(s) for s in sublist]
        indices.sort()

        while len(indices) > 0:
            start_index = indices.pop(0)
            end_index = start_index
            while len(indices) > 0 and indices[0] == end_index + 1:
                end_index = indices.pop(0)

            # by this point, have consumed all contiguous elements
            if start_index == end_index:
                yield start_index, None
            else:
                yield start_index, end_index


class PartPickResult:

    def __init__(self, section, line: OCC.Core.gp.gp_Lin, picked_part: Part):
        self._picked_part = picked_part
        curve = OCC.Core.GC.GC_MakeLine(line).Value()

        verts: typing.List[OCC.Core.TopoDS.TopAbs_VERTEX] = section.explore.vertex.get()

        def get_vert_param(vert):
            return OCC.Core.GeomAPI.GeomAPI_ProjectPointOnCurve(
                OCC.Core.BRep.BRep_Tool.Pnt(vert.shape), curve).Parameter(1)

        pruned_verts = [v for v in verts if get_vert_param(v) >= 0]

        pruned_verts.sort(key=get_vert_param)

        self._verts = pruned_verts

    def first(self) -> Part:
        return self._verts[0]

    def first_face(self) -> Part:
        return self.nth_face(0)

    def first_edge(self) -> Part:
        return self.nth_edge(0)

    def nth_face(self, n: int) -> Part:
        vertex = self.as_list()[n]

        for f in self._picked_part.explore.face.get():
            section = vertex.bool.common(f)

            if len(section.explore.vertex.get()) != 0:
                return f

        raise ValueError("No faces picked.")

    def nth_edge(self, n: int) -> Part:
        vertex = self.as_list()[n]

        for e in self._picked_part.explore.edge.get():
            section = vertex.bool.common(e)

            if len(section.explore.vertex.get()) != 0:
                return e

        raise ValueError("No edges picked.")

    def face_list(self) -> typing.List[Part]:
        return [self.nth_face(i) for i in range(0, len(self.as_list()))]

    def all(self) -> Part:
        return PartFactory(self._picked_part.cache_token.get_cache()).compound(*self._verts)

    def as_list(self) -> typing.List[Part]:
        """
        @return: the vertex list of intersections
        """

        return self._verts


class PartPick:

    def __init__(self, part: Part):
        self._part = part

    def from_dir(self, dx: float = 0, dy: float = 0, dz: float = 0):
        origin = self._part.xts.xyz_mid

        # get a number greater than the maximum possible length of the object
        max_dim = self._part.xts.x_span ** 2 + self._part.xts.y_span ** 2 + self._part.xts.z_span ** 2

        origin[0] -= dx * max_dim
        origin[1] -= dy * max_dim
        origin[2] -= dz * max_dim

        return self.dir(origin, (dx, dy, dz))

    def dir(self,
            origin: typing.Tuple[float, float, float],
            direction: typing.Tuple[float, float, float]):
        origin_pnt = OCC.Core.gp.gp_Pnt(*origin)
        direction_dir = OCC.Core.gp.gp_Dir(OCC.Core.gp.gp_Vec(*direction).Normalized())

        line = OCC.Core.gp.gp_Lin(origin_pnt, direction_dir)
        shape = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(line).Edge()
        ray = Part(self._part.cache_token.mutated("pick", shape), SubshapeMap.from_single_shape(shape))

        section = ray.bool.section(self._part)

        return PartPickResult(section, line, self._part)


class PartCast:

    def __init__(self, part: Part):
        self._part = part

    def to(self,
           part_to: Part,
           direction: typing.Optional[OCC.Core.gp.gp_Dir] = None,
           tolerance: float = Precision.precision.Confusion()) -> Part:

        return PartCast._project_to(self._part, part_to, direction, tolerance)

    @staticmethod
    def _project_to(part_from: Part,
                   part_to: Part,
                   direction: typing.Optional[OCC.Core.gp.gp_Dir] = None,
                   tolerance: float = Precision.precision.Confusion()) -> Part:
        dist = OCC.Core.BRepExtrema.BRepExtrema_DistShapeShape(
            part_from.shape,
            part_to.shape)

        dist.Perform()

        if not dist.IsDone():
            raise ValueError("Could not compute distance")

        pnt_from = dist.PointOnShape1(1)
        pnt_to = dist.PointOnShape2(1)

        if (pnt_from.Distance(pnt_to)) <= tolerance:
            # job is done
            return part_from

        translation_vector = None
        if direction is None:
            # can directly close the distance
            translation_vector = (
                pnt_to.X() - pnt_from.X(),
                pnt_to.Y() - pnt_from.Y(),
                pnt_to.Z() - pnt_from.Z())
        else:
            magnitude = OCC.Core.gp.gp_Vec(pnt_from, pnt_to).Dot(OCC.Core.gp.gp_Vec(direction))

            if magnitude == 0:
                part_from.preview(part_to)
                raise ValueError("The closest points line has no component in the specified direction.")

            translation_vector = OCC.Core.gp.gp_Vec(direction).Scaled(magnitude)
            translation_vector = (translation_vector.X(), translation_vector.Y(), translation_vector.Z())

        return PartCast._project_to(
            part_from.transform.translate(*translation_vector),
            part_to,
            direction,
            tolerance)


