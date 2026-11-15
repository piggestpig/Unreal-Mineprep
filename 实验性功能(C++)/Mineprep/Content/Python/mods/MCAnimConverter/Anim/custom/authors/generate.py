"""CLI & programmatic entry to generate/verify Mineprep procedurally authored Bedrock clips."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import types

if __package__ in (None, ''):
    _pkg = types.ModuleType('_mc_anim_authors')
    _pkg.__path__ = [str(Path(__file__).resolve().parent)]
    sys.modules[_pkg.__name__] = _pkg
    __package__ = _pkg.__name__

from .common import write_bedrock_clip
from .wolf_clips import build_wolf_play_bow

BEDROCK_DIR = Path(__file__).resolve().parents[1] / 'Bedrock'

CLIP_BUILDERS = {
    'wolf_play_bow.animation.json': build_wolf_play_bow,
}


def _select_builders(names: list[str] | tuple[str, ...] | None) -> list[str]:
    selected = list(names) if names else list(CLIP_BUILDERS)
    for filename in selected:
        if filename not in CLIP_BUILDERS:
            raise KeyError(f'Unknown clip builder: {filename}')
    return selected


def generate_all(output_dir: Path | str = BEDROCK_DIR, names: list[str] | tuple[str, ...] | None = None) -> list[Path]:
    """Generate selected (or all) procedurally authored Bedrock JSON files into `output_dir`."""
    dest = Path(output_dir)
    return [
        write_bedrock_clip(dest / filename, CLIP_BUILDERS[filename]())
        for filename in _select_builders(names)
    ]


def verify_all(output_dir: Path | str = BEDROCK_DIR, names: list[str] | tuple[str, ...] | None = None) -> list[str]:
    """Return registered clip filenames that are missing or differ from `output_dir`."""
    dest = Path(output_dir)
    mismatches: list[str] = []
    for filename in _select_builders(names):
        target = dest / filename
        if not target.is_file():
            mismatches.append(filename)
            continue
        existing = json.loads(target.read_text(encoding='utf-8-sig'))
        if existing != CLIP_BUILDERS[filename]():
            mismatches.append(filename)
    return mismatches


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description='Generate or verify procedural Mineprep custom Bedrock animations.')
    parser.add_argument('--out', type=Path, default=BEDROCK_DIR, help='Target Bedrock directory.')
    parser.add_argument('--only', nargs='*', help='Subset of registered output filenames.')
    parser.add_argument('--check', action='store_true', help='Verify existing Bedrock JSONs without overwriting.')
    args = parser.parse_args(argv)
    if args.check:
        mismatches = verify_all(args.out, args.only)
        if mismatches:
            print(f'drift detected: {", ".join(mismatches)}', file=sys.stderr)
            raise SystemExit(1)
        print(f'verified {len(_select_builders(args.only))} authored clip(s)')
        return
    for path in generate_all(args.out, args.only):
        print(f'wrote {path}')


if __name__ == '__main__':
    main()
