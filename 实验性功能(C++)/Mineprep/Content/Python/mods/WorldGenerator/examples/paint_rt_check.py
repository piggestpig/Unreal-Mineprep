"""User-run UE checks. No scene writes; only generated paint masters and transient RTs.

In the UE Python console:
    import runpy
    paint_check = runpy.run_path(r'E:/ue/Mineprep_5_8/Plugins/Mineprep/Content/Python/mods/WorldGenerator/examples/paint_rt_check.py')
    paint_runner = paint_check['check']()
Later inspect paint_runner.done, paint_runner.error, paint_runner.result.
Optional CPU submission probes: paint_check['measure'](512), then (2048).
Categorical probe: paint_check['measure'](512, kind='biome_map').
"""
import time
import numpy as np
import unreal as ue
import mineprep
from mods.WorldGenerator.core.data import Region
from mods.WorldGenerator.painting import Canvas, Brush
from mods.WorldGenerator.paint_render import PaintRender
from mods.WorldGenerator.biome_paint import BiomeCanvas
from mods.WorldGenerator import api
from mods.WorldGenerator.paint_panel import PaintPanel


def _read(renderer, target):
    # UE's raw readback helper excludes RG32F. Copy RG unchanged to RGBA32F.
    h,w = renderer.shape
    renderer._draw(renderer.texture,target,(0,0,w,h),4,Brush(0,1,1))
    colors = ue.RenderingLibrary.read_render_target_raw(renderer.world,target,normalize=False)
    if colors is None or len(colors)!=h*w:
        raise RuntimeError('RGBA32F validation readback failed')
    return np.array([(v.r,v.g) for v in colors],np.float32).reshape(h,w,2)


@mineprep.asynctask
def check():
    renderer = PaintRender(mineprep.world())
    target = ue.RenderingLibrary.create_render_target2d(renderer.world,48,32,
        ue.TextureRenderTargetFormat.RTF_RGBA32F,ue.LinearColor(0,0,0,0))
    reports = []

    def verify(label, doc):
        state = _read(renderer,target)
        brush = renderer.brush
        alpha = state[...,1]*brush.strength
        actual = (np.where(state[...,1]>.5,brush.value,state[...,0]) if doc.categorical
                  else state[...,0]*(1-alpha)+brush.value*alpha)
        error = float(np.max(np.abs(actual-doc.values)))
        np.testing.assert_allclose(actual,doc.values,rtol=3e-6,atol=3e-5,err_msg=label)
        if doc.categorical:
            np.testing.assert_array_equal(actual,doc.values,err_msg=label)
        # Check base/mask too: a matching display alone can hide stale coverage.
        np.testing.assert_allclose(state,doc.preview_state(),rtol=3e-6,atol=3e-5,err_msg=label)
        reports.append(dict(stage=label,max_error=error,uploads=renderer.uploads))

    try:
        values = np.arange(32*48,dtype=np.float32).reshape(32,48)/1000
        values[0,0],values[-1,-1] = 70000.125,-12.25
        doc = Canvas('heightmap',Region(-31,7,96,32),values)
        renderer.flush(doc)
        identities = tuple(v.get_path_name() for v in renderer.targets)
        yield
        verify('initial float32, negative and non-square pixels',doc)
        submit = PaintPanel()
        submit._paint_renderer = renderer
        doc.begin((-15,14),Brush(-18,13.5,.35,.6))
        submit._paint_flush(doc)
        passes = renderer.passes
        doc.stroke.segment((-15,14),(48,27))
        submit._paint_flush(doc)
        assert renderer.passes > passes, 'a second dirty submission was time-throttled'
        passes = renderer.passes
        submit._paint_flush(doc)
        assert renderer.passes == passes, 'clean input submitted another pass'
        yield
        verify('soft negative stroke',doc)
        before = doc.values.copy()
        doc.stroke.segment((-15,14),(48,27))
        doc.finish()
        renderer.flush(doc)
        yield
        np.testing.assert_array_equal(before,doc.values)
        verify('overlap and commit',doc)
        # Queue two different brushes before a flush, including distant dirty boxes.
        doc.begin((-27,35),Brush(24,5,1,.4));doc.finish()
        doc.begin((60,9),Brush(-4,3,1,1));doc.cancel()
        renderer.flush(doc)
        yield
        verify('ordered brushes, hard edge, distant cancel',doc)
        doc.begin((48,27),Brush(0,11,.2,.8));renderer.flush(doc)
        yield
        verify('erase toward zero',doc)
        doc.cancel();renderer.flush(doc)
        yield
        verify('cancel active coverage',doc)
        assert renderer.uploads==2, 'ordinary strokes reimported textures'
        doc.history();renderer.flush(doc)
        yield
        verify('undo resynchronization',doc)
        doc.history(True);renderer.flush(doc)
        yield
        verify('redo resynchronization',doc)
        for kind,value in (('vegetation',0.),('clearance',1.)):
            doc = Canvas(kind,doc.region,np.full((32,48),1-value,np.float32))
            renderer.flush(doc)
            doc.begin((-10,18),Brush(value,8,.5,.65))
            renderer.flush(doc)
            yield
            verify(kind+' layer switch and soft brush',doc)
            doc.finish();renderer.flush(doc)
            yield
            verify(kind+' commit',doc)
        doc = BiomeCanvas(api.pack(),doc.region,np.zeros((32,48),np.int32))
        renderer.flush(doc)
        yield
        verify('categorical initialization',doc)
        uploads = renderer.uploads
        doc.begin((-12,18),Brush(doc.target('forest'),12,.2,.3))
        doc.stroke.segment((-12,18),(30,24));renderer.flush(doc)
        yield
        verify('categorical active hard coverage',doc)
        doc.finish();renderer.flush(doc)
        yield
        verify('categorical commit',doc)
        doc.begin((20,24),Brush(doc.target('desert'),9));doc.finish()
        doc.begin((-12,18),Brush(0,7));doc.finish()
        doc.begin((45,24),Brush(doc.target('forest'),11));doc.cancel()
        renderer.flush(doc)
        yield
        verify('categorical switch, erase and cancel',doc)
        assert renderer.uploads==uploads, 'categorical strokes reimported textures'
        for redo in (False,True):
            doc.history(redo);renderer.flush(doc)
            yield
            verify('categorical redo' if redo else 'categorical undo',doc)
        assert identities==tuple(v.get_path_name() for v in renderer.targets), 'same-size RTs were replaced'
        ue.log('Paint RT checks passed: '+str(reports))
        return reports
    finally:
        renderer.close()
        ue.RenderingLibrary.release_render_target2d(target)


