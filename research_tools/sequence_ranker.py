"""Experimental history-conditioned ranker; raw logits never authorize motion.

Supports software forward checks on dispatch inputs. Supervised training requires
separate, reviewed recovery-decision samples; trial outcomes cannot be broadcast
over every articulation command. No model novelty or performance is established.
"""
import argparse
import json
from pathlib import Path

from .diagnostics import require
from .recovery_candidates import encode_macro
from .runtime_intake import clock, ordered


def tensors(features):
    import torch
    require(bool(features), "no features")
    keys=("current_observation", "candidate_target", "past_observations", "executed_history")
    batch={key:torch.tensor([r[key] for r in features],dtype=torch.float32) for key in keys}
    for key in ("observation_history_mask", "action_history_mask"):
        require(all(isinstance(r[key],list) and r[key] and all(type(v) is bool for v in r[key])
                    for r in features), "history masks must be bool lists")
        batch[key]=torch.tensor([r[key] for r in features],dtype=torch.bool)
    for value in batch.values():
        require(bool(torch.isfinite(value).all()), "nonfinite feature")
    for vector,mask in (("past_observations","observation_history_mask"),
                        ("executed_history","action_history_mask")):
        n,h=batch[mask].shape
        require(batch[vector].shape[1]%h==0, "history shape mismatch")
        batch[vector]=batch[vector].reshape(n,h,-1)
    return batch


def build_model(config):
    import torch
    from torch import nn

    class Ranker(nn.Module):
        def __init__(self):
            super().__init__()
            h=config['hidden']
            self.obs=nn.GRUCell(config['observation_history_dim'],h) if config['observation_history_steps'] else None
            self.action=nn.GRUCell(config['action_history_dim'],h) if config['action_history_steps'] else None
            extra=h*(int(self.obs is not None)+int(self.action is not None))
            self.head=nn.Sequential(nn.Linear(config['current_dim']+config['candidate_dim']+extra,h),
                                    nn.ReLU(),nn.Linear(h,1))

        def recurrent(self,cell,values,mask):
            state=values.new_zeros((len(values),config['hidden']))
            for i in range(values.shape[1]):
                # Mask before computing as well as before updating state.
                x=torch.where(mask[:,i,None],values[:,i],torch.zeros_like(values[:,i]))
                proposal=cell(x,state)
                state=torch.where(mask[:,i,None],proposal,state)
            return state

        def forward(self,batch):
            parts=[batch['current_observation'],batch['candidate_target']]
            if self.obs is not None:
                steps=config['observation_history_steps']
                parts.append(self.recurrent(self.obs,batch['past_observations'][:,-steps:],
                                            batch['observation_history_mask'][:,-steps:]))
            if self.action is not None:
                steps=config['action_history_steps']
                parts.append(self.recurrent(self.action,batch['executed_history'][:,-steps:],
                                            batch['action_history_mask'][:,-steps:]))
            return self.head(torch.cat(parts,dim=1)).flatten()

    return Ranker()


def configuration(batch,hidden=32,use_history=True,observation_steps=None,action_steps=None):
    require(type(hidden) is int and hidden>0, 'hidden must be positive')
    obs=batch['past_observations'].shape[1] if observation_steps is None and use_history else (observation_steps or 0)
    actions=batch['executed_history'].shape[1] if action_steps is None and use_history else (action_steps or 0)
    require(type(obs) is int and 0<=obs<=batch['past_observations'].shape[1], 'observation history window unavailable')
    require(type(actions) is int and 0<=actions<=batch['executed_history'].shape[1], 'action history window unavailable')
    return dict(current_dim=batch['current_observation'].shape[-1],candidate_dim=batch['candidate_target'].shape[-1],
                observation_history_dim=batch['past_observations'].shape[-1],
                action_history_dim=batch['executed_history'].shape[-1],hidden=hidden,use_history=bool(obs or actions),
                observation_history_steps=obs,action_history_steps=actions)


def parameter_count(config):
    h=config['hidden']
    extra=0;recurrent=0
    for key,dimension in (('observation_history_steps','observation_history_dim'),('action_history_steps','action_history_dim')):
        if config[key]:
            recurrent+=3*h*config[dimension]+3*h*h+6*h
            extra+=h
    return recurrent+(config['current_dim']+config['candidate_dim']+extra+2)*h+1


