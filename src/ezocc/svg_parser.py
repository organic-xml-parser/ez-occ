from __future__ import annotations

import functools
import itertools
import json
import math
import re
import sys
import typing
import xml.etree.ElementTree as ElTree

import OCC
import OCC.Core.BRep
import OCC.Core.BRepAdaptor
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBndLib
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepFeat
import OCC.Core.BRepFilletAPI
import OCC.Core.BRepGProp
import OCC.Core.BRepLib
import OCC.Core.BRepMesh
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.BRepTools
import OCC.Core.BRepTools
import OCC.Core.Bnd
import OCC.Core.GC
import OCC.Core.GCE2d
import OCC.Core.GProp
import OCC.Core.Geom
import OCC.Core.GeomAPI
import OCC.Core.STEPControl
import OCC.Core.ShapeAnalysis
import OCC.Core.ShapeFix
import OCC.Core.ShapeUpgrade
import OCC.Core.StdFail
import OCC.Core.StlAPI
import OCC.Core.TColgp
import OCC.Core.TopAbs
import OCC.Core.TopExp
import OCC.Core.TopTools
import OCC.Core.TopoDS
import OCC.Core.gp
import OCC.Core.gp
from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Elips, gp_Circ, gp_OZ, gp_XOY

import ezocc.occutils_python as op
from ezocc.part_manager import Part


class SVGPathCommand:

    def __init__(self, command: str, args: typing.List[float]):
        self.command = command
        self.args = args

    def apply(self, sketchers: typing.List[op.WireSketcher], command_history: typing.List[SVGPathCommand]):
        raise NotImplementedError()

    def __str__(self) -> str:
        return json.dumps({"command": self.command, "args": self.args})


class SVGPathMoveCommand(SVGPathCommand):

    @staticmethod
    def get_args_to_take(input_args):
        return len(input_args) - len(input_args) % 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def apply(self, sketchers: typing.List[op.WireSketcher], command_history: typing.List[SVGPathCommand]):
        if self.command.upper() != "M":
            raise RuntimeError("Invalid command")

        next_pnt = OCC.Core.gp.gp_Pnt(self.args[0], self.args[1], 0)

        if self.command.islower():
            last_point = sketchers[-1].last_vertex_pnt if len(sketchers) > 0 else OCC.Core.gp.gp.Origin()
            next_pnt = OCC.Core.gp.gp_Pnt(last_point.X() + next_pnt.X(),
                                          last_point.Y() + next_pnt.Y(),
                                          last_point.Z() + next_pnt.Z())

        sketcher = op.WireSketcher(next_pnt)
        for i in range(2, len(self.args), 2):
            next_x = self.args[i]
            next_y = self.args[i + 1]

            sketcher.line_to(next_x, next_y, 0, is_relative=self.command.islower())

        sketchers.append(sketcher)




class SVGPathLineCommand(SVGPathCommand):

    @staticmethod
    def get_args_to_take(input_args):
        return 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def apply(self, sketchers: typing.List[op.WireSketcher], command_history: typing.List[SVGPathCommand]):
        if self.command.upper() != "L":
            raise ValueError("Invalid command string")

        sketchers[-1].line_to(self.args[0], self.args[1], 0, is_relative=self.command.islower())


class SVGPathArcCommand(SVGPathCommand):

    @staticmethod
    def get_args_to_take(input_args):
        return 7

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def apply(self, sketchers: typing.List[op.WireSketcher], command_history: typing.List[SVGPathCommand]):
        rx = self.args[0]
        ry = self.args[1]
        rot = self.args[2]
        fa = self.args[3]
        fs = self.args[4]

        curve_end_x = self.args[5]
        curve_end_y = self.args[6]

        is_relative = (self.command == "a")

        plane = OCC.Core.GC.GC_MakePlane(OCC.Core.gp.gp.Origin(), OCC.Core.gp.gp.DZ()).Value()

        sketchers[-1].svg_arc(plane, rx, ry, rot, fa, fs, curve_end_x, curve_end_y, is_relative=is_relative)


