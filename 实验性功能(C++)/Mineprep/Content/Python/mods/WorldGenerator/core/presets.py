"""Parameter-only preset operations shared by editor and offline scripts."""
from ..ui_model import page_id
from .spec import WorldSpec


def section_keys(pack, section):
    section = page_id(section, pack)
    keys = tuple(k for k, d in pack.params.items() if page_id(d.page, pack) == section)
    if section in ('blocks', 'output') or not keys:
        raise ValueError(f'unknown generation section: {section!r}')
    return keys


def preset_sections(pack):
    """Membership uses declared keys, never defaults injected by resolve()."""
    return {pid: tuple(dict.fromkeys(page_id(pack.params[k].page, pack) for k in p.params
                                    if page_id(pack.params[k].page, pack) not in ('blocks', 'output')))
            for pid, p in pack.presets.items()}


def apply_preset(pack, spec, preset_id, section=None):
    if preset_id not in pack.presets:
        raise ValueError(f'unknown preset: {preset_id!r}')
    preset = pack.presets[preset_id]
    if section is None:
        if preset.section is not None:
            raise ValueError('local preset requires its section')
        result = spec.replace(preset=preset_id, params=())
    else:
        section = page_id(section, pack)
        keys = section_keys(pack, section)
        if preset.section is not None and preset.section != section:
            raise ValueError('local preset belongs to another section')
        patch = {k: v for k, v in preset.params.items() if k in keys}
        if not patch:
            raise ValueError('preset has no parameters in this section')
        result = spec.with_params({**pack.resolve(spec).to_dict(), **patch})
    pack.resolve(result)
    return result


def reset_section(pack, spec, section):
    result = spec.with_params({k: pack.params[k].default for k in section_keys(pack, section)})
    pack.resolve(result)
    return result
