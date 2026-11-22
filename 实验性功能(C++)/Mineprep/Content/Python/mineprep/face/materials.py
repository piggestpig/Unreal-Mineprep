from __future__ import annotations


try:
    import unreal
except ModuleNotFoundError:
    unreal = None

from .protocol import (
    DEFAULT_FACE_OPTIONS,
    FACE2D_CORE_MATERIAL,
    FACE2D_MATERIAL_VERSION,
    FACE3D_CORE_MATERIAL,
    FACE3D_MATERIAL_VERSION,
    FACE_CURVES,
    FACE_MAT_VERSION_TAG,
    _MOUTH_OPEN_DN,
    _MOUTH_OPEN_UP,
    _MOUTH_PUCKER_V,
    _MOUTH_PUCKER_X,
    _MOUTH_SHIFT_X,
    _MOUTH_SMILE_X,
    _MOUTH_SMILE_Y,
    _MOUTH_WIDE_X,
    hex_to_linear_rgba,
    normalize_face_options,
)


# ---------------------------------------------------------------------------
# Unreal Engine 5.8 Core Materials (`M_Face2D`, Dual-Mode `M_Face3D`) & Curve API
# ---------------------------------------------------------------------------

FACE2D_HLSL = """
// Mineprep 2D Trailer Face Synthesizer (UV0 = source features, UV1 = clean skin base)
float2 texSize = max(float2(TexWidth, TexHeight), float2(1.0, 1.0));
float2 p = UV0 * texSize;
float4 col = Texture2DSampleLevel(SkinTex, SkinTexSampler, UV1, 0);

// --- 1. Eyes (Sclera + Dynamic Blink / Wide + Independent Scaled Sliding Pupil) ---
float4 sockets[2] = { Rect_Eye_L, Rect_Eye_R };
float4 pupils[2]  = { Rect_Pupil_L, Rect_Pupil_R };
float  blinks[2]  = { saturate(face_blink_l), saturate(face_blink_r) };
float  lookXs[2]  = { clamp(face_look_x_l, -2.0, 2.0), clamp(face_look_x_r, -2.0, 2.0) };
float  wide       = clamp(face_eye_wide, -1.5, 1.5);
float  pScale     = clamp(1.0 + 0.35 * clamp(face_pupil_scale, -1.5, 1.5), 0.25, 1.9);
float  lookY      = clamp(face_look_y, -2.0, 2.0);

[unroll]
for (int ei = 0; ei < 2; ++ei)
{
    float4 s = sockets[ei];
    if (s.z > s.x && s.w > s.y)
    {
        float sw = s.z - s.x;
        float sh = s.w - s.y;
        float top = s.y - max(0.0, wide) * 0.50 * sh + max(0.0, -wide) * 0.38 * sh;
        float bot = s.w + max(0.0, wide) * 0.10 * sh - max(0.0, -wide) * 0.38 * sh;
        float openTop = lerp(top, bot, blinks[ei]);
        if (PixelSnap > 0.5)
        {
            openTop = round(openTop * 2.0) * 0.5;
            bot = round(bot * 2.0) * 0.5;
        }
        if (p.x >= s.x && p.x < s.z && p.y >= openTop && p.y < bot && (bot - openTop) > 0.02)
        {
            col.rgb = lerp(col.rgb, ScleraColor.rgb, saturate(ScleraColor.a));
            col.a = max(col.a, step(0.01, ScleraColor.a));

            float4 pr = pupils[ei];
            float pw = max(pr.z - pr.x, 0.5);
            float ph = max(pr.w - pr.y, 0.5);
            float maxDx = max(sw - pw, pw * 0.85);
            float maxDy = max((bot - top) - ph, ph * 0.40);
            float2 shift = float2(lookXs[ei] * maxDx, -lookY * maxDy);
            if (PixelSnap > 0.5)
            {
                shift = round(shift * 2.0) * 0.5;
            }
            float2 pCenter = 0.5 * (pr.xy + pr.zw) + shift;
            float2 pHalf   = 0.5 * float2(pw, ph) * pScale;
            float2 pMin    = pCenter - pHalf;
            float2 pMax    = pCenter + pHalf;
            if (p.x >= pMin.x && p.x < pMax.x && p.y >= pMin.y && p.y < pMax.y)
            {
                float2 samplePx = clamp(pr.xy + (p - pMin) / pScale, pr.xy + 0.02, pr.zw - 0.02);
                float4 pCol = Texture2DSampleLevel(SkinTex, SkinTexSampler, samplePx / texSize, 0);
                if (pCol.a > 0.05)
                {
                    col = pCol;
                }
            }
        }
    }
}

// --- 2. 2D Eyebrows (Separate Brows + Bridged Unibrow Support) ---
if (UseBrows > 0.5)
{
    float browYL = clamp(face_brow_y_l, -1.0, 1.0);
    float browYR = clamp(face_brow_y_r, -1.0, 1.0);
    float browRL = clamp(face_brow_rot_l, -1.0, 1.0);
    float browRR = clamp(face_brow_rot_r, -1.0, 1.0);
    bool isUnibrow = (Rect_Brow_L.z > Rect_Brow_L.x && Rect_Brow_R.z > Rect_Brow_R.x && abs(Rect_Brow_L.x - Rect_Brow_R.z) < 0.15);

    if (isUnibrow)
    {
        float uMin = Rect_Brow_R.x;
        float uMax = Rect_Brow_L.z;
        float vMin = min(Rect_Brow_R.y, Rect_Brow_L.y);
        float vMax = max(Rect_Brow_R.w, Rect_Brow_L.w);
        float midX = Rect_Brow_L.x;
        float halfSpan = max(0.5 * (uMax - uMin), 0.5);
        float relX = p.x - midX;
        float normX = clamp(relX / halfSpan, -1.0, 1.0);

        float blinkDip = (0.5 * (blinks[0] + blinks[1]) + 0.5 * (blinks[0] - blinks[1]) * normX) * (0.90 * saturate(BrowFollowBlink));
        float baseShiftY = -(0.5 * (browYL + browYR) + 0.5 * (browYL - browYR) * normX) * 1.25 + blinkDip;
        float centerDip  = -0.5 * (browRL + browRR) * 0.48;
        float sideSlope  = (relX >= 0.0 ? browRL : browRR) * 0.96 * abs(normX);
        float totalShiftY = baseShiftY + centerDip + sideSlope;
        if (PixelSnap > 0.5)
        {
            totalShiftY = round(totalShiftY * 2.0) * 0.5;
        }
        float2 srcP = float2(p.x, p.y - totalShiftY);
        if (srcP.x >= uMin && srcP.x < uMax && srcP.y >= vMin && srcP.y < vMax)
        {
            float2 bSample = clamp(srcP, float2(uMin, vMin) + 0.02, float2(uMax, vMax) - 0.02);
            float4 bCol = Texture2DSampleLevel(SkinTex, SkinTexSampler, bSample / texSize, 0);
            if (bCol.a > 0.05)
            {
                col = bCol;
            }
        }
    }
    else
    {
        float4 brows[2]    = { Rect_Brow_L, Rect_Brow_R };
        float  browYs[2]   = { browYL, browYR };
        float  browRs[2]   = { browRL, browRR };
        float  rotSigns[2] = { 1.0, -1.0 };

        [unroll]
        for (int bi = 0; bi < 2; ++bi)
        {
            float4 br = brows[bi];
            if (br.z > br.x && br.w > br.y)
            {
                float2 bc = 0.5 * (br.xy + br.zw);
                float2 shift = float2(0.0, -browYs[bi] * 1.25 + blinks[bi] * (0.90 * saturate(BrowFollowBlink)));
                if (PixelSnap > 0.5)
                {
                    shift = round(shift * 2.0) * 0.5;
                }
                float ang = browRs[bi] * rotSigns[bi] * 0.38;
                float ca = cos(-ang);
                float sa = sin(-ang);
                float2 rel = p - (bc + shift);
                float2 srcP = bc + float2(rel.x * ca - rel.y * sa, rel.x * sa + rel.y * ca);
                if (srcP.x >= br.x && srcP.x < br.z && srcP.y >= br.y && srcP.y < br.w)
                {
                    float2 bSample = clamp(srcP, br.xy + 0.02, br.zw - 0.02);
                    float4 bCol = Texture2DSampleLevel(SkinTex, SkinTexSampler, bSample / texSize, 0);
                    if (bCol.a > 0.05)
                    {
                        col = bCol;
                    }
                }
            }
        }
    }
}

// --- 3. 2D Trailer Mouth (Consistent Skin Lip Color + Stylized Blocky Scaling) ---
if (UseMouth > 0.5 && Rect_Mouth.z > Rect_Mouth.x && Rect_Mouth.w > Rect_Mouth.y)
{
    float4 mr = Rect_Mouth;
    float mOpen  = clamp(face_mouth_open, -1.0, 1.0);
    float mWide  = clamp(face_mouth_wide, -1.0, 1.0);
    float mSmile = clamp(face_mouth_smile, -1.0, 1.0);
    float mX     = clamp(face_mouth_x, -1.0, 1.0);
    float active = max(max(abs(mOpen), abs(mWide)), max(abs(mSmile), abs(mX)));

    if (active < 0.01)
    {
        if (p.x >= mr.x - 0.04 && p.x <= mr.z + 0.04 && p.y >= mr.y - 0.04 && p.y <= mr.w + 0.04)
        {
            float4 lipRest = Texture2DSampleLevel(SkinTex, SkinTexSampler, UV0, 0);
            col.rgb = lerp(lipRest.rgb, MouthColor.rgb, saturate(MouthColor.a));
            col.a = lipRest.a;
        }
    }
    else
    {
        float openPos   = max(0.0, mOpen);
        float openScale = max(0.0, 1.0 + mOpen);
        float2 mc = 0.5 * (mr.xy + mr.zw) + float2(mX * 0.85, 0.25 * openPos);
        float hw = max(0.30, 0.5 * (mr.z - mr.x) * (1.0 + 0.55 * mWide + 0.20 * abs(mSmile)));
        float hh = 0.5 * (mr.w - mr.y) * openScale * (1.0 - 0.20 * saturate(abs(mSmile) - openPos * 2.0));
        float dx = (p.x - mc.x) / hw;
        float bend = -mSmile * 0.35 * (dx * dx - 0.35);
        float py = p.y - bend;
        if (PixelSnap > 0.5)
        {
            py = round(py * 2.0) * 0.5;
        }
        if (hh > 0.005 && abs(dx) <= 1.0 && abs(py - mc.y) <= hh)
        {
            float2 lipSample = clamp(mr.xy + float2((dx * 0.5 + 0.5) * (mr.z - mr.x), 0.5 * (mr.w - mr.y)), mr.xy + 0.02, mr.zw - 0.02);
            float4 lipCol = Texture2DSampleLevel(SkinTex, SkinTexSampler, lipSample / texSize, 0);
            col.rgb = lerp(lipCol.rgb, MouthColor.rgb, saturate(MouthColor.a));
            col.a = 1.0;
        }
    }
}

return col;
""".strip()


