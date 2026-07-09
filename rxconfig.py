from pathlib import Path

import reflex as rx
from reflex_base.environment import environment


# Keep the legacy repo-local data dir out of the dev file watcher. Reflex's
# exclusion check calls Path.samefile, which raises on missing paths — so only
# register the exclusion when the directory actually exists (it is gitignored
# and absent on fresh clones; runtime data now lives outside the repo anyway).
_legacy_data_dir = Path("data")
if _legacy_data_dir.is_dir():
    environment.REFLEX_HOT_RELOAD_EXCLUDE_PATHS.set([_legacy_data_dir])


class _StableSet(set):
    # Reflex serializes this into its frontend package-install cache.
    def __iter__(self):
        return iter(sorted(set.__iter__(self)))


# Use a non-default backend port to avoid common local 8000 conflicts.
# Override with REFLEX_BACKEND_PORT when needed.
config = rx.Config(app_name="dnd_and_beyond", backend_port=8101)
config._non_default_attributes = _StableSet(config._non_default_attributes)