@mineprep.asynctask
def measure(size=512, kind='heightmap'):
    """One local segment submission per frame; no GPU readback or terrain generation."""
    if size not in (512,2048):raise ValueError('Use 512 or 2048')
    if kind not in ('heightmap','biome_map'):raise ValueError('Use heightmap or biome_map')
    renderer = PaintRender(mineprep.world())
    try:
        region = Region(0,0,size,size)
        doc = BiomeCanvas(api.pack(),region) if kind=='biome_map' else Canvas('heightmap',region)
        renderer.flush(doc)
        identities = tuple(v.get_path_name() for v in renderer.targets)
        yield
        uploads,passes,pixels = renderer.uploads,renderer.passes,renderer.submitted_pixels
        costs = []
        for i in range(24):
            x,z = 32+i*5,48+i*3
            value = doc.target('forest' if i%2==0 else 'desert') if doc.categorical else 16 if i%2==0 else -8
            doc.begin((x,z),Brush(value,32,.5,.7))
            doc.stroke.segment((x,z),(x+8,z+4));doc.finish()
            started = time.perf_counter()
            renderer.flush(doc)
            costs.append((time.perf_counter()-started)*1000)
            yield
        assert renderer.uploads==uploads, 'ordinary strokes reimported textures'
        assert identities==tuple(v.get_path_name() for v in renderer.targets)
        report = dict(size=size,kind=kind,strokes=24,stroke_imports=renderer.uploads-uploads,
            targets=len(renderer.targets),dynamic_materials=2,rt_MiB=2*size*size*8/1024**2,
            passes=renderer.passes-passes,submitted_pixels=renderer.submitted_pixels-pixels,
            cpu_submit_median_ms=float(np.median(costs)),cpu_submit_max_ms=max(costs))
        ue.log('Paint RT CPU submission (not GPU time): '+str(report))
        return report
    finally:
        renderer.close()
