"""Synthetic exact grading/queue/env tests; no solver execution and no benchmark seeds."""
import unittest
from common import S6, load
from driver import environment
from grade import answer_key, algebraic_expression, descriptor_key, expression_key, serial

class Contract(unittest.TestCase):
    def test_exact_rational_power_and_root_sign(self):
        self.assertEqual(algebraic_expression('(2/9)**(1/3)'), (('9','0','0','-2'),0))
        self.assertNotEqual(expression_key('sqrt(2)'), expression_key('-sqrt(2)'))
    def test_equivalent_polynomial_and_representation(self):
        self.assertEqual(descriptor_key(('2','0','-4'),1), algebraic_expression('sqrt(2)'))
        self.assertEqual(descriptor_key(('-2','0','4'),1), algebraic_expression('sqrt(2)'))
        self.assertEqual(descriptor_key(('1','0','-3','0','2'),3), algebraic_expression('sqrt(2)'))
    def test_full_set_not_subset(self):
        refs=serial([expression_key('70'),expression_key('160')])
        self.assertNotEqual(refs,serial([expression_key('70')]))
        self.assertNotEqual(refs,serial([expression_key('70'),expression_key('160'),expression_key('0')]))
        self.assertEqual(refs,serial([expression_key('160'),expression_key('70'),expression_key('70')]))
    def test_affine_pi(self):
        d=lambda v:dict(minimal_polynomial=['1',str(-v)],real_root_index=0)
        self.assertEqual(answer_key(dict(kind='affine_pi',pi_coefficient=d(2),constant=d(3))),expression_key('2*pi+3'))
        self.assertEqual(answer_key(dict(kind='affine_pi',pi_coefficient=d(0),constant=d(3))),expression_key('3'))
    def test_env_and_fixed_queue(self):
        self.assertNotIn('GEOSOLVER_S3_TANGENCY_MODE',environment('T2'))
        self.assertEqual(environment('T1')['GEOSOLVER_S3_TANGENCY_MODE'],'T1')
        jobs=load(S6/'run-plan.json')['jobs']
        self.assertEqual(len(jobs),264)
        self.assertEqual(len({(j['identity'],j['seed'],j['configuration']) for j in jobs}),264)
        self.assertEqual({j['seed'] for j in jobs},{501,502,503})

if __name__=='__main__':
    unittest.main()
