"""WorldGenerator package. Importing it outside Unreal remains supported."""

# The Mod scanner imports this package. Load editor modules only on register.
mod_info = {
    "Description": "Pack-driven Minecraft-style world generation: preview, prepare and place in the editor.",
    "Version": "0.64.7",
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
