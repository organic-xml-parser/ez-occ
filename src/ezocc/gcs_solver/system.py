import time
import typing

import numpy as np
import scipy
from OCC.Core import Precision

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.entity import Entity
from ezocc.gcs_solver.graph.constraint_graph import ConstraintGraph, Node, Edge
from ezocc.gcs_solver.parameter import Parameter
from ezocc.part_manager import NoOpPartCache, PartFactory, PartCache


class System:

    def __init__(self):
        self.parameters: typing.List[Parameter] = []
        self.constraints: typing.List[Constraint] = []
        self.entities: typing.List[Entity] = []
        self.entity_labels: typing.Dict[Entity, str] = {}

    def add_parameter(self, initial_value: float, fixed: bool = False) -> Parameter:
        result = Parameter(initial_value, fixed=fixed)
        self.parameters.append(result)

        return result

    def add_constraint(self, constraint: Constraint):
        self.constraints.append(constraint)

    def add_entity(self, entity: Entity):
        self.entities.append(entity)
        for c in entity.get_implicit_constraints():
            self.add_constraint(c)

    def label_entity(self, entity: Entity, label: str):
        self.entity_labels[entity] = label

    def get_preview_parts(self, cache: PartCache = None):
        if cache is None:
            cache = NoOpPartCache.instance()

        result = []

        for e in self.entities:
            part = e.get_part(cache)
            if e in self.entity_labels:
                part = part.name(self.entity_labels[e])
            result.append(part)

        return PartFactory(cache).compound(*result)

    def solve(self):
        # Analyze the constraint graph to determine overconstrained/unconstrained sections
        constraint_graph = ConstraintGraph()
        for p in self.parameters:
            # fixed parameters do not contribute any degrees of freedom
            constraint_graph.add_node(p, Node(0 if p.fixed else 1))

        for c in self.constraints:
            constraint_graph.add_hyperedge(c, Edge(c.dof_restricted()), c.params)

        for e in self.entities:
            print("DOF analysis for entity:", e)
            constraint_graph.check_fully_constrained(set(e.params))

        state_vector_length = 0
        for p in self.parameters:
            # clear the parameter index
            p.index = None

            if not p.fixed:
                p.index = state_vector_length
                state_vector_length += 1

        print("System of equations with parameters:")
        print([str(p) for p in self.parameters])

        print()
        print("Entities:")
        for e in self.entities:
            print(e)

        def _lsq_fn(input_array) -> typing.List[float]:
            for p in self.parameters:
                if not p.fixed:
                    p.read_from_array(input_array)

            constraints_output = [0.0] * len(self.constraints)

            for i, c in enumerate(self.constraints):
                constraints_output[i] = c.get_error()

            return constraints_output

        x0 = np.array([0] * state_vector_length)
        for p in self.parameters:
            if not p.fixed:
                p.write_to_array(x0)

        tol = Precision.precision.Confusion() * 0.1
        start = time.time()
        result = scipy.optimize.least_squares(_lsq_fn, x0, verbose=2, gtol=tol, ftol=tol, xtol=tol)
        end = time.time()

        for p in self.parameters:
            if not p.fixed:
                p.read_from_array(result.x)

        #print(result)
        print(f"Solver time: {end - start}")

        for e in self.entities:
            print(e)

        #print("CONSTRAINT SUMMARY")
        #for c in self.constraints:
        #    print(c)
        #    print(c.get_error())