FACE3D_VS_HLSL = f"""
// Mineprep 3D Dual-Mode Vertex DeltaUV (Single UV0 + COLOR_0 failsafe)
// VCol.a > 0.75 (1.0): static (failsafe default when COLOR_0 is absent)
// VCol.a in [0.25, 0.75] (0.5): above-eye rim UV slide (UP-only matching `_mc_eye_wide_pos = max(face_eye_wide, 0)`)
// VCol.a < 0.25 (0.0): mouth-ring UV slide (G = xn, B = signed_w)
if (VCol.a > 0.75)
{{
    return float2(0.0, 0.0);
}}
if (UVSlideMode > 0.5)
{{
    float3 dPos = (PosCurr - PosBind);
    return float2(dot(dPos, FaceU_Grad.xyz), dot(dPos, FaceV_Grad.xyz));
}}
float2 invTex = 1.0 / max(float2(TexWidth, TexHeight), float2(1.0, 1.0));
if (VCol.a >= 0.25)
{{
    float dv_eye = -VCol.b * 2.0 * max(0.0, face_eye_wide);
    return float2(0.0, dv_eye) * invTex;
}}
float xn = VCol.g * 2.0 - 1.0;
if (abs(xn) < 0.01) xn = 0.0;
float sw = VCol.b * 2.0 - 1.0;
float w  = (abs(sw) < 0.02) ? 0.0 : abs(sw);
float arch = max(0.22, 1.0 - 0.70 * xn * xn);
float mOpenPos = max(0.0, face_mouth_open);
float mPucker  = max(0.0, -face_mouth_open);
float du_px = w * (xn * ({_MOUTH_WIDE_X} * face_mouth_wide + {_MOUTH_SMILE_X} * face_mouth_smile - {_MOUTH_PUCKER_X} * mPucker) + {_MOUTH_SHIFT_X} * face_mouth_x);
float dv_px = w * ((sw >= 0.0 ? -{_MOUTH_OPEN_UP} : {_MOUTH_OPEN_DN}) * arch * mOpenPos + (sw >= 0.0 ? {_MOUTH_PUCKER_V} : -{_MOUTH_PUCKER_V}) * mPucker - (xn * xn - 0.25) * {_MOUTH_SMILE_Y} * face_mouth_smile);
return float2(du_px, dv_px) * invTex;
""".strip()


