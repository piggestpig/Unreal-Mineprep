"""Optional static cave pools; geometry and surface hydrology are untouched."""
from ...core.fluids import basin_candidates, bodies_touch
from ...core.data import Region
from .water_connections import query


def sample(pack,params,seed,region,resources):
    connected=tuple(e.body for e in query(pack,params,seed,region,resources))
    pools=[]
    for body in basin_candidates(pack,params,seed,region,resources):
        runs=body.runs
        if not len(runs):continue
        x0,z0=int(runs[:,0].min())-1,int(runs[:,1].min())-1
        check=Region(x0,z0,int(runs[:,0].max())-x0+2,int(runs[:,1].max())-z0+2)
        if any(bodies_touch(body,e.body) for e in query(pack,params,seed,check,resources)):
            resources.water_connection_pool_conflicts=getattr(resources,'water_connection_pool_conflicts',0)+1
        else:pools.append(body)
    return connected+tuple(pools)
