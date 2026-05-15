"""Provider implementations for the Blast Radius Scorer."""

from .base import Provider, ProviderReport, Capability
from .railway import RailwayProvider
from .aws import AWSProvider
from .supabase import SupabaseProvider

# Registry: provider name -> provider class.
PROVIDERS = {
    RailwayProvider.name: RailwayProvider,
    AWSProvider.name: AWSProvider,
    SupabaseProvider.name: SupabaseProvider,
}


def get_provider(name: str) -> Provider:
    """Instantiate a provider by name. Raises ValueError if unknown."""
    name = (name or "").lower()
    cls = PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown provider '{name}'. Supported: {', '.join(sorted(PROVIDERS))}"
        )
    return cls()


__all__ = [
    "Provider",
    "ProviderReport",
    "Capability",
    "RailwayProvider",
    "AWSProvider",
    "SupabaseProvider",
    "PROVIDERS",
    "get_provider",
]
