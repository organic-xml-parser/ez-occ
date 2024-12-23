from __future__ import annotations

import pdb
import typing

from OCC.Core.gp import gp_Pnt

from ezocc.data_structures.point_like import P3DLike
from ezocc.gcs_solver.constraints.angle_constraint import AngleConstraint
from ezocc.gcs_solver.constraints.distance_constraint import DistanceConstraint
from ezocc.gcs_solver.constraints.equality_constraint import EqualityConstraint
from ezocc.gcs_solver.constraints.gt_than_constraint import GtThanConstraint
from ezocc.gcs_solver.constraints.incidence_constraint import IncidenceConstraint
from ezocc.gcs_solver.constraints.length_constraint import LengthConstraint
from ezocc.gcs_solver.constraints.tangency_constraint import TangencyConstraint
from ezocc.gcs_solver.constraints.vdistance_constraint import VDistanceConstraint
from ezocc.gcs_solver.entities.bounded_curve_entity import BoundedCurveEntity
from ezocc.gcs_solver.entities.circle_arc_entity import CircleArcEntity
from ezocc.gcs_solver.entities.circle_entity import CircleEntity
from ezocc.gcs_solver.entities.curve_entity import CurveEntity
from ezocc.gcs_solver.entities.entity import Entity
from ezocc.gcs_solver.entities.line_segment_entity import LineSegmentEntity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartCache, Part, NoOpPartCache


class Var:

    def __init__(self, intial_value: float):
        self.inital_value = intial_value


InputParam = typing.Union[float, Var, typing.Callable[[], Parameter]]


def _create_system_param(param: InputParam, system: System) -> Parameter:
    if isinstance(param, float) or isinstance(param, int):
        return system.add_parameter(param, fixed=True)
    elif isinstance(param, Var):
        return system.add_parameter(param.inital_value, fixed=False)
    else:
        return param()


EntityFieldAccessor = typing.Callable[[Entity], typing.Union[Entity, Parameter]]
EntityResolverParam = typing.Union[str, typing.Tuple[str, EntityFieldAccessor], Entity]


def _resolve(p: EntityResolverParam, system: SystemBuilder) -> Entity:
    if isinstance(p, str):
        return system.resolve_entity(p, lambda e: e)
    elif isinstance(p, Entity):
        return p
    else:
        return system.resolve_entity(p[0], p[1])


def _assert_resolved_to(entity, expected_type):
    if not isinstance(entity, expected_type):
        raise ValueError(f"Expected resolved entity to be of type {expected_type}. Instead was: {entity}")


class EntityBuilder:

    def __init__(self, system: SystemBuilder):
        self._system = system
        self.name: typing.Optional[str] = None
        self.on_done: typing.List[typing.Callable[[Entity], None]] = []

    def done(self) -> SystemBuilder:
        entity = self._create_entity()
        self._system.register_entity(self.name, entity)

        for c in self.on_done:
            c(entity)

        return self._system

    def __getattr__(self, item):
        entity = self._create_entity()

        if item.startswith("with_"):
            self.done()
            return getattr(self.system, item)

    def named(self, name: str) -> EntityBuilder:
        self.name = name
        return self

    def _create_entity(self) -> Entity:
        raise NotImplementedError()


class BoundedCurveEntityBuilder(EntityBuilder):

    def __init__(self, system: SystemBuilder):
        super().__init__(system)

    def from_existing_point(self, p: EntityResolverParam) -> BoundedCurveEntityBuilder:
        raise NotImplementedError()

    def to_existing_point(self, p: EntityResolverParam) -> BoundedCurveEntityBuilder:
        raise NotImplementedError()

    def from_point(self, x0: InputParam, y0: InputParam) -> BoundedCurveEntityBuilder:
        raise NotImplementedError()

    def to_point(self, x1: InputParam, y1: InputParam) -> BoundedCurveEntityBuilder:
        raise NotImplementedError()


class CircleBuilder(EntityBuilder):

    def __init__(self, system: SystemBuilder):
        super().__init__(system)
        self.center_x: typing.Optional[InputParam] = None
        self.center_y: typing.Optional[InputParam] = None
        self.rad: typing.Optional[InputParam] = None

    def centered(self, x: InputParam, y: InputParam) -> CircleBuilder:
        self.center_x = x
        self.center_y = y

        return self

    def radius(self, rad: InputParam) -> CircleBuilder:
        self.rad = rad

        return self

    def _create_entity(self) -> Entity:
        return CircleEntity(
            PointEntity(
                _create_system_param(self.center_x, self._system.system),
                _create_system_param(self.center_y, self._system.system)
            ),
            _create_system_param(self.rad, self._system.system)
        )


