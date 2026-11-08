"""WorldGenerator package. Importing it outside Unreal remains supported."""

# The Mod scanner imports this package. Load editor modules only on register.
# Localized display metadata lives in mod_manifest.toml.
mod_info = {
    "Version": "0.77.0",
    "EnabledByDefault": True,
    "ReloadWithMineprep": True,
    "Advanced": False,
}


def register():
    from .panel import WorldGenerator

    WorldGenerator.register(True)


def unregister():
    from . import panel, ops

    # The UE Blueprint close event normally calls destruct. Proactively stop
    # jobs so a missed close event cannot leave a ticker or staging import.
    for instance in list(panel.LIVE_INSTANCES):
        instance.destruct()
    ops.cancel_all()
    from .core.pack_modules import uninstall
    uninstall()
    panel.WorldGenerator.unregister()
