"""Descriptive independent-trial outcomes; no identical-root or iid claims."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from .diagnostics import require
from .garment_trace_intake import verify_files


def full_fold_record(directory):
    """Keep an upstream point-region judgement separate from SRS success."""
    import numpy as np
    root = Path(directory)
    manifest = verify_files(root)
    record = json.loads((root/'full-fold-recovery.json').read_text(encoding='utf-8'))
    require(record['trial_id'] == manifest['trial_id'], 'cross-trial final record')
    judgment = record['judgment']
    with np.load(root/'final-point-cloud.npz', allow_pickle=False) as data:
        points = data['points']
    require(points.ndim == 2 and points.shape[1] == 3 and len(points)>0
            and np.isfinite(points).all(), 'invalid final points')
    x0,x1,y0,y1 = judgment['boundary_world_xy_m']
    count = int(((points[:,0]>=x0)&(points[:,0]<=x1)&(points[:,1]>=y0)&(points[:,1]<=y1)).sum())
    require(count == judgment['inside_count'] and len(points) == judgment['point_count'], 'judgment count mismatch')
    require((count/len(points)>=judgment['minimum_ratio']) == judgment['upstream_success'], 'judgment mismatch')
    return {'trial_id':record['trial_id'], 'method':'scripted_regrasp', 'block_id':record['injection'],
            'garment':record['garment'], 'label_audit':'pending', 'autonomous_success':None,
            'local_success':None, 'upstream_region_ratio':count/len(points),
            'upstream_success':judgment['upstream_success'], 'online_authorized':False,
            'continuous_history_trial_id':None, 'same_root_comparison_available':False}


def summarize(records):
    require(isinstance(records,list) and bool(records), 'no trial records')
    ids=[r['trial_id'] for r in records]
    require(all(isinstance(k,str) and k for k in ids) and len(ids)==len(set(ids)), 'duplicate/missing trial ID')
    groups=defaultdict(list)
    for r in records:
        require(r.get('autonomous_success') is None or type(r['autonomous_success']) is bool, 'outcome must be bool or null')
        if r.get('autonomous_success') is not None:
            require(r.get('label_audit')=='audited' and bool(r.get('review_reference')), 'unaudited SRS label')
        groups[(r['method'],r['block_id'])].append(r)
    counts=[]
    for (method,block),rows in sorted(groups.items()):
        counts.append({'method':method, 'block_id':block, 'recorded_trials':len(rows),
                       'confirmed_autonomous_successes':sum(r.get('autonomous_success') is True for r in rows),
                       'confirmed_autonomous_failures':sum(r.get('autonomous_success') is False for r in rows),
                       'unknown_autonomous_outcomes':sum(r.get('autonomous_success') is None for r in rows)})
    return {'schema':'independent-trial-description/1', 'groups':counts,
            'pairwise_selection_rate':None, 'causal_effect':None,
            'statistical_independence_confirmed':False, 'research_conclusion':'NOT_ESTABLISHED'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-fold-dirs',nargs='+',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    records=[full_fold_record(p) for p in args.full_fold_dirs]
    result={'records':records, 'summary':summarize(records)}
    with Path(args.output).open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':
    main()
