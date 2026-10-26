"""Finite immutable model recipes and sparse column occupancy; no Unreal objects."""
from dataclasses import dataclass, field
from hashlib import sha256
import numpy as np
from .features import FeatureBatch


def rotate(points, turns):
    p = np.asarray(points).copy()
    for _ in range(int(turns)):
        p[:, [0, 2]] = p[:, [2, 0]] * (-1, 1)  # positive UE yaw, MC X/Y/Z
    return p


def tree_template(id, trunk, foliage, *, trunk_block, foliage_block, block_ids,
                  block_defs, snow_layer=0):
    """Build a native-model tree recipe without terrain, climate or editor access.

    Integer local MC XYZ cells are deduplicated in input order; trunk wins
    overlaps. snow_layer is 0 (no snow) or 1..8 eighth-block layers. The pack
    declares snow_layer_N with its matching native model and unit transform.
    No climate or cold parameters are read.
    JSON/mesh or transformed wood/leaves require the ordinary FeatureBatch path.
    """
    def points(raw, role):
        p = np.asarray(raw)
        if p.shape == (0,):
            p = np.empty((0, 3), np.int32)
        if p.ndim != 2 or p.shape[1:] != (3,) or p.dtype.kind not in 'iu':
            raise ValueError(f'tree template {id}: {role} needs integer XYZ cells')
        # Leave room for a snow cell and its half-open box, including rotation.
        if p.size and (p.min() <= -np.iinfo(np.int32).max + 2 or p.max() >= np.iinfo(np.int32).max - 2):
            raise ValueError(f'tree template {id}: {role} exceeds local coordinate bounds')
        _, first = np.unique(p, axis=0, return_index=True)
        return p[np.sort(first)].astype(np.int32)

    if type(snow_layer) is not int or not 0 <= snow_layer <= 8:
        raise ValueError(f'tree template {id}: snow_layer must be an integer in [0, 8]')

    def material(name):
        if not isinstance(name, str) or name not in block_ids or name not in block_defs:
            raise ValueError(f'tree template {id}: undeclared block {name!r}')
        d = block_defs[name]
        if (d.source != 'builtin' or d.shape != 'cube' or d.scale != (1., 1., 1.)
                or d.offset != (0., 0., 0.)):
            raise ValueError(f'tree template {id}: unsupported source/transform for {name!r}; use FeatureBatch')
        value = block_ids[name]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or not 0 <= value <= 65535:
            raise ValueError(f'tree template {id}: invalid block ID for {name!r}')
        return value, d.value

    wood = points(trunk, 'trunk')
    leaves = points(foliage, 'foliage')
    if not len(wood):
        raise ValueError(f'tree template {id}: trunk must not be empty')
    # Stable set difference; leaves intersecting the trunk are not emitted twice.
    combined = np.concatenate((wood, leaves))
    _, first = np.unique(combined, axis=0, return_index=True)
    leaves = combined[np.sort(first[first >= len(wood)])]
    wood_id, wood_model = material(trunk_block)
    leaf_id, leaf_model = material(foliage_block)
    offsets = np.concatenate((wood, leaves))
    types = np.r_[np.full(len(wood), wood_id, np.uint16), np.full(len(leaves), leaf_id, np.uint16)]
    cells = [(*map(int, p), model, ()) for group, model in ((wood, wood_model), (leaves, leaf_model)) for p in group]
    canopy = leaves
    if snow_layer:
        snow_name = f'snow_layer_{snow_layer}'
        snow_id, snow_model = material(snow_name)
        expected = 'snow_block' if snow_layer == 8 else f'snow_height{2*snow_layer}'
        if snow_model != expected or block_defs[snow_name].occludes:
            raise ValueError(f'tree template {id}: {snow_name} needs non-occluding builtin {expected}')
        order = np.lexsort((offsets[:, 1], offsets[:, 2], offsets[:, 0]))
        sorted_points = offsets[order]
        ends = np.r_[np.flatnonzero(np.any(sorted_points[1:, [0, 2]] != sorted_points[:-1, [0, 2]], axis=1)), len(offsets)-1]
        roofs = order[ends]
        snow = offsets[roofs[roofs >= len(wood)]].copy()
        snow[:, 1] += 1
        offsets = np.concatenate((offsets, snow))
        types = np.r_[types, np.full(len(snow), snow_id, np.uint16)]
        cells.extend((*map(int, p), 'snow', (('layers', str(snow_layer)),)) for p in snow)
        canopy = np.concatenate((leaves, snow))
    boxes = [[wood.min(axis=0), wood.max(axis=0)+1]]
    if len(canopy):
        mid = (int(canopy[:, 1].min()) + int(canopy[:, 1].max()) + 1) // 2
        for part in (canopy[canopy[:, 1] < mid], canopy[canopy[:, 1] >= mid]):
            if len(part):
                boxes.append([part.min(axis=0), part.max(axis=0)+1])
    return TemplateDefinition(id, offsets, types, np.asarray(boxes, np.int32), tuple(cells), scale_jitter=True)