FACE3D_PS_HLSL = """
// Mineprep 3D Face Pixel Shader (Single UV0 + VertexInterpolator DeltaUV + MouthCavityColor)
if (VColR < 0.25)
{
    return float4(MouthCavityColor.rgb, 1.0);
}
float2 finalUV = UV0 + DeltaUV;
if (VColA < 0.25 && Rect_Mouth_UV.z > Rect_Mouth_UV.x && Rect_Mouth_UV.w > Rect_Mouth_UV.y)
{
    if (finalUV.x > Rect_Mouth_UV.x && finalUV.x < Rect_Mouth_UV.z &&
        finalUV.y > Rect_Mouth_UV.y && finalUV.y < Rect_Mouth_UV.w)
    {
        // Erase painted 2D mouth strictly in head-frozen finalUV space so horizontal/vertical mouth
        // shifts never drag or shear the left/right cheek or beard seam across the lower face.
        float midX = 0.5 * (Rect_Mouth_UV.x + Rect_Mouth_UV.z);
        float halfPxU = 0.5 / max(TexWidth, 1.0);
        finalUV.x = (finalUV.x < midX) ? (Rect_Mouth_UV.x - halfPxU) : (Rect_Mouth_UV.z + halfPxU);
    }
}
float4 col = Texture2DSampleLevel(SkinTex, SkinTexSampler, finalUV, 0);
col.rgb *= VColR;
return col;
""".strip()