class SVGPathCubicCurveCommand(SVGPathCommand):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def previous_X2_Y2_X_Y(self) -> typing.Tuple[float, float, float, float]:
        raise NotImplementedError()


class SVGPathCCubicCurveCommand(SVGPathCubicCurveCommand):

    @staticmethod
    def get_args_to_take(input_args):
        return 6

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._previous_X2_Y2_X_Y = None

    def apply(self, sketchers: typing.List[op.WireSketcher], command_history: typing.List[SVGPathCommand]):
        plane = OCC.Core.GC.GC_MakePlane(OCC.Core.gp.gp.Origin(), OCC.Core.gp.gp.DZ()).Value()

        is_relative = self.command.islower()

        if len(self.args) < 6:
            raise ValueError(f"Cubic curve command has insufficient args: {self.args}")

        self._previous_X2_Y2_X_Y = [self.args[2], self.args[3], self.args[4], self.args[5]]
        if is_relative:
            last_pnt = sketchers[-1].last_vertex_pnt

            self._previous_X2_Y2_X_Y[0] += last_pnt.X()
            self._previous_X2_Y2_X_Y[1] += last_pnt.Y()
            self._previous_X2_Y2_X_Y[2] += last_pnt.X()
            self._previous_X2_Y2_X_Y[3] += last_pnt.Y()

        sketchers[-1].cubic_bezier(plane,
                                   self.args[0],
                                   self.args[1],
                                   self.args[2],
                                   self.args[3],
                                   self.args[4],
                                   self.args[5],
                                   is_relative=is_relative)

    # returns the absolute values of the previous args, regardless of whether command was relative
    @property
    def previous_X2_Y2_X_Y(self) -> typing.Tuple[float, float, float, float]:
        if self._previous_X2_Y2_X_Y is None:
            raise RuntimeError("Values not computed yet")

        return tuple(self._previous_X2_Y2_X_Y)


class SVGPathSCubicCurveCommand(SVGPathCubicCurveCommand):

    @staticmethod
    def get_args_to_take(input_args):
        return 4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._previous_X2_Y2_X_Y = None

    def apply(self, sketchers: typing.List[op.WireSketcher], command_history: typing.List[SVGPathCommand]):
        x2 = self.args[0]
        y2 = self.args[1]
        x = self.args[2]
        y = self.args[3]

        last_pnt = sketchers[-1].last_vertex_pnt

        is_relative = self.command.islower()
        if is_relative:
            x2 += last_pnt.X()
            y2 += last_pnt.Y()
            x += last_pnt.X()
            y += last_pnt.Y()

        x1, y1 = self._calculate_cmd_points(last_pnt.X(), last_pnt.Y(), x2, y2, command_history)

        self._previous_X2_Y2_X_Y = [x2, y2, x, y]

        plane = OCC.Core.GC.GC_MakePlane(OCC.Core.gp.gp.Origin(), OCC.Core.gp.gp.DZ()).Value()
        sketchers[-1].cubic_bezier(plane,
                                   x1,
                                   y1,
                                   x2,
                                   y2,
                                   x,
                                   y,
                                   is_relative=False) # since all values have been calculated as abs, set relative false

    # returns ABSOLUTE x2,y2 for this bezier curve
    @staticmethod
    def _calculate_cmd_points(x_last: float,
                              y_last: float,
                              x2: float,
                              y2: float,
                              command_history: typing.List[SVGPathCommand]) -> typing.Tuple[float, float]:
        if len(command_history) == 0 or command_history[-1].command.upper() not in ['S', 'C']:
            return x2, y2

        prev_command = command_history[-1]
        if not isinstance(prev_command, SVGPathCubicCurveCommand):
            raise ValueError()

        prev_points = prev_command.previous_X2_Y2_X_Y

        x2_last, y2_last = prev_points[0], prev_points[1]

        # reflect previous x2y2 in last points (all as abs)
        return x_last + (x_last - x2_last), y_last + (y_last - y2_last)

    # returns the absolute values of the previous args, regardless of whether command was relative
    @property
    def previous_X2_Y2_X_Y(self) -> typing.Tuple[float, float, float, float]:
        if self._previous_X2_Y2_X_Y is None:
            raise RuntimeError("Values not computed yet")

        return tuple(self._previous_X2_Y2_X_Y)