@dataclass(frozen=True)
class TemplateDefinition:
    id: str
    offsets: np.ndarray
    types: np.ndarray
    boxes: np.ndarray                 # half-open local [K,2,3], conservative clearance
    bake_cells: tuple                 # (X,Y,Z, model name, tuple of property pairs)
    two_sided: bool = True            # material policy, independent of face culling
    scale_jitter: bool = False        # render-only uniform micro-shrink for overlapping trees
    cellwise: bool = False            # split into shared native cell models after placement
    orientations: tuple = field(init=False, repr=False, compare=False)
    tops: tuple = field(init=False, repr=False, compare=False)
    surface_tops: tuple = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if any(type(v) is not bool for v in (self.two_sided,self.scale_jitter,self.cellwise)):
            raise ValueError('template: two_sided, scale_jitter and cellwise must be bool')
        p, t, b = (np.array(a, copy=True) for a in (self.offsets, self.types, self.boxes))
        if (not isinstance(self.id,str) or not self.id.isidentifier() or p.ndim!=2 or p.shape[1:]!=(3,)
                or not len(p) or t.shape!=(len(p),) or b.ndim!=3 or b.shape[1:]!=(2,3)
                or not 1<=len(b)<=8 or any(a.dtype.kind not in 'iu' for a in (p,t,b))
                or np.any(b[:,0]>=b[:,1])):
            raise ValueError('template: invalid cells, types or clearance boxes')
        if not isinstance(self.bake_cells,tuple) or len(self.bake_cells)!=len(p):
            raise ValueError('template: bake cells must be an immutable tuple matching logical cells')
        if len({tuple(v) for v in p})!=len(p): raise ValueError('template: duplicate cells')
        if not np.all(np.any(np.all((p[:,None]>=b[None,:,0])&(p[:,None]<b[None,:,1]),axis=2),axis=1)):
            raise ValueError('template: cells exceed clearance boxes')
        for point,record in zip(p,self.bake_cells):
            if (not isinstance(record,tuple) or len(record)!=5 or tuple(record[:3])!=tuple(point) or not isinstance(record[3],str)
                    or not record[3] or not isinstance(record[4],tuple)
                    or any(len(pair)!=2 or not all(isinstance(v,str) for v in pair) for pair in record[4])):
                raise ValueError('template: invalid bake cell record')
        orientations=[];tops=[];surface_tops=[]
        for turn in range(4):
            q=rotate(p,turn)
            order=np.lexsort((q[:,1],q[:,2],q[:,0])); s=q[order]
            adjacent=np.all(s[1:, [0,2]]==s[:-1,[0,2]],axis=1)&(s[1:,1]==s[:-1,1]+1)
            starts=np.r_[0,np.flatnonzero(~adjacent)+1];ends=np.r_[starts[1:]-1,len(s)-1]
            xz=s[starts][:,[0,2]];lo=s[starts,1];hi=s[ends,1]+1
            faces,face_types = s[ends].copy(),t[order[ends]].copy()
            faces.setflags(write=False);face_types.setflags(write=False)
            surface_tops.append((faces,face_types))
            # Cell extrema transform half-open boxes correctly around the cell centre.
            corners=np.array([[x,y,z] for box in b for x in (box[0,0],box[1,0]-1)
                              for y in (box[0,1],box[1,1]-1) for z in (box[0,2],box[1,2]-1)])
            corners=rotate(corners,turn).reshape(len(b),8,3)
            boxes=np.stack((corners.min(axis=1),corners.max(axis=1)+1),axis=1)
            ends=np.r_[np.flatnonzero(np.any(s[1:,[0,2]]!=s[:-1,[0,2]],axis=1)),len(s)-1]
            roof=s[ends];materials=t[order[ends]]
            for a in (roof,materials):a.setflags(write=False)
            tops.append((roof,materials))
            for a in (q,xz,lo,hi,boxes):a.setflags(write=False)
            orientations.append((q,xz,lo,hi,boxes))
        for a in (p,t,b):a.setflags(write=False)
        object.__setattr__(self,'offsets',p);object.__setattr__(self,'types',t);object.__setattr__(self,'boxes',b)
        object.__setattr__(self,'orientations',tuple(orientations))
        object.__setattr__(self,'tops',tuple(tops))
        object.__setattr__(self,'surface_tops',tuple(surface_tops))

    @property
    def array_bytes(self):
        return (sum(a.nbytes for a in (self.offsets,self.types,self.boxes))
                +sum(a.nbytes for row in (*self.orientations,*self.tops,*self.surface_tops) for a in row))


