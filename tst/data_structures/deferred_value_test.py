import unittest
import OCC.Core.gp

from ezocc.data_structures.deferred_value import DeferredValue


class DeferredValueTest(unittest.TestCase):

    def test_get(self):
        self.assertEqual(1, DeferredValue.of(1).resolve())
        self.assertEqual(2, DeferredValue.of(2).resolve())
        self.assertEqual(33, DeferredValue.of(33).resolve())

    def test_get_plus(self):
        self.assertEqual(3, (DeferredValue.of(1) + 2).resolve())

