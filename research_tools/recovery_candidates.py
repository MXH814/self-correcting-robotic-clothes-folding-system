"""Encode an explicitly proposed recovery macro, never infer it from future motion."""
from .diagnostics import finite, require
from .runtime_intake import clock, ordered


def encode_macro(candidate):
    require(candidate.get('schema')=='recovery-macro-proposal/1'
            and candidate.get('kind')=='release-retreat-regrasp-lift', 'unsupported recovery macro')
    require(candidate.get('coordinate_frame')=='world' and candidate.get('position_unit')=='m',
            'macro coordinates must be explicit world metres')
    require(candidate.get('arm') in ('left','right'), 'macro arm')
    require(candidate.get('source_reference') and candidate.get('candidate_id'), 'missing proposal provenance')
    clock(candidate['available_at'])
    vector=[float(candidate['arm']=='left'),float(candidate['arm']=='right')]
    for key in ('retreat_world_m','pick_world_m','lift_world_m'):
        v=candidate[key]
        require(isinstance(v,list) and len(v)==3 and all(finite(x) for x in v), 'invalid macro position')
        vector.extend(v)
    orientation=candidate['orientation_wxyz']
    require(isinstance(orientation,list) and len(orientation)==4 and all(finite(x) for x in orientation)
            and abs(sum(x*x for x in orientation)-1)<.01, 'macro orientation must be unit wxyz')
    vector.extend(orientation)
    for key in ('open_wait_steps','close_wait_steps'):
        require(type(candidate[key]) is int and 0<=candidate[key]<=18000, 'invalid macro wait steps')
        vector.append(float(candidate[key]))
    return vector


def recovery_features(dispatch_input,candidate):
    vector=encode_macro(candidate)
    require(dispatch_input.get('schema')=='garment-dispatch-input/1', 'expected causal garment context')
    require(ordered(clock(candidate['available_at']),clock(dispatch_input['as_of'])),
            'candidate became available after decision')
    require(candidate.get('trial_id')==dispatch_input['trial_id'], 'cross-trial candidate')
    require(dispatch_input.get('online_authorized') is False, 'offline context only')
    result=dict(dispatch_input)
    result.update(schema='recovery-decision-features/1',candidate_target=vector,
                  candidate_id=candidate['candidate_id'],input_scope='recovery_macro_decision',
                  recovery_macro_candidate_spec=candidate,online_authorized=False)
    return result
