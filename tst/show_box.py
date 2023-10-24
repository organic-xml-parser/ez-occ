from ezocc.part_manager import PartFactory, NoOpPartCache

if __name__ == '__main__':
    PartFactory(NoOpPartCache.instance()).box(1, 1, 1, x_max_face_name="xmax", x_min_face_name="xmin")\
        .annotate("color", "red")\
        .annotate_subshape("xmin", ("color", "green"))\
        .preview()