class SVGPathCloseCommand(SVGPathCommand):

    @staticmethod
    def get_args_to_take(input_args):
        return 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def apply(self, sketchers: typing.List[op.WireSketcher], command_history: typing.List[SVGPathCommand]):
        sketchers[-1].close()


class SVGOrdinalLineCommand(SVGPathCommand):

    @staticmethod
    def get_args_to_take(input_args):
        return 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def apply(self, sketchers: typing.List[op.WireSketcher], command_history: typing.List[SVGPathCommand]):
        self._apply_ordinal_line(sketchers,
                                 magnitude=self.args[0],
                                 is_vertical=self.command.upper() == 'V',
                                 is_relative=self.command.islower())

    @staticmethod
    def _apply_ordinal_line(sketchers: typing.List[op.WireSketcher],
                            magnitude: float,
                            is_vertical: bool,
                            is_relative: bool):

        last_pnt = sketchers[-1].last_vertex_pnt if len(sketchers) > 0 else OCC.Core.gp.gp.Origin()

        if is_relative:
            magnitude += last_pnt.Y() if is_vertical else last_pnt.X()

        next_pnt = gp_Pnt(last_pnt.X(), magnitude, last_pnt.Z()) if is_vertical else gp_Pnt(magnitude, last_pnt.Y(), last_pnt.Z())

        sketchers[-1].line_to(next_pnt.X(), next_pnt.Y(), next_pnt.Z(), is_relative=False)


class SVGPathArgsParser:

    def __init__(self, value: str):
        self.value = value

    def parse(self) -> typing.Generator[float, None, None]:
        csv_elements = self.value.split(',')

        for ex in itertools.chain(*[SVGPathArgsParser.explode_element(e.strip()) for e in csv_elements]):
            yield float(ex)

    @staticmethod
    def explode_element(value: str) -> typing.Generator[str, None, None]:
        if value == '':
            #nothing to yield
            return

        # split on spaces first
        split_index = value.find(' ', 1)
        if split_index != -1:
            space_split = value.split(' ')
            for e in SVGPathArgsParser.explode_element(space_split[0]):
                yield e
            for s in space_split[1:]:
                for e in SVGPathArgsParser.explode_element(s):
                    yield e

            return

        # if there is a sign that is not the first character, that forms the split point
        if split_index == -1:
            split_index = max(value.find('-', 1), value.find('+', 1))

            # sign is part of an exponent
            if split_index != -1 and value[split_index - 1] == "e":
                split_index = -1

        # otherwise, split on the second occurrence of the period character
        if split_index == -1:
            first_period_index = value.find('.')
            if first_period_index != -1:
                split_index = value.find('.', first_period_index + 1)

        # if we have not found any split points, then the result is a single element
        if split_index == -1:
            yield value
        else:
            for e in SVGPathArgsParser.explode_element(value[:split_index]):
                yield e
            for e in SVGPathArgsParser.explode_element(value[split_index:]):
                yield e


class SVGRectParser:

    @staticmethod
    def parse(node: ElTree.Element):

        xPos = float(node.attrib["x"])
        yPos = float(node.attrib["y"])
        width = float(node.attrib["width"])
        height = float(node.attrib["height"])

        x0 = xPos
        x1 = xPos + width

        y0 = yPos
        y1 = yPos + height

        rx = float(node.attrib["rx"]) if "rx" in node.attrib else 0
        ry = float(node.attrib["ry"]) if "ry" in node.attrib else 0

        if rx != ry:
            raise ValueError("rx must == ry")

        plane = OCC.Core.GC.GC_MakePlane(OCC.Core.gp.gp.Origin(), OCC.Core.gp.gp.DZ()).Value()

        sketcher = op.WireSketcher(gp_Pnt(x0 + rx, y0, 0))

        sketcher.line_to(x1 - rx, y0, 0)
        if rx != 0:
            sketcher.svg_arc(plane, rx, rx, 0, 0, 1, rx, rx, True)

        sketcher.line_to(x1, y1 - rx, 0)
        if rx != 0:
            sketcher.svg_arc(plane, rx, rx, 0, 0, 1, -rx, rx, True)

        sketcher.line_to(x0 + rx, y1, 0)
        if rx != 0:
            sketcher.svg_arc(plane, rx, rx, 0, 0, 1, -rx, -rx, True)

        sketcher.line_to(x0, y0 + rx, 0)
        if rx != 0:
            sketcher.svg_arc(plane, rx, rx, 0, 0, 1, rx, -rx, True)

        sketcher.close()
        return sketcher.get_face(True)


