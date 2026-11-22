"""Publish a packaged Java GLB with catalog identity."""

import hashlib
import json

from mineprep.model_assets import RECIPE, SOURCE, publish_skinned_glb
from .importer import ENTRIES

SOURCE_HASH = 'VanillaMobLoader.SourceHash'


def build(entry, keys, target, path, version, *, recipe, shared_materials=None,
          face_spec=None, register_curves=(), face_options=None):
    return publish_skinned_glb(
        target, path, owner={SOURCE: 'java_glb', RECIPE: recipe, ENTRIES: json.dumps(keys)},
        metadata={'VanillaMobLoader.Version': version, 'VanillaMobLoader.Model': path.name,
                  'VanillaMobLoader.Name': entry.name,
                  SOURCE_HASH: hashlib.sha256(path.read_bytes()).hexdigest()},
        allow_pose_change=True,
        shared_materials=shared_materials,
        face_spec=face_spec,
        register_curves=register_curves,
        face_options=face_options,
    )