def _copy_labpbr_defaults(instance) -> None:
    """Sync LabPBR defaults from `皮肤_Steve` so face and body match seamlessly under lighting."""
    mel = unreal.MaterialEditingLibrary
    steve_ref = unreal.load_asset('/Game/Mineprep/材质/皮肤/Core/皮肤_Steve')
    if not steve_ref:
        return
    for sname in ('照明强度', '单面', '发光亮度', '法线强度', '视差凹凸强度'):
        mel.set_material_instance_scalar_parameter_value(
            instance, sname, mel.get_material_instance_scalar_parameter_value(steve_ref, sname),
        )
    for vname in ('不透明R~G+B*A', '金属/高光/粗糙/孔隙率', '次表面颜色RGB+透射A', '纹理颜色'):
        mel.set_material_instance_vector_parameter_value(
            instance, vname, mel.get_material_instance_vector_parameter_value(steve_ref, vname),
        )


def _wire_labpbr_output(mat, source_expr, x: int, y: int) -> None:
    mel = unreal.MaterialEditingLibrary
    lab_fn_asset = unreal.load_asset('/Game/Mineprep/材质/Core/LabPBR总材质函数')
    if lab_fn_asset is not None:
        lab_call = mel.create_material_expression(mat, unreal.MaterialExpressionMaterialFunctionCall, x, y)
        lab_call.set_material_function(lab_fn_asset)
        mel.connect_material_expressions(source_expr, '', lab_call, '重载纹理贴图')
        mel.connect_material_property(lab_call, '已遮罩材质', unreal.MaterialProperty.MP_FRONT_MATERIAL)
        mel.connect_material_property(lab_call, '不透明蒙版', unreal.MaterialProperty.MP_OPACITY_MASK)
        mel.connect_material_property(lab_call, '环境光遮挡', unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
        mel.connect_material_property(lab_call, '全局位置偏移', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    else:
        mel.connect_material_property(source_expr, '', unreal.MaterialProperty.MP_BASE_COLOR)


def _warn_face(msg: str) -> None:
    try:
        from mineprep import utils
        utils.warn(msg)
    except Exception:
        if unreal is not None:
            unreal.log_warning(msg)


def _prepare_master_material(destination: str, *, rebuild: bool, expected_version: str | None = None):
    if unreal is None:
        raise RuntimeError('Material creation requires Unreal Editor')
    lib = unreal.EditorAssetLibrary
    if lib.does_asset_exist(destination) and not rebuild:
        loaded = unreal.load_asset(destination)
        if isinstance(loaded, unreal.Material):
            if expected_version:
                actual = str(lib.get_metadata_tag(loaded, FACE_MAT_VERSION_TAG) or '').strip()
                if actual != str(expected_version):
                    _warn_face(
                        f'表情母材质 {destination} 版本为 {actual or "未标记"}（当前推荐版本 v{expected_version}）。'
                        '为保留可能存在的手动修改未自动覆盖，如需重建请调用 rebuild=True。'
                    )
            return loaded, False
    folder, asset_name = destination.rsplit('/', 1)
    lib.make_directory(folder)
    mel = unreal.MaterialEditingLibrary
    if lib.does_asset_exist(destination):
        mat = unreal.load_asset(destination)
        mel.delete_all_material_expressions(mat)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name, folder, unreal.Material, unreal.MaterialFactoryNew(),
        )
    if not isinstance(mat, unreal.Material):
        raise RuntimeError('无法创建材质: ' + destination)
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_SUBSURFACE_PROFILE)
    mat.set_editor_property('two_sided', True)
    mat.set_editor_property('used_with_skeletal_mesh', True)
    return mat, True


