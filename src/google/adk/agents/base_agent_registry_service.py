import abc
from typing import List


class BaseAgentRegistryService(abc.ABC):
    """Abstract base class for agent registry services."""

    @abc.abstractmethod
    def list_agent_ids(
        self,
        org_id: str,
        team_id: str,
        version: str,
    ) -> List[str]:
        """Returns a list of agent IDs for the given org/team/version."""
        pass

    @abc.abstractmethod
    def register_agent(
        self,
        org_id: str,
        team_id: str,
        version: str,
        agent_id: str,
        definition: dict,
    ):
        """Registers an agent definition (used by in-memory backend)."""
        pass

    @abc.abstractmethod
    def get_agent_definition(
        self,
        org_id: str,
        team_id: str,
        version: str,
        agent_id: str,
    ) -> dict | None:
        """Fetches an agent definition by ID."""
        pass 