class SVGEllipseParser:

    @staticmethod
    def parse(node: ElTree.Element):

        cx = float(node.attrib["cx"])
        cy = float(node.attrib["cy"])

        rx = float(node.attrib["rx"])
        ry = float(node.attrib["ry"])

        if ry <= rx:
            ax = OCC.Core.gp.gp_XOY().Translated(gp_Vec(cx, cy, 0))
        else:
            ax = OCC.Core.gp.gp_XOY()\
                .Rotated(gp_OZ(), math.radians(90))\
                .Translated(gp_Vec(cx, cy, 0))

            # swap major and minor axes
            tmp = rx
            rx = ry
            ry = tmp

        ellipse = gp_Elips(ax, rx, ry)

        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(ellipse).Shape()
        wire = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(edge).Shape()
        face = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(wire).Shape()

        return face


class SVGCircleParser:

    @staticmethod
    def parse(node: ElTree.Element):

        cx = float(node.attrib["cx"])
        cy = float(node.attrib["cy"])

        r = float(node.attrib["r"])

        circ = gp_Circ(gp_XOY().Translated(gp_Vec(cx, cy, 0)), r)

        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(circ).Shape()
        wire = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(edge).Shape()
        face = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(wire).Shape()

        return face


class SVGPathParser:

    @staticmethod
    def parse_wire(input_obj: typing.Union[ElTree.Element, str]) -> OCC.Core.TopoDS.TopoDS_Compound:
        if isinstance(input_obj, ElTree.Element):
            path = input_obj.attrib['d']
        else:
            path = input_obj

        path_commands = SVGPathParser.parse(path)

        sketchers: typing.List[op.WireSketcher] = []
        command_history = []
        for cmd in path_commands:
            cmd.apply(sketchers, command_history)
            command_history.append(cmd)

        return op.GeomUtils.make_compound(*[w.get_wire() for w in sketchers])

    @staticmethod
    def parse(path: str) -> typing.Generator[SVGPathCommand, None, None]:
        cmd_regex = re.compile("[MmLlHhVvCcSsQqTtAaZz]")

        start_indices = [m.start() for m in cmd_regex.finditer(path)]
        for i, start_index in enumerate(start_indices):
            # command consists of match until the next one
            end_index = start_indices[i + 1] if i < len(start_indices) - 1 else len(path)

            for cmd in SVGPathParser.parse_commands(path[start_index], path[start_index + 1:end_index]):
                yield cmd

    @staticmethod
    def parse_commands(cmd_str: str, args_str: str) -> typing.Generator[SVGPathCommand, None, None]:
        args = list(SVGPathArgsParser(args_str).parse())

        cmd_class = SVGPathParser.get_path_cmd_class(cmd_str)

        while True:
            args_to_take = cmd_class.get_args_to_take(args)

            take_args = args[:args_to_take]
            args = args[args_to_take:]

            yield cmd_class(cmd_str, take_args)

            if len(args) == 0:
                break

    @staticmethod
    def get_path_cmd_class(cmd_str: str):
        cmd_str_compare = cmd_str.upper()

        if cmd_str_compare == "M":
            return SVGPathMoveCommand
        elif cmd_str_compare == "L":
            return SVGPathLineCommand
        elif cmd_str_compare == "A":
            return SVGPathArcCommand
        elif cmd_str_compare == "C":
            return SVGPathCCubicCurveCommand
        elif cmd_str_compare == "S":
            return SVGPathSCubicCurveCommand
        elif cmd_str_compare == "Z":
            return SVGPathCloseCommand
        elif cmd_str_compare in ['H', 'V']:
            return SVGOrdinalLineCommand
        else:
            raise ValueError(f"Unknown command type: {cmd_str}")