def definitions(instances):
    """A recipe ID is unique throughout a World, including different feature generators."""
    result={};seen=set()
    for m in instances:
        t=m.template
        if id(t) in seen:continue
        seen.add(id(t));old=result.get(t.id)
        if old is not None and (old.two_sided!=t.two_sided or old.scale_jitter!=t.scale_jitter or old.cellwise!=t.cellwise or old.bake_cells!=t.bake_cells or any(
                not np.array_equal(a,b) for a,b in ((old.offsets,t.offsets),(old.types,t.types),(old.boxes,t.boxes)))):
            raise ValueError(f'template {t.id}: conflicting recipes')
        result[t.id]=t
    return result


@dataclass(frozen=True)
class TemplateBatch:
    templates: tuple
    template_ids: np.ndarray
    owners: np.ndarray
    rotations: np.ndarray             # four positive yaw quarter turns, 0..3


@dataclass(frozen=True)
class TemplateInstance:
    id: tuple
    anchor: tuple
    bounds: tuple
    block_count: int
    template: TemplateDefinition
    rotation: int


def output_models(instances, region):
    """Keep whole-object placement decisions, then reuse one native mesh per cell state."""
    result, library = [], {}
    for instance in instances:
        model = instance.template
        if not model.cellwise:
            result.append(instance)
            continue
        points = model.orientations[instance.rotation][0] + instance.anchor
        for point,kind,record in zip(points,model.types,model.bake_cells):
            x,y,z = map(int,point)
            if not (region.x0 <= x < region.x0+region.width and region.z0 <= z < region.z0+region.depth):
                continue
            key = (record[3],record[4],int(kind),model.two_sided)
            if key not in library:
                ident = 'cell_'+sha256(repr(key).encode()).hexdigest()[:16]
                library[key] = TemplateDefinition(ident,np.zeros((1,3),np.int32),
                    np.array([kind],np.uint16),np.array([[[0,0,0],[1,1,1]]],np.int32),
                    ((0,0,0,record[3],record[4]),),two_sided=model.two_sided)
            anchor = (x,y,z)
            ident = instance.id + record[:3]
            result.append(TemplateInstance(ident,anchor,(anchor,(x+1,y+1,z+1)),
                                           1,library[key],instance.rotation))
    return tuple(result)


