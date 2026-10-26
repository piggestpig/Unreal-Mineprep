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

Options.localize('Speed', '速度', 'Speed', '速度')  # Class method, not a meta key.
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
| Numeric limits | `ClampMin`, `ClampMax` | Editor constraints; also validate programmatic inputs |
| Comfortable drag range | `UIMin`, `UIMax` | UI range, not an application limit |
| Drag increments / sensitivity | `Delta`, `SliderExponent` | Do not assume typed values are quantized |
| Seed/identifier entry | `NoSpinbox=True` | Avoid numeric dragging; preserve the numeric type |
| Physical units | `Units='cm'`, `ForceUnits='cm'` | Units may adapt display units; ForceUnits fixes them; establish application conversions separately |
| Numeric presentation | `MaxFractionalDigits` | Not a storage or generation precision contract |
| Multiline text/code | `MultiLine=True` on `str` | Preserve ordinary text and its persistence |
| Opaque-only color | `HideAlphaChannel=True` | Keep Alpha for painting or transparency |
| Asset selection | Typed UObject; `AllowedClasses` for soft paths | Typed Texture2D/StaticMesh already narrows the picker; validate operations too |
| Files/directories | `unreal.FilePath` + `FilePathFilter`; `unreal.DirectoryPath` | Package paths are not filesystem paths; changing an existing string type requires migration |
| Display text | `DisplayName`, `ToolTip` | For localized field labels, call the concrete group's class method as above; `localize` is not a metadata key |
| Order within a category | `DisplayPriority`, `DisplayAfter` | PropertyGroup already assigns declaration-order priority |

Vector/custom struct widgets may process metadata differently from scalar widgets.
Check their customization before assuming every key reaches every component. Do
not attach physical units to dimensionless noise or block coordinates merely to
shorten a label.

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