class CircleArcBuilder(BoundedCurveEntityBuilder):

    def __init__(self, system: SystemBuilder):
        super().__init__(system)

        self._center: typing.Optional[PointEntity] = None
        self._p0: typing.Optional[PointEntity] = None
        self._p1: typing.Optional[PointEntity] = None

    def center(self, x: InputParam, y: InputParam) -> CircleArcBuilder:
        _center_x = _create_system_param(x, self._system.system)
        _center_y = _create_system_param(y, self._system.system)

        self._center = PointEntity(_center_x, _center_y)

        return self

    def center_point(self, p: EntityResolverParam) -> CircleArcBuilder:
        self._center = _resolve(p, self._system)
        _assert_resolved_to(self._center, PointEntity)
        return self

    def from_point(self, x: InputParam, y: InputParam) -> CircleArcBuilder:
        p0_x = _create_system_param(x, self._system.system)
        p0_y = _create_system_param(y, self._system.system)

        self._p0 = PointEntity(p0_x, p0_y)

        return self

    def from_existing_point(self, p: EntityResolverParam) -> CircleArcBuilder:
        self._p0 = _resolve(p, self._system)
        _assert_resolved_to(self._p0, PointEntity)
        return self

    def to_point(self, x: InputParam, y: InputParam) -> CircleArcBuilder:
        p1_x = _create_system_param(x, self._system.system)
        p1_y = _create_system_param(y, self._system.system)

        self._p1 = PointEntity(p1_x, p1_y)

        return self

    def to_existing_point(self, p: EntityResolverParam) -> CircleArcBuilder:
        self._p1 = _resolve(p, self._system)
        _assert_resolved_to(self._p1, PointEntity)
        return self

    def _create_entity(self) -> Entity:
        if self._center is None:
            raise ValueError("Center has not been set")

        if self._p0 is None:
            raise ValueError("P0 has not been set")

        if self._p1 is None:
            raise ValueError("P1 has not been set")

        return CircleArcEntity(self._center, self._p0, self._p1)


class PointBuilder(EntityBuilder):

    def __init__(self, system: SystemBuilder):
        super().__init__(system)
        self.x: typing.Optional[InputParam] = None
        self.y: typing.Optional[InputParam] = None

    def at(self, x: InputParam, y: InputParam) -> PointBuilder:
        self.x = x
        self.y = y

        return self

    def _create_entity(self) -> Entity:
        result = PointEntity(
            _create_system_param(self.x, self._system.system),
            _create_system_param(self.y, self._system.system)
        )

        return result


class LineSegmentBuilder(BoundedCurveEntityBuilder):

    def __init__(self, system: SystemBuilder):
        super().__init__(system)

        self.x0: typing.Optional[InputParam] = None
        self.y0: typing.Optional[InputParam] = None

        self.x1: typing.Optional[InputParam] = None
        self.y1: typing.Optional[InputParam] = None

    def _create_entity(self) -> Entity:
        if self.x0 is None:
            raise ValueError("X0 Not specified")
        if self.x1 is None:
            raise ValueError("X1 Not specified")

        if self.y0 is None:
            raise ValueError("Y0 Not specified")
        if self.y1 is None:
            raise ValueError("Y1 Not specified")

        return LineSegmentEntity(
            PointEntity(
                _create_system_param(self.x0, self._system.system),
                _create_system_param(self.y0, self._system.system)),
            PointEntity(
                _create_system_param(self.x1, self._system.system),
                _create_system_param(self.y1, self._system.system)))

    def from_existing_point(self, p: EntityResolverParam) -> LineSegmentBuilder:
        def _resolve_x0():
            _val = _resolve(p, self._system)
            _assert_resolved_to(_val, PointEntity)
            return _val.x

        def _resolve_y0():
            _val = _resolve(p, self._system)
            _assert_resolved_to(_val, PointEntity)
            return _val.y

        self.x0 = _resolve_x0
        self.y0 = _resolve_y0

        return self

    def to_existing_point(self, p: EntityResolverParam) -> LineSegmentBuilder:
        def _resolve_x1():
            _val = _resolve(p, self._system)
            _assert_resolved_to(_val, PointEntity)
            return _val.x

        def _resolve_y1():
            _val = _resolve(p, self._system)
            _assert_resolved_to(_val, PointEntity)
            return _val.y

        self.x1 = _resolve_x1
        self.y1 = _resolve_y1

        return self

    def from_point(self, x0: InputParam, y0: InputParam) -> LineSegmentBuilder:
        self.x0 = x0
        self.y0 = y0
        return self

    def to_point(self, x1: InputParam, y1: InputParam) -> LineSegmentBuilder:
        self.x1 = x1
        self.y1 = y1
        return self