def validate(batch, feature, count, block_ids, validated=None):
    ids, owners, rotations=batch.template_ids,batch.owners,batch.rotations
    if (not batch.templates or any(not isinstance(t,TemplateDefinition) for t in batch.templates)
            or any(not isinstance(a,np.ndarray) or a.ndim!=1 or a.dtype.kind not in 'iu' for a in (ids,owners,rotations))
            or ids.shape!=owners.shape or ids.shape!=rotations.shape
            or np.any(ids<0) or np.any(ids>=len(batch.templates)) or np.any(owners<0) or np.any(owners>=count)
            or len(np.unique(owners))!=len(owners) or np.any(rotations<0) or np.any(rotations>3)
            or len({t.id for t in batch.templates})!=len(batch.templates)):
        raise ValueError(f'feature {feature.id}: invalid TemplateBatch')
    from .multi_features import validate_batch
    for t in batch.templates:
        key=feature.id,id(t)
        if validated is not None and key in validated: continue
        validate_batch(FeatureBatch(t.offsets,t.types,np.zeros(len(t.offsets),np.int32)),feature,1,block_ids)
        if np.any(t.boxes[:,0]<feature.bounds[0]) or np.any(t.boxes[:,1]>feature.bounds[1]):
            raise ValueError(f'feature {feature.id}: template boxes exceed bounds')
        # Rotation is an actual geometry change, not just a render transform.
        for p,_,_,_,boxes in t.orientations:
            if (np.any(p<feature.bounds[0]) or np.any(p>=feature.bounds[1])
                    or np.any(boxes[:,0]<feature.bounds[0]) or np.any(boxes[:,1]>feature.bounds[1])):
                raise ValueError(f'feature {feature.id}: rotated template exceeds bounds')
        if validated is not None: validated.add(key)


def clearance(batch, roots):
    """Only horizontal projections of a few boxes, not all model cells."""
    lows, highs, owners=[],[],[]
    for template_id,turn in sorted(set(zip(batch.template_ids.tolist(),batch.rotations.tolist()))):
        selected=np.flatnonzero((batch.template_ids==template_id)&(batch.rotations==turn))
        root_owners=batch.owners[selected].astype(np.intp)
        boxes=batch.templates[template_id].orientations[turn][4]
        for lower,upper in boxes:
            x,z=np.meshgrid(np.arange(lower[0],upper[0]),np.arange(lower[2],upper[2]))
            local=np.column_stack((x.ravel(),np.full(x.size,lower[1]),z.ravel()))
            lows.append((roots[root_owners,None,:]+local[None,:,:]).reshape(-1,3))
            highs.append(np.repeat(roots[root_owners,1]+upper[1]-1,len(local)))
            owners.append(np.repeat(root_owners,len(local)))
    return np.concatenate(lows),np.concatenate(highs),np.concatenate(owners)