#    static void splitVector(const int& chunkSize, std::vector<double> vec, std::function<void(const std::vector<double>&)> consumer) {
#        if (vec.size() % chunkSize != 0) {
#            throw std::runtime_error("Vector size is not a multiple of chunksize");
#        }
#
#        for (int i = 0; i < vec.size() / chunkSize; i++) {
#            std::vector<double> subvector;
#            for (int index = chunkSize * i; index < chunkSize * (i + 1); index++) {
#                subvector.push_back(vec[index]);
#            }
#
#            consumer(subvector);
#        }
#    }
#};


class SVGTransformParser:

    @staticmethod
    def parse(trsf: OCC.Core.gp.gp_GTrsf, node: ElTree.Element):
        if "transform" not in node.attrib.keys():
            # nothing to do
            return

        transform_value = node.attrib["transform"]

        reg = re.compile("(\w+\([\,\.\+\-\d\s]+\))")

        for match in reg.finditer(transform_value):
            SVGTransformParser.apply_transform(trsf, match.group())

    @staticmethod
    def apply_transform(trsf: OCC.Core.gp.gp_GTrsf, cmd: str):
        bracket_separated_elements = cmd.split('(')

        verb = bracket_separated_elements[0]
        args = bracket_separated_elements[1].replace(')', '')
        args_vals = list(SVGPathArgsParser(args).parse())

        if verb == "translate":
            t = OCC.Core.gp.gp_Trsf()
            t.SetTranslation(gp_Vec(args_vals[0], args_vals[1], 0))
            trsf.SetTrsf(t)
        elif verb == "scale":
            sx, sy = args_vals
            trsf.SetVectorialPart(OCC.Core.gp.gp_Mat(sx, 0 , 0,
                                                     0 , sy, 0,
                                                     0 , 0 , 1))
        elif verb == "matrix":
            a, b, c, d, e, f = args_vals
            trsf.SetVectorialPart(OCC.Core.gp.gp_Mat(a, c, e, b, d, f, 0, 0, 1))


class SVGParserOutput:

    def __init__(self):
        self._elements: typing.Dict[str, typing.List[OCC.Core.TopoDS.TopoDS_Shape]] = {}

    def add_shape(self, key: str, shape: OCC.Core.TopoDS.TopoDS_Shape):
        if key not in self._elements:
            self._elements[key] = []

        self._elements[key].append(shape)

    def add_all(self, other):
        for k, v in other._elements.items():
            for s in v:
                self.add_shape(k, s)

    @property
    def shapes(self) -> typing.Generator[OCC.Core.TopoDS.TopoDS_Shape, None, None]:
        return itertools.chain(*self._elements.values())

    def get_compound(self) -> OCC.Core.TopoDS.TopoDS_Compound:
        return op.GeomUtils.make_compound(self.shapes)

    def modify_all(self, modifier: typing.Callable[[OCC.Core.TopoDS.TopoDS_Shape], OCC.Core.TopoDS.TopoDS_Shape]):
        for shape_list in self._elements.values():
            for i in range(0, len(shape_list)):
                shape_list[i] = modifier(shape_list[i])