class ConstraintBuilder:

    def __init__(self, system_builder: SystemBuilder):
        self._system_builder = system_builder

    @property
    def where(self) -> ConstraintBuilder:
        return self._system_builder.where

    @property
    def system(self) -> SystemBuilder:
        return self._system_builder

    def horizontal(self, p: EntityResolverParam) -> ConstraintBuilder:
        p = _resolve(p, self._system_builder)
        _assert_resolved_to(p, LineSegmentEntity)

        constraint = EqualityConstraint(p.get_p0().y, p.get_p1().y)
        self._system_builder.system.add_constraint(constraint)
        return self

    def vertical(self, p: EntityResolverParam) -> ConstraintBuilder:
        p = _resolve(p, self._system_builder)
        _assert_resolved_to(p, LineSegmentEntity)

        constraint = EqualityConstraint(p.get_p0().x, p.get_p1().x)
        self._system_builder.system.add_constraint(constraint)
        return self

    def incident(self, p: EntityResolverParam, c: EntityResolverParam) -> ConstraintBuilder:
        p = _resolve(p, self._system_builder)
        c = _resolve(c, self._system_builder)

        _assert_resolved_to(p, PointEntity)
        _assert_resolved_to(c, CurveEntity)

        constraint = IncidenceConstraint(p, c)

        self._system_builder.system.add_constraint(constraint)

        return self

    def point_point_dist(self, p0: EntityResolverParam, p1: EntityResolverParam, dist: InputParam) -> ConstraintBuilder:
        p0 = _resolve(p0, self._system_builder)
        p1 = _resolve(p1, self._system_builder)

        dist = _create_system_param(dist, self.system.system)

        _assert_resolved_to(p0, PointEntity)
        _assert_resolved_to(p1, PointEntity)

        DistanceConstraint.create(self._system_builder.system, p0, p1, dist)

        return self

    def length(self, c: EntityResolverParam, length: InputParam):
        c = _resolve(c, self._system_builder)
        _assert_resolved_to(c, BoundedCurveEntity)

        length = _create_system_param(length, self._system_builder.system)

        constraint = LengthConstraint(length, c)

        self._system_builder.system.add_constraint(constraint)

        return self


    def tangency(self, p: EntityResolverParam, c0: EntityResolverParam, c1: EntityResolverParam) -> ConstraintBuilder:
        p = _resolve(p, self._system_builder)
        c0 = _resolve(c0, self._system_builder)
        c1 = _resolve(c1, self._system_builder)

        _assert_resolved_to(p, PointEntity)
        _assert_resolved_to(c0, CurveEntity)
        _assert_resolved_to(c1, CurveEntity)

        constraint = TangencyConstraint(p, c0, c1)

        self._system_builder.system.add_constraint(constraint)

        return self

    def angle(self, p_origin: EntityResolverParam, p0: EntityResolverParam, p1: EntityResolverParam, angle: InputParam) -> ConstraintBuilder:
        p_origin = _resolve(p_origin, self._system_builder)
        _assert_resolved_to(p_origin, PointEntity)

        p0 = _resolve(p0, self._system_builder)
        _assert_resolved_to(p0, PointEntity)

        p1 = _resolve(p1, self._system_builder)
        _assert_resolved_to(p1, PointEntity)

        angle = _create_system_param(angle, self._system_builder.system)

        constraint = AngleConstraint(p_origin, p0, p1, angle)

        self._system_builder.system.add_constraint(constraint)

        return self

    def distance(self, p0: EntityResolverParam, p1: EntityResolverParam, dist: InputParam) -> ConstraintBuilder:
        p0 = _resolve(p0, self._system_builder)
        _assert_resolved_to(p0, PointEntity)

        p1 = _resolve(p1, self._system_builder)
        _assert_resolved_to(p1, PointEntity)

        dist = _create_system_param(dist, self._system_builder.system)

        constraint = DistanceConstraint(dist, p0.x, p0.y, p1.x, p1.y)

        self._system_builder.system.add_constraint(constraint)

        return self


    def vdistance(self, p0: EntityResolverParam, p1: EntityResolverParam, dist: InputParam) -> ConstraintBuilder:
        p0 = _resolve(p0, self._system_builder)
        _assert_resolved_to(p0, PointEntity)

        p1 = _resolve(p1, self._system_builder)
        _assert_resolved_to(p1, PointEntity)

        dist = _create_system_param(dist, self._system_builder.system)

        constraint = VDistanceConstraint(dist, p0.y, p1.y)

        self._system_builder.system.add_constraint(constraint)

        return self

    def hdistance(self, p0: EntityResolverParam, p1: EntityResolverParam, dist: InputParam) -> ConstraintBuilder:
        p0 = _resolve(p0, self._system_builder)
        _assert_resolved_to(p0, PointEntity)

        p1 = _resolve(p1, self._system_builder)
        _assert_resolved_to(p1, PointEntity)

        dist = _create_system_param(dist, self._system_builder.system)

        constraint = VDistanceConstraint(dist, p0.x, p1.x)

        self._system_builder.system.add_constraint(constraint)

        return self

    def radius(self, p: EntityResolverParam, value: InputParam) -> ConstraintBuilder:
        p = _resolve(p, self._system_builder)
        value = _create_system_param(value, self._system_builder.system)

        if isinstance(p, CircleEntity):
            self._system_builder.system.add_constraint(EqualityConstraint(p.radius, value))
        elif isinstance(p, CircleArcEntity):
            self._system_builder.system.add_constraint(DistanceConstraint(
                value,
                p.p0.x, p.p0.y,
                p.center.x, p.center.y
            ))
        else:
            raise ValueError(f"Invalid radius entity: {p}")

        return self

    def greater_than(self,
                     v0: EntityResolverParam,
                     v1: EntityResolverParam) -> ConstraintBuilder:

        v0 = _resolve(v0, self._system_builder)
        _assert_resolved_to(v0, Parameter)

        v1 = _resolve(v1, self._system_builder)
        _assert_resolved_to(v1, Parameter)

        constraint = GtThanConstraint(v0, v1)
        self._system_builder.system.add_constraint(constraint)
        return self

    def greater_than_value(self,
                     v0: EntityResolverParam,
                     v1: InputParam) -> ConstraintBuilder:

        v0 = _resolve(v0, self._system_builder)
        _assert_resolved_to(v0, Parameter)

        v1 = _create_system_param(v1, self._system_builder.system)

        constraint = GtThanConstraint(v0, v1)
        self._system_builder.system.add_constraint(constraint)
        return self

    def less_than_value(self,
                     v0: EntityResolverParam,
                     v1: InputParam) -> ConstraintBuilder:

        v0 = _resolve(v0, self._system_builder)
        _assert_resolved_to(v0, Parameter)

        v1 = _create_system_param(v1, self._system_builder.system)

        constraint = GtThanConstraint(v1, v0)
        self._system_builder.system.add_constraint(constraint)
        return self