def _wire_custom_inputs(mat, custom, wiring) -> None:
    mel = unreal.MaterialEditingLibrary
    inputs = []
    for pin_name, _, _ in wiring:
        ci = unreal.CustomInput()
        ci.set_editor_property('input_name', pin_name)
        inputs.append(ci)
    custom.set_editor_property('inputs', inputs)
    for pin_name, expr, out_pin in wiring:
        if not mel.connect_material_expressions(expr, out_pin, custom, pin_name):
            mel.connect_material_expressions(expr, '', custom, pin_name)


def _add_default_skin_tex(mat, x: int, y: int):
    mel = unreal.MaterialEditingLibrary
    skin_tex = mel.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, x, y)
    skin_tex.set_editor_property('parameter_name', '纹理贴图')
    skin_tex.set_editor_property('group', '01_Textures & Layout')
    default_steve = unreal.load_asset('/Game/Mineprep/材质/皮肤/Core/皮肤_Steve')
    if default_steve:
        base_tex = mel.get_material_instance_texture_parameter_value(default_steve, '纹理贴图')
        if base_tex:
            skin_tex.set_editor_property('texture', base_tex)
    return skin_tex


def ensure_face2d_material(destination: str = FACE2D_CORE_MATERIAL, *, rebuild: bool = False):
    """Ensure `/Game/Mineprep/材质/Core/M_Face2D` exists and is compiled."""
    mat, needs_build = _prepare_master_material(
        destination, rebuild=rebuild, expected_version=FACE2D_MATERIAL_VERSION,
    )
    if not needs_build:
        return mat
    mel = unreal.MaterialEditingLibrary

    def add_scalar(name: str, default: float, group: str, x: int, y: int):
        node = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('default_value', float(default))
        node.set_editor_property('group', group)
        return node

    def add_vector4(name: str, rgba: tuple[float, float, float, float], group: str, x: int, y: int):
        node = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, x, y)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('default_value', unreal.LinearColor(*rgba))
        node.set_editor_property('group', group)
        app = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, x + 220, y)
        mel.connect_material_expressions(node, '', app, 'A')
        mel.connect_material_expressions(node, 'A', app, 'B')
        return app

    uv0 = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1100, -520)
    uv0.set_editor_property('coordinate_index', 0)
    uv1 = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1100, -420)
    uv1.set_editor_property('coordinate_index', 1)
    skin_tex = _add_default_skin_tex(mat, -1100, -300)

    tex_w = add_scalar('TexWidth', 64.0, '01_Textures & Layout', -1100, -120)
    tex_h = add_scalar('TexHeight', 64.0, '01_Textures & Layout', -1100, -30)
    use_brows = add_scalar('UseBrows', 0.0, '01_Textures & Layout', -1100, 60)
    use_mouth = add_scalar('UseMouth', 1.0, '01_Textures & Layout', -1100, 150)
    pixel_snap = add_scalar('PixelSnap', 0.0, '01_Textures & Layout', -1100, 240)
    brow_follow_blink = add_scalar('BrowFollowBlink', 0.0, '01_Textures & Layout', -1100, 320)

    rect_defs = (
        ('Rect_Eye_L', (13.0, 12.0, 15.0, 13.0)),
        ('Rect_Eye_R', (9.0, 12.0, 11.0, 13.0)),
        ('Rect_Pupil_L', (13.0, 12.0, 14.0, 13.0)),
        ('Rect_Pupil_R', (10.0, 12.0, 11.0, 13.0)),
        ('Rect_Brow_L', (13.0, 11.0, 15.0, 12.0)),
        ('Rect_Brow_R', (9.0, 11.0, 11.0, 12.0)),
        ('Rect_Mouth', (11.0, 14.0, 13.0, 15.0)),
    )
    rect_nodes = [
        (name, add_vector4(name, vals, '02_Rects (LeftU, TopV, RightU, BottomV)', -1100, 380 + i * 160))
        for i, (name, vals) in enumerate(rect_defs)
    ]
    sclera_col = add_vector4('ScleraColor', (1.0, 1.0, 1.0, 1.0), '03_Colors', -1100, 1540)
    mouth_col = add_vector4('MouthColor', (0.0, 0.0, 0.0, 0.0), '03_Colors', -1100, 1710)
    curve_nodes = [
        (cname, add_scalar(cname, 0.0, '04_Face Curves', -720, -520 + i * 95))
        for i, cname in enumerate(FACE_CURVES)
    ]

    custom = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -220, 120)
    custom.set_editor_property('description', 'Face2D_HLSL')
    custom.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    custom.set_editor_property('code', FACE2D_HLSL)

    wiring = [
        ('UV0', uv0, ''), ('UV1', uv1, ''), ('SkinTex', skin_tex, ''),
        ('TexWidth', tex_w, ''), ('TexHeight', tex_h, ''),
        ('UseBrows', use_brows, ''), ('UseMouth', use_mouth, ''), ('PixelSnap', pixel_snap, ''),
        ('BrowFollowBlink', brow_follow_blink, ''),
        *((name, node, '') for name, node in rect_nodes),
        ('ScleraColor', sclera_col, ''), ('MouthColor', mouth_col, ''),
        *((cname, node, '') for cname, node in curve_nodes),
    ]
    _wire_custom_inputs(mat, custom, wiring)
    _wire_labpbr_output(mat, custom, 180, 120)

    mel.recompile_material(mat)
    lib = unreal.EditorAssetLibrary
    lib.set_metadata_tag(mat, FACE_MAT_VERSION_TAG, FACE2D_MATERIAL_VERSION)
    policy = str(lib.get_metadata_tag(mat, 'Mineprep.MaterialPolicy') or '').strip()
    if not policy or policy == 'keep_parent':
        lib.set_metadata_tag(mat, 'Mineprep.MaterialPolicy', 'keep')
    if not lib.save_loaded_asset(mat):
        raise RuntimeError('保存 M_Face2D 材质失败: ' + destination)
    return mat


