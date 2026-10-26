"""Feature ownership statistics; all content categories and metric names are pack data."""
def summarize(pack, parts, instances, scatter_counts=()):
    by_id = {f.id: dict(instances=0, cells=0, blocks={}) for f in pack.feature_defs}
    for instance in instances:
        by_id[instance.id[0]]['instances'] += 1
    for part in parts:
        for name, block, count in part.block_counts:
            item = by_id[name]
            label = pack.blocks[block]
            item['blocks'][label] = item['blocks'].get(label, 0) + count
            item['cells'] += count
    definitions = {f.id: f for f in pack.feature_defs}
    for name, count in scatter_counts:
        item = by_id[name]
        item['instances'] += count
        item['cells'] += count
        block = definitions[name].block
        item['blocks'][block] = item['blocks'].get(block, 0) + count
    return aggregate(pack,by_id)


def aggregate(pack, by_id):
    categories = {f.id: f.category for f in pack.feature_defs}
    by_category = {}
    for name, item in by_id.items():
        group = by_category.setdefault(categories[name], dict(instances=0, cells=0, blocks={}))
        for k in ('instances', 'cells'):
            group[k] += item[k]
        for block, count in item['blocks'].items():
            group['blocks'][block] = group['blocks'].get(block, 0) + count
    result = dict(feature_counts=by_id, feature_categories=by_category)
    for name, group in by_category.items():
        result[name+'_cells'] = group['cells']
        result[name+'_instances'] = group['instances']
    for name, rule in (pack.feature_metrics or {}).items():
        group = by_category.get(rule['category'], dict(blocks={}))
        result[name] = sum(group['blocks'].get(n, 0) for n in rule['blocks'])
    return result