def ablation_configurations(batch,hidden=32):
    """Temporal/capacity controls, not reproductions of SADP or other papers."""
    full=configuration(batch,hidden,True,4,4)
    target=parameter_count(full)
    base=batch['current_observation'].shape[-1]+batch['candidate_target'].shape[-1]+2
    near=max(1,int((target-1)/base))
    width=min((near,near+1),key=lambda n:abs(base*n+1-target))
    return {'current':configuration(batch,hidden,False),
            'observation-total3':configuration(batch,hidden,True,2,0),
            'observation-total5':configuration(batch,hidden,True,4,0),
            'observation-action-total5':full,
            'current-capacity-match':configuration(batch,width,False)}


def validate_training_rows(rows, require_coverage=True, allow_unassigned=False):
    require(isinstance(rows,list) and bool(rows),'no recovery samples')
    splits={}
    identities=set()
    profiles=set()
    contexts=set()
    encodings=set()
    for row in rows:
        require(row.get('schema')=='reviewed-recovery-sample/1'
                and row.get('decision_scope')=='recovery_macro',
                'training requires reviewed recovery decisions, not articulation dispatches')
        allowed=('train','development','unassigned') if allow_unassigned else ('train','development')
        require(row.get('split') in allowed, 'only train/development allowed; sealed test forbidden')
        require(type(row.get('continuation_success')) is bool and row.get('label_review_reference'),
                'reviewed continuation labels required; unknown cannot become negative')
        require(row.get('target_definition')=='fixed-controller-continuation/v1', 'unfrozen supervision target')
        require(bool(row.get('continuation_context_reference')), 'controller/goal/budget context required')
        contexts.add(row['continuation_context_reference'])
        require(row.get('candidate_spec_reference') and row.get('candidate_available_before_decision') is True,
                'predecision recovery candidate specification required')
        require(isinstance(row.get('trial_id'),str) and row['trial_id'], 'missing trial identity')
        family=row.get('lineage_group')
        require(isinstance(family,str) and family, 'missing trajectory/branch lineage group')
        for key in ('trial:'+row['trial_id'],'family:'+family):
            require(splits.setdefault(key,row['split'])==row['split'], 'trial/family split leakage')
        ident=(row['trial_id'],row.get('decision_id'),row.get('candidate_id'))
        require(all(isinstance(x,str) and x for x in ident) and ident not in identities, 'duplicate/missing decision identity')
        identities.add(ident)
        feature=row['features']
        require(feature.get('continuation_context_reference')==row['continuation_context_reference'],
                'feature/training context mismatch')
        require(isinstance(row.get('encoding_reference'),str) and row['encoding_reference']
                and feature.get('encoding_reference')==row['encoding_reference'], 'feature encoding reference mismatch')
        encodings.add(row['encoding_reference'])
        require(feature.get('trial_id')==row['trial_id'], 'cross-trial supervision')
        require(feature.get('input_scope')=='recovery_macro_decision',
                'a whole recovery proposal must replace the articulation target before training')
        proposal=feature.get('recovery_macro_candidate_spec',{})
        require(encode_macro(proposal)==feature['candidate_target']
                and proposal['trial_id']==row['trial_id'] and proposal['candidate_id']==row['candidate_id'],
                'recovery proposal encoding/identity mismatch')
        require(ordered(clock(proposal['available_at']),clock(feature['as_of'])), 'future recovery proposal')
        require(feature.get('local_success') is None and feature.get('autonomous_success') is None,
                'outcome must remain outside features')
        profiles.add(feature.get('profile_id'))
    require(len(profiles)==1 and None not in profiles, 'inconsistent joint profile')
    require(len(contexts)==1, 'this prototype requires a fixed controller/goal/budget context')
    require(len(encodings)==1, 'inconsistent feature encodings')
    train=[r for r in rows if r['split']=='train']
    dev=[r for r in rows if r['split']=='development']
    if require_coverage:
        require(bool(dev) and {r['continuation_success'] for r in train}=={False,True},
                'need reviewed positive/negative train outcomes and separate development data')
    return train,dev


def _fit_scale(batch):
    import torch
    scale={}
    for key,value in batch.items():
        if key.endswith('_mask'):
            continue
        selected=value
        if key in ('past_observations','executed_history'):
            mask=batch['observation_history_mask' if key=='past_observations' else 'action_history_mask']
            selected=value[mask]
        if selected.numel():
            mean=selected.mean(dim=0)
            std=selected.std(dim=0,unbiased=False).clamp_min(1e-6)
        else:
            mean=torch.zeros(value.shape[-1]);std=torch.ones(value.shape[-1])
        scale[key]={'mean':mean,'std':std}
    return scale