def ensure_face3d_material(destination: str = FACE3D_CORE_MATERIAL, *, rebuild: bool = False):
    """Ensure `/Game/Mineprep/材质/Core/M_Face3D` exists (Single UV0 + Dual-Mode Analytic/Geometric)."""
    mat, needs_build = _prepare_master_material(
        destination, rebuild=rebuild, expected_version=FACE3D_MATERIAL_VERSION,
    )
    if not needs_build:
        return mat
    mat.set_editor_property('used_with_morph_targets', True)
    mel = unreal.MaterialEditingLibrary

    def add_scalar(name: str, default: float, group: str, x: int, y: int):
        node = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('default_value', float(default))
        node.set_editor_property('group', group)
        return node

    def add_vector4(name: str, rgba: tuple[float, float, float, float], group: str, x: int, y: int):
        node = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, x, y)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('default_value', unreal.LinearColor(*rgba))
        node.set_editor_property('group', group)
        app = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, x + 220, y)
        mel.connect_material_expressions(node, '', app, 'A')
        mel.connect_material_expressions(node, 'A', app, 'B')
        return app

    uv0 = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -960, -520)
    uv0.set_editor_property('coordinate_index', 0)

    lp_curr = mel.create_material_expression(mat, unreal.MaterialExpressionLocalPosition, -1420, -340)
    lp_curr.set_editor_property('local_origin', unreal.LocalPositionOrigin.INSTANCE)
    lp_curr.set_editor_property('included_offsets', unreal.PositionIncludedOffsets.EXCLUDE_OFFSETS)

    lp_bind = mel.create_material_expression(mat, unreal.MaterialExpressionLocalPosition, -1420, -230)
    lp_bind.set_editor_property('local_origin', unreal.LocalPositionOrigin.INSTANCE_PRE_SKINNING)
    lp_bind.set_editor_property('included_offsets', unreal.PositionIncludedOffsets.EXCLUDE_OFFSETS)

    vcol = mel.create_material_expression(mat, unreal.MaterialExpressionVertexColor, -1420, -100)
    vcol_rgba = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, -1180, -100)
    mel.connect_material_expressions(vcol, '', vcol_rgba, 'A')
    mel.connect_material_expressions(vcol, 'A', vcol_rgba, 'B')

    slide_mode = add_scalar('UVSlideMode', 0.0, '01_Textures & Layout', -1420, 40)
    tex_w = add_scalar('TexWidth', 64.0, '01_Textures & Layout', -1420, 130)
    tex_h = add_scalar('TexHeight', 64.0, '01_Textures & Layout', -1420, 220)
    # Default UV gradients for standard +X 64x64 player head (6.25 cm/px -> 1/(6.25*64)=0.0025 UV/cm)
    face_u_grad = add_vector4('FaceU_Grad', (0.0, -0.0025, 0.0, 0.0), '02_Custom Multi-Bone (UVSlideMode=1)', -1420, 330)
    face_v_grad = add_vector4('FaceV_Grad', (0.0, 0.0, -0.0025, 0.0), '02_Custom Multi-Bone (UVSlideMode=1)', -1420, 490)

    e_wide = add_scalar('face_eye_wide', 0.0, '04_Face Curves', -1420, 580)
    m_open = add_scalar('face_mouth_open', 0.0, '04_Face Curves', -1420, 670)
    m_wide = add_scalar('face_mouth_wide', 0.0, '04_Face Curves', -1420, 760)
    m_smile = add_scalar('face_mouth_smile', 0.0, '04_Face Curves', -1420, 850)
    m_x = add_scalar('face_mouth_x', 0.0, '04_Face Curves', -1420, 940)

    vs_custom = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -940, -120)
    vs_custom.set_editor_property('description', 'Face3D_VS_DeltaUV')
    vs_custom.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    vs_custom.set_editor_property('code', FACE3D_VS_HLSL)
    _wire_custom_inputs(mat, vs_custom, [
        ('PosCurr', lp_curr, ''), ('PosBind', lp_bind, ''), ('VCol', vcol_rgba, ''),
        ('UVSlideMode', slide_mode, ''), ('TexWidth', tex_w, ''), ('TexHeight', tex_h, ''),
        ('FaceU_Grad', face_u_grad, ''), ('FaceV_Grad', face_v_grad, ''),
        ('face_eye_wide', e_wide, ''),
        ('face_mouth_open', m_open, ''), ('face_mouth_wide', m_wide, ''),
        ('face_mouth_smile', m_smile, ''), ('face_mouth_x', m_x, ''),
    ])

    vi = mel.create_material_expression(mat, unreal.MaterialExpressionVertexInterpolator, -620, -120)
    mel.connect_material_expressions(vs_custom, '', vi, 'VS')

    skin_tex = _add_default_skin_tex(mat, -940, 140)
    rect_mouth = add_vector4('Rect_Mouth_UV', (0.0, 0.0, 0.0, 0.0), '01_Textures & Layout', -940, 320)
    cavity_col = add_vector4('MouthCavityColor', hex_to_linear_rgba(DEFAULT_FACE_OPTIONS['mouth_cavity_color'], 1.0), '03_Colors', -940, 490)

    ps_custom = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -240, 40)
    ps_custom.set_editor_property('description', 'Face3D_PS_HLSL')
    ps_custom.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    ps_custom.set_editor_property('code', FACE3D_PS_HLSL)
    _wire_custom_inputs(mat, ps_custom, [
        ('UV0', uv0, ''), ('DeltaUV', vi, ''),
        ('VColR', vcol, 'R'), ('VColA', vcol, 'A'),
        ('SkinTex', skin_tex, ''), ('TexWidth', tex_w, ''),
        ('Rect_Mouth_UV', rect_mouth, ''), ('MouthCavityColor', cavity_col, ''),
    ])

    _wire_labpbr_output(mat, ps_custom, 180, 40)

    mel.recompile_material(mat)
    lib = unreal.EditorAssetLibrary
    lib.set_metadata_tag(mat, FACE_MAT_VERSION_TAG, FACE3D_MATERIAL_VERSION)
    policy = str(lib.get_metadata_tag(mat, 'Mineprep.MaterialPolicy') or '').strip()
    if not policy or policy == 'keep_parent':
        lib.set_metadata_tag(mat, 'Mineprep.MaterialPolicy', 'keep')
    if not lib.save_loaded_asset(mat):
        raise RuntimeError('保存 M_Face3D 材质失败: ' + destination)
    return mat


