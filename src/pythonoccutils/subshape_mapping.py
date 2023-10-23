from __future__ import annotations

import json
import traceback

import OCC.Core.TopoDS
import typing

from pythonoccutils.occutils_python import SetPlaceableShape, InterrogateUtils, ListUtils

T_MKS = typing.Union[
                OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeShape,
                OCC.Core.BRepTools.BRepTools_History,
                OCC.Core.BRepOffset.BRepOffset_MakeOffset]


class ShapeAttributes:

    def __init__(self, values: typing.Dict[str, str] = None):
        if values is None:
            values = dict()

        self._values = values

    def __str__(self) -> str:
        return str(self._values)

    def clone(self) -> ShapeAttributes:
        return ShapeAttributes(self._values.copy())

    @property
    def values(self):
        return self._values

    def get(self, key: str):
        if key in self._values:
            return self._values[key]

        raise ValueError(f"This shape does not have an attribute named \"{key}\"")

    def with_updated_attribute(self, key: str, value: str):
        new_values = self._values.copy()
        new_values[key] = value
        return ShapeAttributes(new_values)

    def __getitem__(self, item):
        return self._values[item]

    def __eq__(self, o: object) -> bool:
        return isinstance(o, ShapeAttributes) and o._values == self._values

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._values.items())))


class AnnotatedShape:

    def __init__(self,
                 shape: typing.Union[OCC.Core.TopoDS.TopoDS_Shape, SetPlaceableShape],
                 attributes: typing.Union[ShapeAttributes, typing.Dict[str, str]] = None):
        if not isinstance(shape, OCC.Core.TopoDS.TopoDS_Shape) and not isinstance(shape, SetPlaceableShape):
            raise ValueError("Invalid shape")

        if attributes is None:
            attributes = ShapeAttributes()
        elif isinstance(attributes, ShapeAttributes):
            attributes = attributes.clone()
        else:
            attributes = ShapeAttributes(attributes.copy())

        self._set_placeable_shape = shape if isinstance(shape, SetPlaceableShape) else SetPlaceableShape(shape)
        self._attributes = attributes

    def __repr__(self):
        return f"{self._set_placeable_shape} ({self._attributes})"

    def clone(self) -> AnnotatedShape:
        return AnnotatedShape(self._set_placeable_shape, self._attributes.clone())

    def with_updated_attribute(self, key: str, value: str) -> AnnotatedShape:
        return AnnotatedShape(
            self._set_placeable_shape,
            self._attributes.with_updated_attribute(key, value))

    @property
    def shape(self) -> OCC.Core.TopoDS.TopoDS_Shape:
        return self._set_placeable_shape.shape

    @property
    def set_placeable_shape(self) -> SetPlaceableShape:
        return self._set_placeable_shape

    @property
    def attributes(self) -> ShapeAttributes:
        return self._attributes

    def with_updated_shape(self, shape: OCC.Core.TopoDS.TopoDS_Shape) -> AnnotatedShape:
        """
        @param shape:
        @return: a new AnnotatedShape, having the same attributes but an updated shape object.
        """
        return AnnotatedShape(shape, self._attributes)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, AnnotatedShape) and self._set_placeable_shape == o._set_placeable_shape and self._attributes == o.attributes

    def __hash__(self) -> int:
        return hash((self._set_placeable_shape, self._attributes))


