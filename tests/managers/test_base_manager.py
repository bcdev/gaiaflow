import unittest
from pathlib import Path
from unittest.mock import MagicMock

from gaiaflow.constants import BaseAction
from gaiaflow.managers.base_manager import BaseGaiaflowManager


class DummyManager(BaseGaiaflowManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started = False
        self.stopped = False
        self.cleaned = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def cleanup(self):
        self.cleaned = True


class TestBaseGaiaflowManager(unittest.TestCase):
    def setUp(self):
        self.gaiaflow_path = Path("/tmp/gaiaflow")
        self.user_project_path = Path("/tmp/project")

    def test_invalid_action_raises_value_error(self):
        class FakeAction:
            name = "FAKE"

        with self.assertRaises(ValueError) as ctx:
            DummyManager(self.gaiaflow_path, self.user_project_path, FakeAction())
        self.assertIn("Invalid action", str(ctx.exception))

    def test_valid_action_initialization(self):
        mgr = DummyManager(
            self.gaiaflow_path,
            self.user_project_path,
            BaseAction.START,
            force_new=True,
            prune=True,
        )
        self.assertEqual(mgr.gaiaflow_path, self.gaiaflow_path)
        self.assertEqual(mgr.user_project_path, self.user_project_path)
        self.assertEqual(mgr.action, BaseAction.START)
        self.assertTrue(mgr.force_new)
        self.assertTrue(mgr.prune)

    def test_restart_calls_stop_and_start(self):
        mgr = DummyManager(
            self.gaiaflow_path, self.user_project_path, BaseAction.RESTART
        )
        mgr.stop = MagicMock()
        mgr.start = MagicMock()

        mgr.restart()

        mgr.stop.assert_called_once()
        mgr.start.assert_called_once()

    def test_get_valid_actions_default(self):
        mgr = DummyManager(
            self.gaiaflow_path, self.user_project_path, BaseAction.START
        )
        actions = mgr._get_valid_actions()
        self.assertIn(BaseAction.START, actions)
        self.assertIn(BaseAction.STOP, actions)
        self.assertIn(BaseAction.RESTART, actions)
        self.assertIn(BaseAction.CLEANUP, actions)

    def test_cleanup_is_called(self):
        mgr = DummyManager(
            self.gaiaflow_path, self.user_project_path, BaseAction.CLEANUP
        )
        mgr.cleanup()
        self.assertTrue(mgr.cleaned)
