from __future__ import annotations


try:
    import unreal
except ModuleNotFoundError:
    unreal = None

from .protocol import (
    FACE3D_CORRECTIVE_MORPHS,
    FACE3D_POST_ABP_PATH,
    FACE3D_SOLVER_CR_PATH,
    FACE3D_SOLVER_VERSION,
    FACE_SOLVER_VERSION_TAG,
)
from .materials import (
    _warn_face,
)


def _find_animgraph_node_entry(ged, context_pins, keywords: tuple[str, ...]) -> str | None:
    """Resolve localized AnimGraph node display path for `create_node_from_name`."""
    candidates = [str(s) for s in ged.list_available_nodes(context_pins)]
    for kw in keywords:
        exact = [c for c in candidates if c.endswith('|' + kw) or c == kw]
        if exact:
            return exact[0]
    for kw in keywords:
        partial = [c for c in candidates if kw in c]
        if partial:
            return partial[0]
    return None


def ensure_face3d_solver_rig(destination: str = FACE3D_SOLVER_CR_PATH, *, rebuild: bool = False):
    """Ensure shared skeleton-agnostic `CR_MineprepFace3DSolver` exists to drive 3D corrective morphs."""
    if unreal is None:
        raise RuntimeError('ensure_face3d_solver_rig requires Unreal Editor')
    lib = unreal.EditorAssetLibrary
    if lib.does_asset_exist(destination) and not rebuild:
        loaded = unreal.load_asset(destination)
        if isinstance(loaded, unreal.ControlRigBlueprint):
            actual = str(lib.get_metadata_tag(loaded, FACE_SOLVER_VERSION_TAG) or '').strip()
            if actual != FACE3D_SOLVER_VERSION:
                _warn_face(
                    f'3D 表情修正绑定 {destination} 版本为 {actual or "未标记"}（当前推荐版本 v{FACE3D_SOLVER_VERSION}）。'
                    '未自动覆盖，如需更新请调用 rebuild=True。'
                )
            return loaded

    folder, _ = destination.rsplit('/', 1)
    lib.make_directory(folder)
    if lib.does_asset_exist(destination):
        cr_bp = unreal.load_asset(destination)
    else:
        cr_bp = unreal.ControlRigBlueprintFactory.create_new_control_rig_asset(destination)
    if not isinstance(cr_bp, unreal.ControlRigBlueprint):
        raise RuntimeError('无法创建 3D 表情修正 ControlRig: ' + destination)

    # Declare ONLY the 6 input + 6 internal output curves (zero bones -> works on EVERY skeleton!)
    hc = cr_bp.get_hierarchy_controller()
    existing_curves = {str(k.name) for k in cr_bp.get_hierarchy().get_curves()}
    for cname in (
        'face_mouth_open', 'face_eye_wide', 'face_blink_l', 'face_blink_r',
        'face_brow_rot_l', 'face_brow_rot_r', *FACE3D_CORRECTIVE_MORPHS,
    ):
        if cname not in existing_curves:
            hc.add_curve(cname, 0.0)

    ctrl = cr_bp.get_controller()
    for node in list(cr_bp.get_default_model().get_nodes()):
        ctrl.remove_node(node)

    v2 = unreal.Vector2D
    begin = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_BeginExecution', 'Execute', v2(0, 0), 'BeginExecution')

    # 1) _mc_mouth_neg_cancel = max(-face_mouth_open, 0.0)
    get_mo = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_GetCurveValue', 'Execute', v2(-260, 140), 'GetMouthOpen')
    ctrl.set_pin_default_value(f'{get_mo.get_name()}.Curve', 'face_mouth_open', False)
    neg_mo = ctrl.add_unit_node_from_struct_path('/Script/RigVM.RigVMFunction_MathFloatNegate', 'Execute', v2(0, 140), 'NegMouthOpen')
    ctrl.add_link(f'{get_mo.get_name()}.Value', f'{neg_mo.get_name()}.Value')
    max_mo = ctrl.add_unit_node_from_struct_path('/Script/RigVM.RigVMFunction_MathFloatMax', 'Execute', v2(220, 140), 'MaxMouthNeg')
    ctrl.set_pin_default_value(f'{max_mo.get_name()}.B', '0.0', False)
    ctrl.add_link(f'{neg_mo.get_name()}.Result', f'{max_mo.get_name()}.A')
    set_mo = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_SetCurveValue', 'Execute', v2(460, 0), 'SetMouthNegCancel')
    ctrl.set_pin_default_value(f'{set_mo.get_name()}.Curve', '_mc_mouth_neg_cancel', False)
    ctrl.add_link(f'{begin.get_name()}.ExecuteContext', f'{set_mo.get_name()}.ExecuteContext')
    ctrl.add_link(f'{max_mo.get_name()}.Result', f'{set_mo.get_name()}.Value')

    # 2) _mc_eye_wide_pos = wide_pos = max(face_eye_wide, 0.0)
    get_w = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_GetCurveValue', 'Execute', v2(-260, 320), 'GetEyeWide')
    ctrl.set_pin_default_value(f'{get_w.get_name()}.Curve', 'face_eye_wide', False)
    max_w = ctrl.add_unit_node_from_struct_path('/Script/RigVM.RigVMFunction_MathFloatMax', 'Execute', v2(0, 320), 'MaxEyeWidePos')
    ctrl.set_pin_default_value(f'{max_w.get_name()}.B', '0.0', False)
    ctrl.add_link(f'{get_w.get_name()}.Value', f'{max_w.get_name()}.A')
    set_wp = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_SetCurveValue', 'Execute', v2(760, 0), 'SetEyeWidePos')
    ctrl.set_pin_default_value(f'{set_wp.get_name()}.Curve', '_mc_eye_wide_pos', False)
    ctrl.add_link(f'{set_mo.get_name()}.ExecuteContext', f'{set_wp.get_name()}.ExecuteContext')
    ctrl.add_link(f'{max_w.get_name()}.Result', f'{set_wp.get_name()}.Value')

    # 3) _mc_blink_wide_l/r = clamp(face_blink_l/r, 0, 1) * wide_pos
    prev_exec = set_wp
    for idx, side in enumerate(('l', 'r')):
        y_off = 480 + idx * 180
        get_b = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_GetCurveValue', 'Execute', v2(-260, y_off), f'GetBlink_{side}')
        ctrl.set_pin_default_value(f'{get_b.get_name()}.Curve', f'face_blink_{side}', False)
        clamp_b = ctrl.add_unit_node_from_struct_path('/Script/RigVM.RigVMFunction_MathFloatClamp', 'Execute', v2(0, y_off), f'ClampBlink_{side}')
        ctrl.set_pin_default_value(f'{clamp_b.get_name()}.Minimum', '0.0', False)
        ctrl.set_pin_default_value(f'{clamp_b.get_name()}.Maximum', '1.0', False)
        ctrl.add_link(f'{get_b.get_name()}.Value', f'{clamp_b.get_name()}.Value')
        mul_bw = ctrl.add_unit_node_from_struct_path('/Script/RigVM.RigVMFunction_MathFloatMul', 'Execute', v2(240, y_off), f'MulBlinkWide_{side}')
        ctrl.add_link(f'{clamp_b.get_name()}.Result', f'{mul_bw.get_name()}.A')
        ctrl.add_link(f'{max_w.get_name()}.Result', f'{mul_bw.get_name()}.B')
        set_bw = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_SetCurveValue', 'Execute', v2(1060 + idx * 280, 0), f'SetBlinkWide_{side}')
        ctrl.set_pin_default_value(f'{set_bw.get_name()}.Curve', f'_mc_blink_wide_{side}', False)
        ctrl.add_link(f'{prev_exec.get_name()}.ExecuteContext', f'{set_bw.get_name()}.ExecuteContext')
        ctrl.add_link(f'{mul_bw.get_name()}.Result', f'{set_bw.get_name()}.Value')
        prev_exec = set_bw

    # 4) _mc_brow_rot_sq_l/r = clamp(face_brow_rot_l/r, -1.2, 1.2)^2 (exact rigid 2D brow rotation pullback)
    for idx, side in enumerate(('l', 'r')):
        y_off = 840 + idx * 180
        get_br = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_GetCurveValue', 'Execute', v2(-260, y_off), f'GetBrowRot_{side}')
        ctrl.set_pin_default_value(f'{get_br.get_name()}.Curve', f'face_brow_rot_{side}', False)
        clamp_br = ctrl.add_unit_node_from_struct_path('/Script/RigVM.RigVMFunction_MathFloatClamp', 'Execute', v2(0, y_off), f'ClampBrowRot_{side}')
        ctrl.set_pin_default_value(f'{clamp_br.get_name()}.Minimum', '-1.2', False)
        ctrl.set_pin_default_value(f'{clamp_br.get_name()}.Maximum', '1.2', False)
        ctrl.add_link(f'{get_br.get_name()}.Value', f'{clamp_br.get_name()}.Value')
        sq_br = ctrl.add_unit_node_from_struct_path('/Script/RigVM.RigVMFunction_MathFloatMul', 'Execute', v2(240, y_off), f'SqBrowRot_{side}')
        ctrl.add_link(f'{clamp_br.get_name()}.Result', f'{sq_br.get_name()}.A')
        ctrl.add_link(f'{clamp_br.get_name()}.Result', f'{sq_br.get_name()}.B')
        set_br = ctrl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_SetCurveValue', 'Execute', v2(1620 + idx * 280, 0), f'SetBrowRotSq_{side}')
        ctrl.set_pin_default_value(f'{set_br.get_name()}.Curve', f'_mc_brow_rot_sq_{side}', False)
        ctrl.add_link(f'{prev_exec.get_name()}.ExecuteContext', f'{set_br.get_name()}.ExecuteContext')
        ctrl.add_link(f'{sq_br.get_name()}.Result', f'{set_br.get_name()}.Value')
        prev_exec = set_br

    cr_bp.recompile_vm()
    lib.set_metadata_tag(cr_bp, FACE_SOLVER_VERSION_TAG, FACE3D_SOLVER_VERSION)
    if not lib.save_loaded_asset(cr_bp):
        raise RuntimeError('保存 3D 表情修正 ControlRig 失败: ' + destination)
    return cr_bp