class SubshapeMap:
    """
    Note: subshape map is mutable. callers should create a copy before making modifications if they require
    immutability.
    """

    def __init__(self,
                 root_shape: AnnotatedShape,
                 map: typing.Dict[str, typing.Set[AnnotatedShape]] = None):
        self._root_shape = root_shape

        if map is not None:
            self._map = SubshapeMap.copy_map(map)
        else:
            self._map: typing.Dict[str, typing.Set[AnnotatedShape]] = dict()

    @staticmethod
    def from_single_shape(shape: OCC.Core.TopoDS.TopoDS_Shape):
        return SubshapeMap(AnnotatedShape(shape))

    @staticmethod
    def from_unattributed_shapes(shape: OCC.Core.TopoDS.TopoDS_Shape,
                                 map: typing.Dict[str, typing.Collection[OCC.Core.TopoDS.TopoDS_Shape]] = None):

        if map is None:
            map = dict()

        return SubshapeMap(
            AnnotatedShape(shape),
            {name: {AnnotatedShape(s) for s in shapes} for name, shapes in map.items()})

    @property
    def root_shape(self) -> AnnotatedShape:
        return self._root_shape

    @property
    def map(self) -> typing.Dict[str, typing.Set[AnnotatedShape]]:
        return self._map

    def with_updated_root_shape(self, new_shape: typing.Union[OCC.Core.TopoDS.TopoDS_Shape, AnnotatedShape]) -> SubshapeMap:
        if isinstance(new_shape, OCC.Core.TopoDS.TopoDS_Shape):
            new_shape = self._root_shape.with_updated_shape(new_shape)

        if not isinstance(new_shape, AnnotatedShape):
            raise ValueError("Expected AnnotatedShape")

        new_map = SubshapeMap.copy_map(self._map)

        # the root shape refers to itself, this should be updated in the new map
        for name in new_map.keys():
            existing_shape = [s for s in new_map[name] if s.set_placeable_shape == new_shape.set_placeable_shape]
            if len(existing_shape) != 0:
                print(f"Updating existing shape {existing_shape} to new shape {new_shape}")
                new_map[name].remove(existing_shape[0])
                new_map[name].add(new_shape)

        return SubshapeMap(new_shape, new_map)

    def place(self, name: str, shape: AnnotatedShape):
        if not isinstance(shape, AnnotatedShape):
            raise ValueError("Expected annotated shape")

        if name not in self._map:
            self._map[name] = set()

        self._map[name].add(shape)

    def merge(self, subshape_map: SubshapeMap):
        for name, shapes in subshape_map._map.items():
            for shape in shapes:
                self.place(name, shape)

    def get(self, name: str) -> typing.Set[AnnotatedShape]:
        self._assert_has(name)

        result = self._map[name]

        if len(result) == 0:
            raise ValueError(f"Subshape name \"{name}\" has zero elements associated with it {self._map}")

        return result.copy()

    def get_single(self, name: str) -> AnnotatedShape:
        self._assert_has(name)

        result = self._map[name]

        if len(result) != 1:
            raise ValueError(f"Subshape name \"{name}\" has != 1 elements associated with it {self._map}")

        return next(s for s in result)

    def _assert_has(self, name: str):
        if name not in self._map:
            raise ValueError(f"Subshape name \"{name}\" not present: available names are: {self._map.keys()}")

    def keys(self):
        return self._map.keys()

    def values(self) -> typing.Set[typing.Set[AnnotatedShape]]:
        return {v.copy() for v in self._map.values()}

    def name_for_shape(self, shape: AnnotatedShape) -> str:
        if not isinstance(shape, AnnotatedShape):
            raise ValueError("Annotated shape expected")

        for name, s in self._map.items():
            if shape in s:
                return name

        raise ValueError(f"Unable to determine name for shape")

    def contains_shape(self, shape: typing.Union[AnnotatedShape, SetPlaceableShape]) -> bool:
        set_pl = shape if isinstance(shape, SetPlaceableShape) else shape.set_placeable_shape

        for s in self._map.values():
            if any(ss.set_placeable_shape == set_pl for ss in s):
                return True

        return False

    def items(self) -> typing.Generator[typing.Tuple[str, typing.Set[AnnotatedShape]], None, None]:
        for k, v in self._map.items():
            yield k, v.copy()

    def remove(self, shape: AnnotatedShape):
        for n, s in self._map.items():
            if shape in s:
                s.remove(shape)

    def rename(self, old_name: str, new_name: str):
        if old_name not in self._map:
            raise ValueError(f"Old subshape set name {old_name} not present in subshape map")

        if new_name in self._map:
            raise ValueError(f"New name {new_name} already has a subshape set associated with it")

        self._map[new_name] = self._map[old_name]
        del self._map[old_name]

    def annotate_subshape(self, name: str, key: str, value: str):
        if name not in self._map:
            raise ValueError(f"No label with name: {name}")

        annotated_shapes = self._map[name]

        if len(annotated_shapes) != 1:
            raise ValueError("Can only annotate based on label when exactly one shape is labelled")

        self._map[name] = { next(s for s in annotated_shapes).with_updated_attribute(key, value)}

    def annotate_subshapes(self, name: str, key: str, value: str):
        if name not in self._map:
            raise ValueError(f"No label with name: {name}")

        annotated_shapes = self._map[name]

        self._map[name] = {s.with_updated_attribute(key, value) for s in annotated_shapes}

    def map_subshape_changes(
            self,
            new_shape: AnnotatedShape,
            mks: T_MKS,
            map_is_partner: bool = False,
            map_is_same: bool = False) -> SubshapeMap:

        if not isinstance(new_shape, AnnotatedShape):
            raise ValueError("Expected annotated shape")

        """
        Tries to track the history of the subshape map according to the changes applied by mks.
        """
        get_is_deleted = SubshapeMap._get_is_deleted_method(mks)

        all_old_shapes: typing.Set[SetPlaceableShape] = {
            SetPlaceableShape(s) for s in InterrogateUtils.traverse_all_subshapes(self._root_shape.set_placeable_shape.shape)}\
            .union({self._root_shape.set_placeable_shape})
        all_new_shapes: typing.Set[SetPlaceableShape] = {SetPlaceableShape(s) for s in
                          InterrogateUtils.traverse_all_subshapes(new_shape.set_placeable_shape.shape)}\
            .union({new_shape.set_placeable_shape})

        shape_conversions: typing.Dict[AnnotatedShape, typing.Set[AnnotatedShape]] = dict()

        for name, shapes in self._map.items():

            for shape in shapes:
                shape_conversions[shape] = SubshapeMap._get_single_shape_mapping(
                    self._root_shape,
                    new_shape,
                    shape,
                    mks,
                    all_old_shapes,
                    all_new_shapes,
                    get_is_deleted,
                    map_is_same,
                    map_is_partner)

        # now build the new subshape map:
        result = SubshapeMap(new_shape)
        for name, shapes in self._map.items():
            for shape in shapes:
                for mapped_shape in shape_conversions[shape]:
                    result.place(name, mapped_shape)

        return result

    def clone(self):
        return SubshapeMap(self._root_shape, self._map)

    def pruned(self) -> SubshapeMap:
        result = SubshapeMap(self._root_shape)

        all_subshapes = {SetPlaceableShape(s) for s in
                         InterrogateUtils.traverse_all_subshapes(self.root_shape.set_placeable_shape.shape)}
        all_subshapes.add(self._root_shape.set_placeable_shape)

        for name, shapes in self._map.items():
            for s in shapes:
                if s.set_placeable_shape in all_subshapes:
                    result.place(name, s)

        return result

    def __getitem__(self, item):
        if not isinstance(item, str):
            raise ValueError(f"Index must be a string. Was instead: {type(item)}")

        return self._map[item].copy()

    @staticmethod
    def _get_is_deleted_method(mks: T_MKS) -> typing.Callable[[AnnotatedShape], bool]:
        if isinstance(mks, OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeShape):
            return lambda s: mks.IsDeleted(s.set_placeable_shape.shape)
        elif isinstance(mks, OCC.Core.BRepOffset.BRepOffset_MakeOffset):
            return lambda s: mks.IsDeleted(s.set_placeable_shape.shape)
        elif isinstance(mks, OCC.Core.BRepTools.BRepTools_History):
            return lambda s: mks.IsRemoved(s.set_placeable_shape.shape)
        else:
            raise ValueError("Unsupported MakeShape type")

    @staticmethod
    def _get_single_shape_mapping(
            top_level_source_shape: AnnotatedShape,
            top_level_new_shape: AnnotatedShape,
            source_shape: AnnotatedShape,
            mks: T_MKS,
            all_old_subshapes: typing.Set[SetPlaceableShape],
            all_new_subshapes: typing.Set[SetPlaceableShape],
            get_is_deleted: typing.Callable[[AnnotatedShape], bool],
            map_is_same: bool,
            map_is_partner: bool) -> typing.Set[AnnotatedShape]:

        if get_is_deleted(source_shape):
            return set()

        if source_shape.set_placeable_shape not in all_old_subshapes:
            # the source shape cannot be mapped because the operation is only performed on the top level source shape,
            # orphan shapes are dropped
            return set()

        result: typing.Set[AnnotatedShape] = set()

        if map_is_same or map_is_partner:
            for s in all_new_subshapes:
                if map_is_same and s.shape.IsSame(source_shape.set_placeable_shape.shape):
                    result.add(source_shape.with_updated_shape(s.shape))

                if map_is_partner and s.shape.IsPartner(source_shape.set_placeable_shape.shape):
                    result.add(source_shape.with_updated_shape(s.shape))

        for s in ListUtils.iterate_list(mks.Modified(source_shape.set_placeable_shape.shape)):
            result.add(source_shape.with_updated_shape(s))

        for s in ListUtils.iterate_list(mks.Generated(source_shape.set_placeable_shape.shape)):
            result.add(source_shape.with_updated_shape(s))

        # the top level source and new shapes are always linked
        if source_shape == top_level_source_shape:
            result.add(top_level_new_shape)

        if source_shape.set_placeable_shape in all_new_subshapes:
            result.add(source_shape)

        return result

    @staticmethod
    def copy_map(map: typing.Dict[str, typing.Set[AnnotatedShape]]) -> typing.Dict[str, typing.Set[AnnotatedShape]]:
        result = dict()
        for k, v in map.items():
            result[k] = set()
            for vv in v:
                result[k].add(vv.clone())

        return result
