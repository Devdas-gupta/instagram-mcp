from abc import ABC, abstractmethod

class BaseProvider(ABC):
    """
    Abstract base class for MCP social platform providers.
    Allows modular expansion for Instagram, TikTok, Twitter/X, etc.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider and its dependencies."""
        pass

    @abstractmethod
    async def validate_session(self) -> bool:
        """Validate whether the provider currently has an active logged-in session."""
        pass