def ensure_face3d_post_process_abp(
    destination: str = FACE3D_POST_ABP_PATH,
    *,
    solver_path: str = FACE3D_SOLVER_CR_PATH,
    rebuild: bool = False,
):
    """Ensure shared skeleton-agnostic Template AnimBlueprint `ABP_MineprepFace3D` exists."""
    if unreal is None:
        raise RuntimeError('ensure_face3d_post_process_abp requires Unreal Editor')
    lib = unreal.EditorAssetLibrary
    cr_bp = ensure_face3d_solver_rig(solver_path, rebuild=rebuild)

    if lib.does_asset_exist(destination) and not rebuild:
        loaded = unreal.load_asset(destination)
        if isinstance(loaded, unreal.AnimBlueprint):
            actual = str(lib.get_metadata_tag(loaded, FACE_SOLVER_VERSION_TAG) or '').strip()
            if actual != FACE3D_SOLVER_VERSION:
                _warn_face(
                    f'3D 表情后处理动画蓝图 {destination} 版本为 {actual or "未标记"}（当前推荐版本 v{FACE3D_SOLVER_VERSION}）。'
                    '未自动覆盖，如需更新请调用 rebuild=True。'
                )
            return loaded

    folder, asset_name = destination.rsplit('/', 1)
    lib.make_directory(folder)
    if lib.does_asset_exist(destination):
        abp = unreal.load_asset(destination)
    else:
        abf = unreal.AnimBlueprintFactory()
        abf.set_editor_property('template', True)
        abf.set_editor_property('parent_class', unreal.AnimInstance)
        abp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name, folder, unreal.AnimBlueprint, abf)
    if not isinstance(abp, unreal.AnimBlueprint):
        raise RuntimeError('无法创建 3D 表情后处理模板动画蓝图: ' + destination)

    ged = unreal.BlueprintGraphEditor.get_graph_editor_by_name(abp, 'AnimGraph')
    all_nodes = list(ged.list_all_nodes())
    root_node = next((n for n in all_nodes if 'Root' in n.get_class().get_name()), None)
    if root_node is None:
        raise RuntimeError('ABP_MineprepFace3D 缺少 AnimGraph Root 节点')
    extra_nodes = [n for n in all_nodes if n != root_node]
    if extra_nodes:
        ged.remove_nodes(extra_nodes)

    root_in = unreal.BlueprintEditorLibrary.list_input_pins(root_node)
    in_name = _find_animgraph_node_entry(ged, root_in, ('Input Pose', '输入姿势', 'Linked Input Pose'))
    cr_name = _find_animgraph_node_entry(ged, root_in, ('Control Rig', '绑定控制'))
    if not in_name or not cr_name:
        raise RuntimeError(f'无法定位 AnimGraph 节点名: in_pose={in_name!r}, control_rig={cr_name!r}')

    in_pose = ged.create_node_from_name(in_name, unreal.Vector2D(-560, 0), root_in)
    cr_node = ged.create_node_from_name(cr_name, unreal.Vector2D(-280, 0), root_in)
    if not in_pose or not cr_node:
        raise RuntimeError('创建 ABP_MineprepFace3D AnimGraph 节点失败')

    cls_path = cr_bp.get_rig_vm_host_class().get_path_name()
    ns = cr_node.get_editor_property('node').copy()
    ns.import_text(
        f'(ControlRigAssetReference=(BlueprintRigClass="{cls_path}"),'
        f'DefaultControlRigAssetReference=(BlueprintRigClass="{cls_path}"),'
        f'bResetInputPoseToInitial=False,bTransferInputPose=True,bTransferInputCurves=True)'
    )
    cr_node.set_editor_property('node', ns)

    in_out = unreal.BlueprintEditorLibrary.list_output_pins(in_pose)[0]
    cr_ins = unreal.BlueprintEditorLibrary.list_input_pins(cr_node)
    cr_out = unreal.BlueprintEditorLibrary.list_output_pins(cr_node)[0]
    cr_src = next(p for p in cr_ins if str(unreal.BlueprintGraphPinLibrary.get_pin_name(p)) == 'Source')
    if not (unreal.BlueprintGraphPinLibrary.try_create_connection(in_out, cr_src)
            and unreal.BlueprintGraphPinLibrary.try_create_connection(cr_out, root_in[0])):
        raise RuntimeError('连接 ABP_MineprepFace3D AnimGraph 引脚失败')

    unreal.BlueprintEditorLibrary.compile_blueprint(abp)
    errs = ged.list_nodes_with_errors()
    if errs:
        raise RuntimeError('编译 ABP_MineprepFace3D 失败: ' + ', '.join(n.get_name() for n in errs))

    lib.set_metadata_tag(abp, FACE_SOLVER_VERSION_TAG, FACE3D_SOLVER_VERSION)
    if not lib.save_loaded_asset(abp):
        raise RuntimeError('保存 ABP_MineprepFace3D 失败: ' + destination)
    return abp
