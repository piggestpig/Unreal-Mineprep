"""Bounded physical occupancy queries for volume planners and placements.

Callers choose the density field explicitly when planning against base rock.
Output crops never participate; arrays are transient, not a world voxel cache.
"""
import numpy as np
from .data import MAX_COORD, check_cancel, require_int
from .density import DensityContext


class VolumeQuery:
    batch_size = 128
    point_batch_size = 2048  # independent of potentially tall profile batches

    def __init__(self, pack, params, seed, resources, *, field=None):
        if pack.density is None or pack.density.base != 'volume':
            raise ValueError('VolumeQuery requires a volume recipe')
        self.pack, self.params, self.seed, self.resources = pack, params, seed, resources
        self.field = field or pack.density.field
        if self.field not in pack.densities:
            raise ValueError(f'unknown volume density field: {self.field}')

    def _points(self, points, width):
        points = np.asarray(points)
        if (points.ndim != 2 or points.shape[1] != width or points.dtype.kind not in 'iu'
                or np.any(points < -MAX_COORD) or np.any(points > MAX_COORD)):
            raise ValueError(f'volume query needs bounded integer [N,{width}] coordinates')
        return points.astype(np.int64,copy=False)

    def _sample(self, x, y, z):
        check_cancel(getattr(self.resources,'cancel_event',None))
        ctx = DensityContext(self.pack,self.params,self.seed,x,y,z,resources=self.resources)
        values = ctx.get(self.field)
        self.resources.report.peak('volume_query_work_bytes',ctx.work_bytes+values.nbytes)
        return values > 0

    def occupied(self, points):
        check_cancel(getattr(self.resources,'cancel_event',None))
        points = self._points(points,3)
        result = np.empty(len(points),bool)
        for start in range(0,len(points),self.point_batch_size):
            p = points[start:start+self.point_batch_size]
            result[start:start+len(p)] = self._sample(*(p[:,i,None,None] for i in range(3)))[:,0,0]
        result.setflags(write=False)
        return result

    def profiles(self, xz, lower, upper):
        check_cancel(getattr(self.resources,'cancel_event',None))
        xz = self._points(xz,2)
        require_int('profile lower',lower,-MAX_COORD,MAX_COORD)
        require_int('profile upper',upper,lower+1,min(MAX_COORD,lower+4096))
        result = np.empty((upper-lower,len(xz)),bool)
        y = np.arange(lower,upper,dtype=np.int64)[None,:,None]
        for start in range(0,len(xz),self.batch_size):
            p = xz[start:start+self.batch_size]
            result[:,start:start+len(p)] = self._sample(p[:,0][None,None,:],y,p[:,1][None,None,:])[0]
        result.setflags(write=False)
        return result

    @staticmethod
    def air_runs(rock):
        edges = np.diff(np.r_[False,~rock,False].astype(np.int8))
        return tuple(zip(np.flatnonzero(edges == 1),np.flatnonzero(edges == -1)))
