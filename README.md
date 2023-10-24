# EZ-OCC

## Examples

### Gears
![screenshot](resources/gears.png)

Parts store a hierarchy of shape data that persists between most operations.
These labels and attributes can be used to group together parts along with
their clearances (labelled parts are highlighted).

```python
def gears(cache):
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
```

### To create a bolt
![screenshot](resources/bolt_m4.png)
```python

def bolt_m4(cache: PartCache):
    factory = PartFactory(cache)

    thread_spec = ThreadSpec.metric("m4")

    body = factory.cylinder(thread_spec.d1_basic_minor_diameter / 2, 10)

    thread = factory.thread(thread_spec, True, 10, separate_sections=False)
    thread_chamfer_cylinder = factory.cylinder(thread.xts.x_span / 2 + 1, thread.xts.z_span) \
        .fillet.chamfer_edges(1.5, lambda e: Part.of_shape(e).xts.z_mid < thread.xts.z_mid)

    thread = thread.bool.common(thread_chamfer_cylinder)
    body = body.bool.common(thread_chamfer_cylinder)

    head = factory.polygon(1, 6) \
        .driver(PartFactory.PolygonDriver).set_flat_to_flat_dist(6) \
        .do_on("body", consumer=lambda p: p.make.face()) \
        .do_on("bounding_circle", consumer=lambda p: p.make.face()) \
        .extrude.prism(dz=3) \
        .do(lambda p: p.sp("body").bool.common(p.sp("bounding_circle").fillet.fillet_edges(0.5))) \
        .align().stack_z1(body)

    head = head.bool.cut(
        factory.text("M4", "arial", 10) \
            .tr.scale_to_y_span(2, scale_other_axes=True) \
            .align().by("xmidymidzmid", head) \
            .align().stack_z1(head) \
            .extrude.prism(dz=-0.2))

    return factory.compound(head, body, thread)
```

### Patterning the bolt, and building an enclosure with a shadow line
![screenshot](resources/enclosure.png)
```python

def enclosure(cache: PartCache):
    factory = PartFactory(cache)

    bolt = bolt_m4(cache).preview().tr.ry(math.radians(90)).incremental_pattern(
        range(0, 4), lambda p: p.tr.mv(dy=p.xts.y_span + 2))

    result = factory.box_surrounding(bolt, 3, 3, 3)\
        .do(lambda p: p.extrude.make_thick_solid(3).bool.cut(p))

    v0, v1 = result.pick.from_dir(1, 0, 0).as_list()[0:2]
    interface_cut = WireSketcher(*v0.xts.xyz_mid)\
        .line_to(x=MathUtils.lerp(x0=v0.xts.x_mid, x1=v1.xts.x_mid, coordinate_proportional=0.5)[0])\
        .line_to(z=2, is_relative=True)\
        .line_to(x=v1.xts.x_mid)\
        .get_wire_part(cache)\
        .extrude.offset(Constants.clearance_mm())

    spine = result.bool.common(
        factory.square_centered(result.xts.x_span, result.xts.y_span)
        .align().by("xmidymidzmid", result)).explore.wire.get_min(lambda w: InterrogateUtils.length(w.shape))

    result = result.bool.cut(
        interface_cut.loft.pipe(
            spine,
            transition_mode=OCC.Core.BRepBuilderAPI.BRepBuilderAPI_TransitionMode.BRepBuilderAPI_RoundCorner))\
        .cleanup()

    bottom, top = result.explore.solid.order_by(lambda s: s.xts.z_max).get()

    return factory.arrange(bottom.add(bolt), top.tr.ry(math.radians(180)), spacing=3)
```

### Chess Piece
![screenshot](resources/chess_piece.png)
```python

from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell as mps

def chess_piece(cache):
    factory = PartFactory(cache)

    base = factory.square_centered(20, 20).fillet.fillet2d_verts(1).make.face()
    top = factory.circle(7).align().com(base).tr.mv(dz=30).make.face()
    top_outer = top.tr.scale_to_x_span(top.xts.x_span + 5, scale_other_axes=True).align().com(top)

    head = factory.loft([
        top,
        top_outer.tr.mv(dz=5),
        top_outer.tr.mv(dz=10),
        top_outer.tr.scale_to_x_span(top_outer.xts.x_span - 2, scale_other_axes=True).align().com(top_outer).tr.mv(dz=10),
        top.tr.mv(dz=5)
    ], last_shape_name="top_face")

    head = head.bool.cut(
        factory.box(head.xts.x_span, 1, 1)
                     .align().by("xminmidymidzmax", head)
                     .extrude.make_thick_solid(1)
                     .pattern(range(0, 10), lambda i, p: p.tr.rz(math.radians(i * 360 / 10), offset=head.xts.xyz_mid)))

    m = mps(WireSketcher().line_to(z=30, is_relative=True).get_wire())
    m.SetMode(factory.helix(30, 10, 0.3).shape, True)

    m.Add(base.make.wire().shape)
    m.Add(top.make.wire().shape)

    body = factory.shell(*Part.of_shape(m.Shape())
        .add(base.make.face(), top.make.face()).explore.face.get())\
        .make.solid()

    base = factory.loft([
        base,
        base.tr.scale_to_x_span(base.xts.x_span + 2, scale_other_axes=True).align().com(base).tr.mv(dz=-5),
        base.tr.scale_to_x_span(base.xts.x_span + 1, scale_other_axes=True).align().com(base).tr.mv(dz=-10)
    ], last_shape_name="bottom")\
        .do(lambda f: f.fillet.chamfer_faces(1, f.sp("bottom")))

    return base.add(body, head)
```