class SystemBuilder:

    def __init__(self):
        self.system = System()
        self.named_entities: typing.Dict[str, Entity] = {}
        self._registered_entities: typing.List[Entity] = []
        self._apply_tangency_on_next_builder = False

    def solve(self) -> SystemBuilder:
        self.system.solve()
        return self

    def get_parts(self, part_cache: PartCache) -> Part:
        return self.system.get_preview_parts(part_cache)

    def tangent_to(self) -> SystemBuilder:
        self._apply_tangency_on_next_builder = True
        return self

    def register_entity(self, id: typing.Optional[str], entity: Entity):
        if id is not None:
            if id in self.named_entities:
                raise ValueError(f'Name "{id}" has already been associated with an entity')

            self.named_entities[id] = entity

        self.system.add_entity(entity)
        self._registered_entities.append(entity)

        if id is not None:
            self.system.label_entity(entity, id)

        if self._apply_tangency_on_next_builder:
            latest_entity = self._registered_entities[-1]
            penultimate_entity = self._registered_entities[-2]

            if not isinstance(latest_entity, BoundedCurveEntity):
                raise ValueError("Last added entity was not a bounded curve. Tangency cannot be applied.")

            if not isinstance(penultimate_entity, BoundedCurveEntity):
                raise ValueError("Previous added entity was not a bounded curve. Tangency cannot be applied.")

            constraint = TangencyConstraint(penultimate_entity.get_p1(), latest_entity, penultimate_entity)

            self.system.add_constraint(constraint)
            self._apply_tangency_on_next_builder = False

    def resolve_entity(self,
                       name: str,
                       field_accessor: EntityFieldAccessor):
        return field_accessor(self.named_entities[name])

    def with_circle(self) -> CircleBuilder:
        return CircleBuilder(self)

    def with_circle_arc(self) -> CircleArcBuilder:
        return self._wrap_with_tangency(CircleArcBuilder(self))

    def with_point(self) -> PointBuilder:
        return PointBuilder(self)

    def with_fillet_between(self, c_from: EntityResolverParam, c_to: EntityResolverParam, apply_constraints: bool=True) -> CircleArcBuilder:
        c_from: BoundedCurveEntity = _resolve(c_from, self)
        c_to: BoundedCurveEntity = _resolve(c_to, self)

        _assert_resolved_to(c_from, BoundedCurveEntity)
        _assert_resolved_to(c_to, BoundedCurveEntity)

        center_point = c_from.get_p1().x.value, c_from.get_p1().y.value
        center_point_3d = P3DLike(gp_Pnt(*center_point, 0))

        t0 = c_from.tangent_at_point(center_point_3d)
        t1 = c_to.tangent_at_point(center_point_3d)

        c_from.p1 = PointEntity(
            _create_system_param(Var(center_point[0] - t0.x * c_from.length() * 0.1), self.system),
            _create_system_param(Var(center_point[1] - t0.y * c_from.length() * 0.1), self.system))
        self.system.add_entity(c_from.p1)

        c_to.p0 = PointEntity(_create_system_param(Var(center_point[0] + t1.x * c_to.length() * 0.1), self.system),
                              _create_system_param(Var(center_point[1] + t1.y * c_to.length() * 0.1), self.system))
        self.system.add_entity(c_to.p0)

        center_x = center_point[0] - t0.x * c_from.length() * 0.1 + t1.x * c_to.length() * 0.1
        center_y = center_point[1] - t0.y * c_from.length() * 0.1 + t1.y * c_to.length() * 0.1

        result = (self.with_circle_arc()
         .from_existing_point(c_from.p1).to_existing_point(c_to.p0)
         .center(Var(center_x), Var(center_y)))

        def on_done(entity):
            self.where.tangency(c_from.get_p1(), c_from, entity)
            self.where.tangency(c_to.get_p0(), entity, c_to)

            #pdb.set_trace()

            #c_from.get_part(NoOpPartCache.instance()).preview(entity.get_part(NoOpPartCache.instance()),
            #                                                  c_to.get_part(NoOpPartCache.instance()))

        if apply_constraints:
            result.on_done.append(on_done)

        return result


    def with_line_segment(self) -> LineSegmentBuilder:
        return self._wrap_with_tangency(LineSegmentBuilder(self))

    @property
    def where(self) -> ConstraintBuilder:
        return ConstraintBuilder(self)

    def _wrap_with_tangency(self, builder: BoundedCurveEntityBuilder):
        if self._apply_tangency_on_next_builder:
            builder.from_existing_point(self._registered_entities[-1].get_p1())

        return builder


if __name__ == '__main__':

    system = (SystemBuilder()
        .with_circle_arc()
            .center(0, 0)
            .p0(Var(-5), Var(5))
            .p1(0, Var(5))
            .named("circle")
            .done()
        .with_line_segment()
            .from_point(-15, -5)
            .to_point(0, -5)
            .named("base")
            .done()
        .with_line_segment()
            .from_existing_point(("circle", lambda c: c.p0))
            .to_existing_point(("base", lambda p: p.p0))
            .named("lin")
            .done()
        .with_line_segment()
            .from_existing_point(("base", lambda p: p.p1))
            .to_existing_point(("circle", lambda p: p.p1))
            .done()
        .where.tangency(("lin", lambda p: p.p0), "lin", "circle")
        .where.radius("circle", 5)
        .system.system
     )

    system.solve()

    system.get_preview_parts().preview()