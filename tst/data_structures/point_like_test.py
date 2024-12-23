import unittest
import OCC.Core.gp
from ezocc.data_structures.point_like import P3DLike


class PointLikeTest(unittest.TestCase):

    def test_p3d_like_create(self):
        point = P3DLike(1, 2, 3)

    def test_p3d_like_xyz(self):
        point = P3DLike(1, 2, 3)
        self.assertEqual((1, 2, 3), point.xyz)

    def test_p3d_like_gp_xyz(self):
        for t in [OCC.Core.gp.gp_Dir, OCC.Core.gp.gp_Pnt, OCC.Core.gp.gp_XYZ]:
            delegate = t(1, 2, 3)
            x = delegate.X()
            y = delegate.Y()
            z = delegate.Z()
            point = P3DLike.create(delegate)
            self.assertEqual(delegate, point.get(t))
            self.assertEqual(x, point.get(t).X())
            self.assertEqual(y, point.get(t).Y())
            self.assertEqual(z, point.get(t).Z())