def create_face2d_material(
    texture, destination: str, spec: dict, created: list | None = None, *, options: dict | None = None,
):
    """Create a configured MaterialInstanceConstant from `M_Face2D` matching LabPBR defaults."""
    if unreal is None:
        raise RuntimeError('create_face2d_material requires Unreal Editor')
    mel = unreal.MaterialEditingLibrary
    opts = normalize_face_options(options)
    parent = ensure_face2d_material()
    folder, asset_name = destination.rsplit('/', 1)
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew(),
    )
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError('Failed to create Face2D material instance: ' + destination)
    if created is not None:
        created.append(instance)
    mel.set_material_instance_parent(instance, parent)
    _copy_labpbr_defaults(instance)

    mel.set_material_instance_texture_parameter_value(instance, '纹理贴图', texture)
    if mel.get_material_instance_texture_parameter_value(instance, '纹理贴图') != texture:
        raise RuntimeError('Failed to assign Face2D skin texture')

    tw, th = spec['tex_size']
    mel.set_material_instance_scalar_parameter_value(instance, 'TexWidth', float(tw))
    mel.set_material_instance_scalar_parameter_value(instance, 'TexHeight', float(th))
    mel.set_material_instance_scalar_parameter_value(instance, 'UseBrows', 1.0 if spec.get('use_brows') else 0.0)
    mel.set_material_instance_scalar_parameter_value(instance, 'UseMouth', 1.0 if spec.get('use_mouth') else 0.0)
    mel.set_material_instance_scalar_parameter_value(instance, 'PixelSnap', float(spec.get('pixel_snap', 0.0)))
    mel.set_material_instance_scalar_parameter_value(instance, 'BrowFollowBlink', 1.0 if opts.get('brow_blink_follow') else 0.0)

    for param_name, key in (
        ('Rect_Eye_L', 'eye_l'), ('Rect_Eye_R', 'eye_r'),
        ('Rect_Pupil_L', 'pupil_l'), ('Rect_Pupil_R', 'pupil_r'),
        ('Rect_Brow_L', 'brow_l'), ('Rect_Brow_R', 'brow_r'),
        ('Rect_Mouth', 'mouth'),
    ):
        rect = spec.get(key) or (0, 0, 0, 0)
        mel.set_material_instance_vector_parameter_value(
            instance, param_name, unreal.LinearColor(*(float(x) for x in rect)),
        )

    sclera_rgba = hex_to_linear_rgba(spec.get('sclera_hex', '#ffffff'), float(spec.get('sclera_alpha', 1.0)))
    mel.set_material_instance_vector_parameter_value(instance, 'ScleraColor', unreal.LinearColor(*sclera_rgba))
    mouth_alpha = float(spec.get('mouth_alpha', 0.0))
    if mouth_alpha > 0.0:
        mouth_rgba = hex_to_linear_rgba(spec.get('mouth_hex', '#5a2220'), mouth_alpha)
        mel.set_material_instance_vector_parameter_value(instance, 'MouthColor', unreal.LinearColor(*mouth_rgba))
    mel.update_material_instance(instance)
    return instance