class ModelIndex:
    """Actual cell intervals, instantiated once for occupancy and open-sky queries."""
    def __init__(self, instances, y_min, y_max):
        self.instances=instances;self.y_min=y_min;self.span=y_max-y_min
        parts=[]
        for instance in instances:
            _,xz,lo,hi,_=instance.template.orientations[instance.rotation]
            root=np.asarray(instance.anchor)
            parts.append((xz+root[[0,2]],lo+root[1],hi+root[1]))
        if not parts:
            self.xz=np.empty((0,2),np.int64);self.lower=self.upper=self.keys=self.columns=np.empty(0,np.int64)
            self.minimum=self.maximum=np.zeros(2,np.int64);self.width=1
            return
        self.xz,self.lower,self.upper=(np.concatenate([p[i] for p in parts]) for i in range(3))
        self.minimum=self.xz.min(axis=0);self.maximum=self.xz.max(axis=0)
        self.width=int(self.maximum[1]-self.minimum[1]+1)
        col=self._columns(self.xz)
        keys=col*self.span+self.lower-y_min
        order=np.argsort(keys,kind='stable')
        self.keys,self.columns,self.xz,self.lower,self.upper=(a[order] for a in (keys,col,self.xz,self.lower,self.upper))
        # Nearby crowns may share cells. Merge intersecting intervals so a
        # short nested interval cannot hide the upper tail of a longer one.
        ends=np.maximum.accumulate(self.columns*self.span+self.upper-y_min)
        if np.any((self.columns[1:]==self.columns[:-1]) & (self.keys[1:]<ends[:-1])):
            starts=np.r_[0,np.flatnonzero((self.columns[1:]!=self.columns[:-1]) | (self.keys[1:]>ends[:-1]))+1]
            last=np.r_[starts[1:]-1,len(self.keys)-1]
            self.keys,self.columns,self.xz,self.lower=(a[starts] for a in (self.keys,self.columns,self.xz,self.lower))
            self.upper=ends[last]-self.columns*self.span+y_min
        for a in (self.keys,self.columns,self.xz,self.lower,self.upper):a.setflags(write=False)

    def _columns(self,xz):
        p=xz-self.minimum
        return p[:,0]*self.width+p[:,1]

    @property
    def array_bytes(self):
        return sum(a.nbytes for a in (self.keys,self.columns,self.xz,self.lower,self.upper))

    def occupied(self,points):
        points=np.asarray(points);found=np.zeros(len(points),bool)
        if not len(self.keys): return found
        inside=np.flatnonzero(np.all((points[:,[0,2]]>=self.minimum)&(points[:,[0,2]]<=self.maximum),axis=1)
                              &(points[:,1]>=self.y_min)&(points[:,1]<self.y_min+self.span))
        q=points[inside];col=self._columns(q[:,[0,2]])
        at=np.searchsorted(self.keys,col*self.span+q[:,1]-self.y_min,side='right')-1
        use=at>=0;use[use]&=(self.columns[at[use]]==col[use])&(q[use,1]<self.upper[at[use]])
        found[inside[use]]=True
        return found

    def add_tops(self,top,region):
        x,z=self.xz[:,0]-region.x0,self.xz[:,1]-region.z0
        use=(x>=0)&(x<region.width)&(z>=0)&(z<region.depth)
        np.maximum.at(top,z[use]*region.width+x[use],self.upper[use]-1)


def append_output(data,instances,definitions):
    """Append one nonmergeable record per complete model after cell merging."""
    from dataclasses import replace
    from mc_math import encode_rotation
    used=sorted({i.template.id for i in instances});names=data.names+tuple('template_'+n for n in used)
    types={n:len(data.names)+j for j,n in enumerate(used)}
    xyz=np.array([i.anchor for i in instances],np.int32);xyz[:,0]-=data.region.x0;xyz[:,2]-=data.region.z0
    rotations=np.r_[np.zeros(data.count,np.uint8) if data.rotations is None else data.rotations,
                    [encode_rotation(0,i.rotation*90,0) for i in instances]].astype(np.uint8)
    sizes=None if data.sizes is None else np.r_[data.sizes,np.ones_like(xyz)]
    offsets=None if data.instance_y_offsets is None else np.r_[data.instance_y_offsets,np.zeros(len(xyz))]
    result=replace(data,xyz=np.r_[data.xyz,xyz],types=np.r_[data.types,[types[i.template.id] for i in instances]].astype(np.uint32),
        names=names,block_defs=data.block_defs+tuple(definitions[n] for n in used),sizes=sizes,
        rotations=rotations,instance_y_offsets=offsets,y_offsets=(data.y_offsets or (0.,)*len(data.names))+(0.,)*len(used),
        scale_jitter_types=data.scale_jitter_types+tuple(sorted({types[i.template.id] for i in instances if i.template.scale_jitter})),
        visible_count=(data.visible_count if data.visible_count is not None else data.count)+len(xyz))
    for a in (result.xyz,result.types,sizes,rotations,offsets):
        if a is not None:a.setflags(write=False)
    return result
