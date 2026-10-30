"""Adapter contract checks independent of Unity, YOLO, or torch."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

HERE=Path(__file__).parent


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load under a private name with a fake state provider. This test cannot
        # accidentally start camera/model threads or change live runtime flags.
        cls.previous=sys.modules.get('usv.state')
        fake=types.ModuleType('usv.state');fake.runtime_settings={}
        sys.modules['usv.state']=fake
        spec=importlib.util.spec_from_file_location('test_adapter_private',HERE/'robust_hooks.py')
        cls.hooks=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.hooks)
        cls.flags=fake.runtime_settings

    @classmethod
    def tearDownClass(cls):
        if cls.previous is None:sys.modules.pop('usv.state',None)
        else:sys.modules['usv.state']=cls.previous

    def test_posterior_and_coast_share_one_clock(self):
        for enabled in [False,True]:
            self.flags['enable_kalman_filter']=enabled;state={}
            for i in range(30):self.hooks.update(state, .001*i, .5, 1000, 1000+i*.1)
            tracker=state['_robust_tracker']
            self.assertEqual(state['kf'] is not None,enabled)
            self.hooks.coast(state,1004)
            self.assertEqual(tracker.time,1004)
            self.hooks.update(state,.04,.5,950,1004)
            self.assertEqual(tracker.time,1004)
            self.assertEqual(state['kf_coast_time'],1004)
            self.assertGreater(state['prediction_confidence'],.99)
            self.assertGreater(self.hooks.posterior(state,0,0)[1],0)

    def test_toggle_during_loss_does_not_invent_an_observation(self):
        self.flags['enable_kalman_filter']=True;state={}
        self.hooks.update(state,0,.5,1000,1000)
        self.hooks.coast(state,1001)
        self.flags['enable_kalman_filter']=False
        self.hooks.coast(state,1001.1)
        self.assertIsNone(state['kf'])
        self.assertFalse(state['_robust_tracker'].kalman)
        self.assertEqual(state['_robust_tracker'].last_seen,1000)
        self.assertLess(state['prediction_confidence'],.7)
        self.flags['enable_kalman_filter']=True
        self.hooks.coast(state,1001.2)
        self.assertIsNotNone(state['kf'])
        self.assertEqual(state['_robust_tracker'].last_seen,1000)

    def test_long_loss_reinitializes_and_toggle_resets(self):
        self.flags['enable_kalman_filter']=True;state={}
        self.hooks.update(state,0,.5,1000,1000)
        old=state['_robust_tracker']
        self.hooks.update(state,.4,.5,300,1004)
        self.assertIsNot(state['_robust_tracker'],old)
        self.assertEqual(state['_robust_tracker'].state()[0],.4)
        self.flags['enable_kalman_filter']=False
        self.hooks.update(state,.3,.5,320,1004.1)
        self.assertIsNone(state['kf'])
        self.assertFalse(state['_robust_tracker'].kalman)

if __name__=='__main__':unittest.main()