class SVGParser:

    @staticmethod
    def parse_file(filename: str) -> SVGParserOutput:

        with open(filename) as f:
            return SVGParser.parse_svg(ElTree.parse(f).getroot())


    @staticmethod
    def parse_svg(node: ElTree.Element) -> SVGParserOutput:
        parse_output = SVGParserOutput()

        SVGParser._parse_svg_elements(parse_output, node, "/")

        # svg coords need to be mirrored in the y direction
        trsf = OCC.Core.gp.gp_Trsf()
        trsf.SetMirror(OCC.Core.gp.gp_ZOX())
        parse_output.modify_all(lambda s: OCC.Core.BRepBuilderAPI.BRepBuilderAPI_Transform(s, trsf, True).Shape())

        return parse_output

    @staticmethod
    def _parse_svg_elements(svg_parser_output: SVGParserOutput, node: ElTree.Element, path: str):
        ignored_nodes = {"metadata", "namedview", "defs", "image"}

        path += node.tag

        node_type = re.compile("\{.+\}").sub("", node.tag)

        if node_type == "svg":
            for subnode in node:
                SVGParser._parse_svg_elements(svg_parser_output, subnode, path)
        elif node_type == "g":
            trsf = OCC.Core.gp.gp_GTrsf()
            SVGTransformParser.parse(trsf, node)

            transformed_entities = SVGParserOutput()
            for subnode in node:
                SVGParser._parse_svg_elements(transformed_entities, subnode, path)

            transformed_entities.modify_all(
                lambda s: OCC.Core.BRepBuilderAPI.BRepBuilderAPI_GTransform(s, trsf, True).Shape())
            svg_parser_output.add_all(transformed_entities)

        elif node_type == "rect":
            svg_parser_output.add_shape(path, SVGRectParser.parse(node))
        elif node_type == "ellipse":
            svg_parser_output.add_shape(path, SVGEllipseParser.parse(node))
        elif node_type == "circle":
            svg_parser_output.add_shape(path, SVGCircleParser.parse(node))
        elif node_type == "path":
            svg_parser_output.add_shape(path, SVGPathParser.parse_wire(node))
        elif node_type in ignored_nodes:
            print(f"Skipping {node_type}")
        else:
            raise ValueError(f"Unknown svg element: {node_type}")


