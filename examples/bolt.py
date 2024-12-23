from ezocc.part_manager import PartCache, PartFactory, ThreadSpec, Part

TITLE = "M4 Bolt"
DESCRIPTION = "Creating a Bolt"
FILENAME = "bolt"


def build(cache: PartCache):
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