def create_face3d_material(
    texture, destination: str, spec: dict | None = None, created: list | None = None,
    *, uv_slide_mode: int = 0, face_u_grad=None, face_v_grad=None, options: dict | None = None,
):
    """Create a configured MaterialInstanceConstant from `M_Face3D`.

    - `uv_slide_mode=0`: Bone-invariant analytic slide (for standard 3D mobs, unsplit or split-head).
    - `uv_slide_mode=1`: Geometric `(PosCurr - PosBind)` projection (for Tier-3 custom multi-bone split heads).
    """
    if unreal is None:
        raise RuntimeError('create_face3d_material requires Unreal Editor')
    mel = unreal.MaterialEditingLibrary
    opts = normalize_face_options(options)
    parent = ensure_face3d_material()
    folder, asset_name = destination.rsplit('/', 1)
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew(),
    )
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError('Failed to create Face3D material instance: ' + destination)
    if created is not None:
        created.append(instance)
    mel.set_material_instance_parent(instance, parent)
    _copy_labpbr_defaults(instance)

    mel.set_material_instance_texture_parameter_value(instance, '纹理贴图', texture)
    if mel.get_material_instance_texture_parameter_value(instance, '纹理贴图') != texture:
        raise RuntimeError('Failed to assign Face3D skin texture')

    mel.set_material_instance_scalar_parameter_value(instance, 'UVSlideMode', float(uv_slide_mode))
    cavity_rgba = hex_to_linear_rgba(opts['mouth_cavity_color'], 1.0)
    mel.set_material_instance_vector_parameter_value(instance, 'MouthCavityColor', unreal.LinearColor(*cavity_rgba))
    if spec:
        tw, th = spec['tex_size']
        mel.set_material_instance_scalar_parameter_value(instance, 'TexWidth', float(tw))
        mel.set_material_instance_scalar_parameter_value(instance, 'TexHeight', float(th))
        if spec.get('use_mouth') and spec.get('mouth') and not spec.get('keep_3d_lip_uv'):
            mx0, my0, mx1, my1 = (float(x) for x in spec['mouth'])
            mel.set_material_instance_vector_parameter_value(
                instance, 'Rect_Mouth_UV', unreal.LinearColor(mx0 / tw, my0 / th, mx1 / tw, my1 / th),
            )
    if face_u_grad is not None:
        mel.set_material_instance_vector_parameter_value(
            instance, 'FaceU_Grad', unreal.LinearColor(float(face_u_grad[0]), float(face_u_grad[1]), float(face_u_grad[2]), 0.0),
        )
    if face_v_grad is not None:
        mel.set_material_instance_vector_parameter_value(
            instance, 'FaceV_Grad', unreal.LinearColor(float(face_v_grad[0]), float(face_v_grad[1]), float(face_v_grad[2]), 0.0),
        )
    mel.update_material_instance(instance)
    return instance


# Backwards-compatible aliases
face2d_material_instance = create_face2d_material
face3d_material_instance = create_face3d_material