class SVGParserUtils:

    @staticmethod
    def get_path_faces(wires_to_fill: typing.List[OCC.Core.TopoDS.TopoDS_Wire]) -> Part:
        """
        Attempts to build svg "filled paths" out of the supplied wires
        """

        fused_wires = op.Cleanup.simplify_domain(op.BoolUtils.fuse(wires_to_fill), True, True, True) \
            if len(wires_to_fill) > 1 \
            else wires_to_fill[0]

        wires_to_fill = [w for w in op.Explorer.wire_explorer(fused_wires).get()]

        wires_faces = [(w, SVGParserUtils._create_bounded_face(w)) for w in wires_to_fill]

        wires_faces.sort(key=functools.cmp_to_key(SVGParserUtils._wf_cmp))

        make_faces = [
            (wires_faces[0], [])
        ]
        del wires_faces[0]

        # take the first face
        while len(wires_faces) > 0:
            last_added = make_faces[-1]

            to_add = wires_faces[0]
            del wires_faces[0]

            if OCC.Core.BRepFeat.brepfeat_IsInside(to_add[1], last_added[0][1]):
                last_added[1].append(to_add)
            else:
                make_faces.append((to_add, []))

        result = []
        for wf, wfs_to_cut in make_faces:
            mkf = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(wf[0])
            #op.VisualizationUtils.visualize(wf[0], *[cwf[0] for cwf in wfs_to_cut],
            #                                show_edge_orientations=True,
            #                                show_edge_endpoints=True,
            #                                show_face_normals=True)
            for cwf in wfs_to_cut:
                mkf.Add(cwf[0])

            result.append(Part(mkf.Face()))

        return result[0].add(*result[1:])

    @staticmethod
    def _wf_cmp(wf0: typing.Tuple[OCC.Core.TopoDS.TopoDS_Wire, OCC.Core.TopoDS.TopoDS_Face],
               wf1: typing.Tuple[OCC.Core.TopoDS.TopoDS_Wire, OCC.Core.TopoDS.TopoDS_Face]):
        return OCC.Core.BRepFeat.brepfeat_IsInside(wf0[1], wf1[1])

    @staticmethod
    def _cleanup_wire(wire: OCC.Core.TopoDS.TopoDS_Wire):
        plane = OCC.Core.gp.gp_Pln(
            OCC.Core.gp.gp.Origin(), OCC.Core.gp.gp.DZ()
        )

        sfw = OCC.Core.ShapeFix.ShapeFix_Wire(wire, OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(plane).Face(), 0.01)
        sfw.Load(wire)
        sfw.FixReorder()
        sfw.FixConnected()
        sfw.FixSmall(True)
        sfw.FixSelfIntersection()
        sfw.SetFixSelfIntersectingEdgeMode(True)
        sfw.SetFixSelfIntersectionMode(True)
        sfw.SetFixNonAdjacentIntersectingEdgesMode(True)
        sfw.SetFixIntersectingEdgesMode(True)
        sfw.SetFixReorderMode(True)
        sfw.SetFixConnectedMode(True)

        sfw.Perform()

        return sfw.Wire()

    @staticmethod
    def _reverse_edge(edge: OCC.Core.TopoDS.TopoDS_Edge):
        """
        Based on https://dev.opencascade.org/node/73040#comment-3070
        :param edge:
        :return:
        """
        curve, first, last = OCC.Core.BRep.BRep_Tool.Curve(edge)

        first = curve.ReversedParameter(first)
        last = curve.ReversedParameter(last)

        return OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(curve.Reversed(), last, first).Edge()

    @staticmethod
    def _reverse_wire(wire: OCC.Core.TopoDS.TopoDS_Wire):
        inverted_edges = [SVGParserUtils._reverse_edge(e) for e in op.Explorer.edge_explorer(wire).get()]
        mkw = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire()
        mkw.Add(op.ListUtils.list(inverted_edges))

        return mkw.Wire()

    @staticmethod
    def _create_bounded_face(wire: OCC.Core.TopoDS.TopoDS_Wire) -> OCC.Core.TopoDS.TopoDS_Face:
        wire = SVGParserUtils._cleanup_wire(wire)

        plane = OCC.Core.gp.gp_Pln(
            OCC.Core.gp.gp.Origin(), OCC.Core.gp.gp.DZ()
        )

        mkf = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(plane)

        mkf.Add(wire)
        result = mkf.Face()

        if op.InterrogateUtils.surface_properties(result).Mass() > 0:
            return result

        mkf = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(OCC.Core.gp.gp_Pln(
            OCC.Core.gp.gp.Origin(), OCC.Core.gp.gp.DZ()
        ))
        mkf.Add(SVGParserUtils._reverse_wire(wire))

        return mkf.Face()


if __name__ == "__main__":

    with open(sys.argv[1]) as f:
        eltree = ElTree.parse(f)

        parse_result = SVGParser.parse_svg(eltree.getroot())

        shapes = [s for s in parse_result.shapes]
        wires = [e for s in shapes for e in op.Explorer.wire_explorer(s).get()]

        path_faces = SVGParserUtils.get_path_faces(wires).pruned().preview(show_edge_orientations=True)



        # unify the wires to remove crossing points
        #wires_bool = op.Cleanup.simplify_domain(op.BoolUtils.fuse(wires), True, True, True)



        #op.VisualizationUtils.visualize(*[fw[1] for fw in wires_faces],
        #                                show_edge_endpoints=True,
        #                                show_edge_orientations=True,
        #                                show_face_normals=True,
        #                                arrange_shapes=True)


        #op.VisualizationUtils.visualize(*[wf[1] for wf in wires_faces], show_edge_endpoints=True, show_edge_orientations=True, show_face_normals=True)



        # preview
        #for w in wires_faces:
        #    offset_wf = [(
        #        op.TransformUtils.translate(wf[1], gp_Vec(0, 0, i * 30)),
        #        op.TransformUtils.translate(wf[1], gp_Vec(0, 0, i * 30))) for i, wf in enumerate(wires_faces)]
#
        #    op.VisualizationUtils.visualize(*[wf[0] for wf in offset_wf], *[wf[1] for wf in offset_wf],
        #                                show_edge_orientations=True,
        #                                show_edge_endpoints=True,
        #                                show_face_normals=True)