### Parabolic dish with lattice support
![screenshot](resources/parabolic_dish_1.png)
![screenshot](resources/parabolic_dish_2.png)
Note: the lattice boolean operation is fairly slow (~=1m). 
After caching the script runs on the order of seconds.
```python

def dish(cache):
    factory = PartFactory(cache)

    curve = factory.parabola(100, 0, 60)

    inner = curve.sp("curve").revol.about(gp_OZ(), math.radians(360))
    outer = inner.extrude.make_thick_solid(4)

    rim = factory.loft([
        inner.explore.edge.get()[1].make.wire(),
        outer.explore.edge.get()[1].make.wire()
    ], is_solid=False)

    result = factory.shell(rim.explore.face.get()[0],
                         *inner.explore.face.get(),
                         *outer.explore.face.get())\
        .make.solid().cleanup.fix_solid()

    result_perimeter = factory.cylinder(inner.xts.x_span / 2,
                                        result.xts.z_span).align().by("xmidymidzmin", result)

    result = result.bool.common(result_perimeter)

    lattice_extrusion_thickness = 0.5

    support_lattice = factory.lattice(9, 9, True, True) \
        .tr.scale_to_x_span(result.xts.x_span - lattice_extrusion_thickness, scale_other_axes=True) \
        .do(lambda p: factory.union(*[w.extrude.offset(lattice_extrusion_thickness, spine=gp_XOY()).make.face() for w in p.explore.wire.get()]))\
        .sew.faces().cleanup()\
        .align().by("xmidymidzmid", result) \
        .bool.common(result_perimeter.extrude.make_thick_solid(-2 * lattice_extrusion_thickness)) \
        .cleanup()\
        .extrude.prism(dz=result.xts.z_span + 2)\
        .align().by("zmin", result).tr.mv(dz=-1)\
        .bool.cut(result).explore.solid.get_min(lambda s: s.xts.z_min)\
        .bool.cut(factory.box_surrounding(result).align().stack_z0(result))\
        .add(factory.ring(result_perimeter.xts.x_span / 2, result_perimeter.xts.x_span / 2 - lattice_extrusion_thickness * 2, inner.xts.z_span)
                    .align().by("xmidymidzmin", result))\
        .cleanup()

    result = result.cleanup.fix_solid().add(support_lattice)

    return result.bool.cut(factory.box(10, 10, result.xts.z_span).align().by("xmidymidzmin", result))

```

## Project goals

Primarily, this project is a python library that sits on top of pythonocc, which itself is a 
wrapper around OCCT (Open CasCade Technology), which itself is a very large set of tools and 
libraries for BRep ("Boundary Representation") modelling.

BRep modelling is preferable for CAD/CAM applications, where the requirement for explicit 
geometric definitions precludes mesh-based modelling (more common in CGI or artistic applications).
An imprecise analogy would be comparing SVG vector graphics to PNG rasterization.

OCCT is huge and quite powerful. Unfortunately it suffers from the limitations of hit-and-miss 
documentation, older coding conventions, poor feature discoverability, and the occasional comment
block written in French. All of these are easily offset by the fact that it is free and open source.

pythonocc is an admirably transparent wrapper around OCCT, exposing most of it without 
significant changes to the API, and adding a few extras, e.g. the viewer. OCCT entities such as the 
ubiquitous library-specific smart pointer are abstracted away (mostly) without issue.

This library attempts to provide a fluent API for performing tasks that would take hundreds 
of lines of code if written in pythonocc alone. The eventual aim is to have something like OpenSCAD, 
but with constraint based modelling and avoiding the DSL.

There are a few other dependencies that I have not mentioned yet. VTK 
(short for Visualization Tool Kit) is an OOP library based on OpenGL to automate the rendering of data sets 
mostly aimed at STEM applications. The inbuilt viewer classes that come with OCC (there is a VTK one)
were not customizable enough to be useful, so I had to implement my own. This issue has been a common 
theme when working with these tools, and why I choose to build them from source vs. using prebuilt 
packages from, for instance, apt.

Finally there is Solvespace, which hasn't really been integrated
very far but is intended to act as the geometric constraint solver (GCS) for when I get around to adding
constraint based modelling.

# Setup and Installation

## Requirements

- Docker ~= 20.10.22

## Dev setup

### Create an Image

There are quite a few dependencies and they can be quite tricky to get working together, 
so the best way is to create a docker container. See [docker](./docker). You can create the image by:

```commandline
# starting from project root

pushd docker
./docker_build.sh
```

The `Dockerfile` serves as documentation for how setup can be performed manually. Note that due 
to the specific versions required, the dependencies are cloned and built from source. This will
take quite a long time.

### To start the Container:

```commandline
./docker_run.sh
```

On start the container will install the python project as an editable pip package,
so any changes you make under `src` will have immediate effect.
The project directory is mapped to container dir `/wsp`.

To export files, e.g. `step`,`stl` you can use the project directory `output`, 
which is mapped to the container directory `/wsp/output`.

Due to the work which needs to be done at startup, you will probably want to
pause the container instead of killing it.

### Running Projects

By convention, executable projects are stored under the `projects` dir, it's simple to
run them:

```commandline
# in container, starting from /wsp
python3 projects/project_name.py
```

Since the library is under development and new features are added when needed, 
older projects are less likely to work. Check the commit history for
the most recent ones to have the best chance of them running correctly.

### Running Tests

To run the meagre set of unit tests:

```commandline
# in container, starting from /wsp
./run_tests.sh
```
