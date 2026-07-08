from pathlib import Path

import reflex as rx
from reflex_base.environment import environment


environment.REFLEX_HOT_RELOAD_EXCLUDE_PATHS.set([Path("data")])


class _StableSet(set):
    # Reflex serializes this into its frontend package-install cache.
    def __iter__(self):
        return iter(sorted(set.__iter__(self)))


# Use a non-default backend port to avoid common local 8000 conflicts.
# Override with REFLEX_BACKEND_PORT when needed.
config = rx.Config(app_name="dnd_and_beyond", backend_port=8101)
config._non_default_attributes = _StableSet(config._non_default_attributes)
