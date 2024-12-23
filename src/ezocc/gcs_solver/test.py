import math

from ezocc.gcs_solver.constraints.angle_constraint import AngleConstraint
from ezocc.gcs_solver.constraints.distance_constraint import DistanceConstraint
from ezocc.gcs_solver.constraints.equality_constraint import EqualityConstraint
from ezocc.gcs_solver.constraints.incidence_constraint import IncidenceConstraint
from ezocc.gcs_solver.constraints.length_constraint import LengthConstraint
from ezocc.gcs_solver.constraints.tangency_constraint import TangencyConstraint
from ezocc.gcs_solver.entities.circle_arc_entity import CircleArcEntity
from ezocc.gcs_solver.entities.circle_entity import CircleEntity
from ezocc.gcs_solver.entities.line_segment_entity import LineSegmentEntity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.system import System
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import NoOpPartCache, PartFactory


def main():
    system = System()

    p0 = PointEntity.create(system, 0, 0)
    p1 = PointEntity.create(system, 1, 1)
    p2 = PointEntity.create(system, 2, 1)

    #DistanceConstraint.create(system, p0, p1, 1)
    #DistanceConstraint.create(system, p0, p2, 1)

    arc0 = CircleArcEntity.create(system, p0, p1, p2)

    system.add_constraint(EqualityConstraint(arc0.p0.x, system.add_parameter(0, fixed=True)))

    arc1 = CircleArcEntity.create(system,
                                  PointEntity.create(system, 1, 1),
                                  PointEntity.create(system, 0, 2),
                                  PointEntity.create(system, 2, 2))

    lin = LineSegmentEntity.create(system, arc0.get_p1(), arc1.get_p0())

    AngleConstraint.create(system, p0, p1, p2, math.radians(45))
    system.add_constraint(TangencyConstraint(lin.get_p0(), arc0, lin))
    system.add_constraint(TangencyConstraint(lin.get_p1(), arc1, lin))
    system.add_constraint(EqualityConstraint(
        arc0.center.x,
        arc1.center.x
    ))
    system.add_constraint(EqualityConstraint(
        lin.get_p0().x,
        lin.get_p1().x
    ))

    #system.add_constraint(IncidenceConstraint(
    #    arc1.get_p0(),
    #    arc0
    #))

    system.add_constraint(LengthConstraint(
        system.add_parameter(5, fixed=True),
        lin))

    #circle = CircleEntity.create(system, p0, 3)
    #circle.radius.fixed = True

    #IncidenceConstraint.create(system, p2, circle)
    #IncidenceConstraint.create(system, p1, circle)
    #DistanceConstraint.create(system, p1, p2, 2)

    #system.preview()
    previews = []

    system.solve()
    sys0 = system.preview()

    previews.append(sys0)


    PartFactory(NoOpPartCache.instance()).arrange(*previews).preview()


if __name__ == '__main__':
    main()
