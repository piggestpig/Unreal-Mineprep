# Native property presentation

Use `(default, {metadata})` in ordinary `mineprep.PropertyGroup` declarations.
Entries are forwarded to the generated `unreal.uproperty`.

## Conditions and inline toggles

Complete declaration example; instantiate before displaying it:

```python
import mineprep
import unreal

class Options(mineprep.PropertyGroup):
    Enabled: bool = True
    Advanced: bool = False
    Count: int = (4, {'ClampMin': 0, 'UIMax': 64})
    Detail: float = (1.0, {
        'EditCondition': 'Enabled && (Advanced || Count > 1)',
        'EditConditionHides': True,
        'HideEditConditionToggle': True,
    })
    OverrideSpeed: bool = (False, {'InlineEditConditionToggle': True})
    Speed: float = (2.5, {
        'EditCondition': 'OverrideSpeed', 'ClampMin': 0,
        'Units': 'm/s', 'Delta': 0.1,
    })
    AutoRange: bool = (True, {'InlineEditConditionToggle': True})
    ManualRange: unreal.Vector2D = (unreal.Vector2D(0, 1), {
        'EditCondition': '!AutoRange',
    })

options = Options()
# Inside an existing Mod.draw or ui script: layout.prop(options)
```

- `EditCondition` keeps the row and disables its value. Add `EditConditionHides`
  when an inapplicable row should disappear. Neither clears its value.
- Use reflected field names, not localized labels or Python aliases. Boolean
  operators `!`, `&&`, `||`, grouping, numeric and supported enum comparisons are
  useful. This is a restricted parser, not a Python/C++ interpreter: do not assume
  arbitrary attribute access, string comparisons or Python method calls work.
- Put `InlineEditConditionToggle` on the controlling **bool** and reference it
  from the value's `EditCondition`. It suppresses the bool's standalone row.
  `!AutoRange` gives a checked manual control when AutoRange is false.
- A multi-field condition cannot supply a single editable inline bool. Keep the
  simple inline condition and hide an outer container for additional availability
  rules. `HideEditConditionToggle` suppresses an unwanted checkbox, not the row.
- SinglePropertyView (`layout.prop(options, 'Field')`) cannot show paired inline
  toggles; use the full `layout.prop(options)` for them.
- In PropertyGroup, conditions reference reflected fields in the same group;
  Python methods do not become UFunctions.

View binding and callbacks: [ui.md](ui.md#prop-callbacks).
Saving fields: [PropertyGroup](ui.md#propertygroup).

## Other useful metadata

| Need | Metadata / choice | Boundary |
| --- | --- | --- |
| Numeric limits | `ClampMin`, `ClampMax` | Enforced by the Details widget (does not clamp direct Python assignment) |
| Comfortable drag range | `UIMin`, `UIMax` | Slider drag range only; manual entry can exceed it |
| Drag increments / sensitivity | `Delta`, `SliderExponent` | Drag step sensitivity only |
| Seed/identifier entry | `NoSpinbox=True` | Hides spinbox arrows on numeric fields |
| Physical units | `Units='cm'`, `ForceUnits='cm'` | Display suffix only |
| Numeric presentation | `MaxFractionalDigits` | Display rounding only |
| Multiline text/code | `MultiLine=True` on `str` | Multiline text box in Details |
| Opaque-only color | `HideAlphaChannel=True` | Keep Alpha for painting or transparency |
| Asset selection | Typed UObject; `AllowedClasses` for soft paths | Typed `Texture2D`/`StaticMesh` already filters the picker |
| Files/directories | `unreal.FilePath` + `FilePathFilter`; `unreal.DirectoryPath` | Package paths (`/Game/...`) are `str` or `SoftObjectPath`, not `FilePath` |
| Display text | `DisplayName`, `ToolTip`, `ShortTooltip` | Plain strings are sufficient; optional [property localization](localization.md#property-groups) uses `Group.localize()` |
| Order within a category | `DisplayPriority`, `DisplayAfter` | PropertyGroup already assigns declaration-order priority |

Vector/custom struct widgets may process metadata differently from scalar widgets.

## Metadata versus property flags

**Do not use `{'AdvancedDisplay': True}` in `unreal.uproperty` or PropertyGroup
metadata: it has no effect on advanced-row display.** C++ AdvancedDisplay sets
`CPF_AdvancedDisplay`. UE 5.8's Python property declaration API has no argument
for that flag; storing an identically named metadata entry does not set it.
This is an Unreal Python API limitation, not a missing Mineprep builder feature.
For a Python form, use an explicit advanced bool with EditConditionHides instead.

Other C++ property specifiers such as `EditFixedSize`, `Transient` and edit/
visibility flags are likewise not arbitrary metadata keys. Consult the actual
Python declaration API rather than copying C++ specifiers into `meta`.
PropertyDef's getter/setter arguments are separate from metadata too.

## Sources and version checks

- Epic: [edit conditions](https://dev.epicgames.com/documentation/en-us/unreal-engine/edit-conditions-for-properties-in-the-details-panel-in-unreal-engine),
  [metadata](https://dev.epicgames.com/documentation/en-us/unreal-engine/metadata-specifiers-in-unreal-engine),
  [property specifiers](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-uproperties),
  [Python PropertyDef](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/PropertyDef).
- Installed source: `Engine/Source/Editor/PropertyEditor/Private/` for condition
  parsing and property widgets; Python property flags are set in
  `Engine/Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/Private/PyWrapperObject.cpp`.
- Mineprep `mc_widget.py`: PropertyGroup declarations and Layout.prop view selection.
  Recheck relevant behavior after engine/plugin upgrades.
