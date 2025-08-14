from abc import ABC, abstractmethod
from pathlib import Path

from gaiaflow.constants import BaseAction


class BaseGaiaflowManager(ABC):
    def __init__(
        self,
        gaiaflow_path: Path,
        user_project_path: Path,
        action: BaseAction,
        force_new: bool = False,
        prune: bool = False,
        **kwargs,
    ):
        self.gaiaflow_path = gaiaflow_path
        self.user_project_path = user_project_path
        self.action = action
        self.force_new = force_new
        self.prune = prune

        # TODO: Move this into a classmethod run() which inits this Class and
        #  calls the action
        if self.action == BaseAction.STOP:
            self.stop(**kwargs)

        if self.action == BaseAction.RESTART:
            self.restart(**kwargs)

        if self.action == BaseAction.START:
            self.start(**kwargs)

        if self.action == BaseAction.CLEANUP:
            self.stop(**kwargs)
            self.cleanup(**kwargs)

    @abstractmethod
    def start(self, **kwargs):
        """Start the services provided by the manager.

        It can use the `force_new` variable to start a fresh set of services
        after removing the old ones.
        """

    @abstractmethod
    def stop(self, **kwargs):
        """Stop the services provided by the manager."""

    def restart(self, **kwargs):
        """Restart the services provided by the manager."""
        self.stop(**kwargs)
        self.start(**kwargs)

    @abstractmethod
    def cleanup(self, **kwargs):
        """Cleanup the services provided by the manager.

        It can use the `prune` flag to permanently delete the services
        provided by the manager.
        """
