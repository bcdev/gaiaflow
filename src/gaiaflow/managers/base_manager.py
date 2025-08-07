from abc import ABC, abstractmethod
from pathlib import Path

from gaiaflow.constants import BaseActions


class BaseGaiaflowManager(ABC):
    def __init__(
        self,
        gaiaflow_path: Path,
        user_project_path: Path,
        action: BaseActions,
        force_new: bool = False,
        prune: bool = False,
        **kwargs,
    ):
        self.gaiaflow_path = gaiaflow_path
        self.user_project_path = user_project_path
        self.action = action
        self.force_new = force_new
        self.prune = prune

        if self.action == BaseActions.STOP:
            self.stop(**kwargs)

        if self.action == BaseActions.RESTART:
            self.restart(**kwargs)

        if self.action == BaseActions.START:
            self.start(**kwargs)

        if self.action == BaseActions.CLEANUP:
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
