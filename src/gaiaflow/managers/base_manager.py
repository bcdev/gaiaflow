from abc import ABC, abstractmethod
from pathlib import Path
from typing import Set

from gaiaflow.constants import Action, BaseAction


class BaseGaiaflowManager(ABC):
    def __init__(
        self,
        gaiaflow_path: Path,
        user_project_path: Path,
        action: Action,
        force_new: bool = False,
        prune: bool = False,
    ):
        valid_actions = self._get_valid_actions()
        if action not in valid_actions:
            valid_names = sorted([a.name for a in valid_actions])
            raise ValueError(f"Invalid action '{action.name}'. Valid: {valid_names}")

        self.gaiaflow_path = gaiaflow_path
        self.user_project_path = user_project_path
        self.action = action
        self.force_new = force_new
        self.prune = prune

    @abstractmethod
    def start(self):
        """Start the services provided by the manager.

        It can use the `force_new` variable to start a fresh set of services
        after removing the old ones.
        """

    @abstractmethod
    def stop(self):
        """Stop the services provided by the manager."""

    def restart(self):
        """Restart the services provided by the manager."""
        self.stop()
        self.start()

    @abstractmethod
    def cleanup(self):
        """Cleanup the services provided by the manager.

        It can use the `prune` flag to permanently delete the services
        provided by the manager.
        """

    def _get_valid_actions(self) -> Set[Action]:
        """Return set of valid actions for this manager. Override in subclasses."""
        return {
            BaseAction.START,
            BaseAction.STOP,
            BaseAction.RESTART,
            BaseAction.CLEANUP,
        }