def normalize(batch,scale):
    result=dict(batch)
    for key,stats in scale.items():
        result[key]=(batch[key]-stats['mean'])/stats['std']
    return result


def train(rows,output,epochs=30,hidden=32,seed=17,use_history=True,variant=None):
    import torch
    train_rows,dev_rows=validate_training_rows(rows)
    require(type(epochs) is int and epochs>0, 'positive epoch count required')
    require(not Path(output).exists(),'checkpoint already exists')
    torch.set_num_threads(1);torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    x=tensors([r['features'] for r in train_rows]);z=tensors([r['features'] for r in dev_rows])
    if variant is None:
        cfg=configuration(x,hidden,use_history)
    else:
        configs=ablation_configurations(x,hidden)
        require(variant in configs,'unknown ablation variant');cfg=configs[variant]
    require(configuration(z,cfg['hidden'],cfg['use_history'],cfg['observation_history_steps'],cfg['action_history_steps'])==cfg,
            'development feature shape mismatch')
    scale=_fit_scale(x);x=normalize(x,scale);z=normalize(z,scale)
    y=torch.tensor([float(r['continuation_success']) for r in train_rows])
    model=build_model(cfg)
    optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        loss=torch.nn.functional.binary_cross_entropy_with_logits(model(x),y)
        require(bool(torch.isfinite(loss)),'nonfinite loss')
        loss.backward();optimizer.step()
    model.eval()
    with torch.no_grad():
        logits=model(z).tolist()
    checkpoint={'schema':'experimental-sequence-ranker/2','config':cfg,'weights':model.state_dict(),
                'normalization':scale,'score_semantics':'rank_only','online_authorized':False,
                'seed':seed,'epochs':epochs,'profile_id':train_rows[0]['features']['profile_id'],
                'target_definition':'fixed-controller-continuation/v1',
                'continuation_context_reference':train_rows[0]['continuation_context_reference'],
                'encoding_reference':train_rows[0]['encoding_reference'],
                'variant':variant or ('history' if use_history else 'current'),
                'research_conclusion':'NOT_ESTABLISHED'}
    with Path(output).open('xb') as f:
        torch.save(checkpoint,f)
    return dict(train_samples=len(train_rows),development_samples=len(dev_rows),
                final_train_loss=float(loss.detach()),development_logits=logits,
                score_semantics='rank_only',online_authorized=False,research_conclusion='NOT_ESTABLISHED')


def predict(checkpoint,features):
    import torch
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    require(saved['schema']=='experimental-sequence-ranker/2','unsupported checkpoint; context-bound v2 required')
    require(all(f['profile_id']==saved['profile_id'] for f in features),'checkpoint profile mismatch')
    require(all(f.get('continuation_context_reference')==saved['continuation_context_reference'] for f in features),
            'checkpoint controller/target/camera/budget context mismatch')
    require(all(f.get('encoding_reference')==saved['encoding_reference'] for f in features), 'checkpoint encoding mismatch')
    batch=tensors(features)
    cfg=saved['config']
    require(configuration(batch,cfg['hidden'],cfg['use_history'],cfg['observation_history_steps'],cfg['action_history_steps'])==cfg,
            'checkpoint input mismatch')
    model=build_model(cfg);model.load_state_dict(saved['weights']);model.eval()
    with torch.no_grad():
        logits=model(normalize(batch,saved['normalization'])).tolist()
    return dict(scores=logits,score_semantics='rank_only',online_authorized=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,help='Reviewed recovery-decision JSONL; dispatch exports are rejected')
    parser.add_argument('--checkpoint',required=True)
    parser.add_argument('--epochs',type=int,default=30)
    parser.add_argument('--current-only',action='store_true')
    parser.add_argument('--variant',choices=('current','observation-total3','observation-total5',
                                            'observation-action-total5','current-capacity-match'))
    args=parser.parse_args()
    rows=[json.loads(line) for line in Path(args.input).read_text(encoding='utf-8').splitlines() if line.strip()]
    require(not(args.current_only and args.variant),'choose --current-only or --variant')
    print(json.dumps(train(rows,args.checkpoint,args.epochs,use_history=not args.current_only,variant=args.variant),indent=2))


if __name__=='__main__':
    main()
