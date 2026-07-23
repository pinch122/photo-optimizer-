"""
Quality providers sub-package.

Exports the two built-in providers and the base classes needed to author
new providers.

Built-in providers
------------------
ClassicalProvider   PIL-based sharpness / exposure / resolution.
CLIPIQAProvider     Perceptual aesthetic score via CLIP prompt comparison.

Adding a new provider
---------------------
1. Create `providers/your_provider.py` subclassing QualityProvider.
2. Implement `evaluate()` and the `name` property.
3. Import and export it here.
4. Pass an instance to QualityService(providers=[..., YourProvider()]).
"""

from .base_provider import QualityProvider, ProviderResult
from .classical_provider import ClassicalProvider
from .clip_iqa_provider import CLIPIQAProvider

__all__ = [
    "QualityProvider",
    "ProviderResult",
    "ClassicalProvider",
    "CLIPIQAProvider",
]
