import unittest
import utils

class TestUtilsModules(unittest.TestCase):

    def test_cc(self):
        self.assertEqual(utils.cc_t_curve(280, 20), 280)
        self.assertEqual(utils.cc_t_curve(280, 10), 280)
        self.assertEqual(utils.cc_t_curve(280, 7.5), 140)
        self.assertEqual(utils.cc_t_curve(280, 5), 0)
        self.assertEqual(utils.cc_t_curve(280, -10), 0)

    def test_dc(self):
        self.assertEqual(utils.dc_t_curve(280, 20), 280)
        self.assertEqual(utils.dc_t_curve(280, 10), 280)
        self.assertEqual(utils.dc_t_curve(280, 7.5), 140)
        self.assertEqual(utils.dc_t_curve(280, 5), 0)
        self.assertEqual(utils.dc_t_curve(280, -10), 0)



if __name__ == '__main__':
    unittest.main()
