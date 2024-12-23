

class RenderedEntitiesSpec:
    """
    Specifies which additional details to render, e.g. hints for face normals, edge directions.
    """

    def __init__(self,
                 visualize_face_normals: bool = True,
                 visualize_edge_directions: bool = True,
                 visualize_vertices: bool = True):
        self._visualize_face_normals = visualize_face_normals
        self._visualize_edge_directions = visualize_edge_directions
        self._visualize_vertices = visualize_vertices

    @property
    def visualize_face_normals(self):
        return self._visualize_face_normals

    @property
    def visualize_edge_directions(self):
        return self._visualize_edge_directions

    @property
    def visualize_vertices(self):
        return self._visualize_vertices
