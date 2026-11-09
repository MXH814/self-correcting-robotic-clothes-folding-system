"""Continuous RGB monitoring and bounded recovery in the existing simulator.

normal-a never injects and refuses any recovery request. fault-b injects once,
but only the official observation detector may request recovery. All dispatches
are guarded below the dense controller; an interrupted controller is unwound
before measuring rest or executing a macro. This is a simulation diagnostic.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np

from fold_recovery_evidence import FoldRecoveryEvidence
from fold_recovery_chain import FullRecoveryChain
from fiper_pre_evidence import FiperPreEvidence, FiperInputsUnavailable
from official_pre_adapter import OfficialPreAdapter
from pre_detection_bridge import make_input, GeometryHoldMonitor
from pre_execution_support import (SynchronousDispatchLedger, measure_rest, refresh_rest,
    validate_macro_ik, build_preflight, MaterialPatchGeometry)
from research_tools.prepare_pre_normal_detector import controller_phase_at, detector_context_reference


class PendingObservationAlert(RuntimeError):
    pass


class OfficialABEvidence(FiperPreEvidence):
    def __init__(self, output, upstream, base_env):
        FoldRecoveryEvidence.__init__(self, output, upstream, base_env)
        self.scenario = os.environ['ROBOTICS_FIPER_PRE_SCENARIO']
        if self.scenario not in ('normal-a', 'fault-b'):
            raise ValueError('Unsupported monitored scenario')
        self.events, self.controller_events = [], []
        self.pending = None
        self.halted = False
        self.mode = 'NORMAL'
        self.monitor_suspended = False
        self.seen_frames = set()
        self.report_counts = Counter()
        self.phase_counts = Counter()
        self.pick = self.lift = self.patch = None
        self.injected = False
        self.record.update(injection=None, candidate=None, pre_scenario=self.scenario,
            detection_entry='OfficialPreAdapter/DetectionRuntime', recovery_attempts=0,
            fixed_continuation_started=False, final_control_state='INITIALIZING',
            product_stop_verified=False, independent_review_status='pending',
            geometry_profile=dict(table_z_m=0.,min_cloth_height_m=.15,max_hand_distance_m=.12,
                window_s=.2,min_samples=3,max_gap_s=.25,
                scope='declared simulation hold heuristic; not product acceptance'))
        repo = Path(__file__).resolve().parents[2]
        hashes = {}
        for source in list(Path(__file__).parent.glob('*.py')) + list((repo/'research_tools').glob('*.py')):
            relative = source.relative_to(repo)
            target = self.output/'source-snapshot'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read_bytes())
            hashes[relative.as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()
        self.config = dict(schema='official-ab-run/1',trial_id=self.record['trial_id'],scenario=self.scenario,
            producer_sha256=hashes, package_directory=os.environ['ROBOTICS_PRE_PACKAGE'],
            encoder_weights=os.environ['ROBOTICS_PRE_ENCODER'],
            detector_source='RGB only; no injection events, material points or future outcomes',
            scope='small development diagnostic; independent human acceptance pending')
        self._save_config()

    def _save_config(self):
        (self.output/'official-ab-config.json').write_text(json.dumps(self.config,indent=2),encoding='utf-8')

    def control_event(self, kind, **payload):
        self.event(kind, **payload)
        self.controller_events.append(self.events[-1])

    def halt(self, reason):
        if not self.halted:
            self.halted = True
            self.ledger.halted = True
            self.ledger.block_normal_dispatch()
            self.record.update(final_control_state='HELP_REQUESTED_AUTOMATIC_DISPATCH_DISABLED',
                dispatch_count_at_help=len(self.chain.trace.actions), help_reason=reason,
                recovery_attempts=self.adapter.flow.attempts)
            self.event('HELP_REQUESTED',reason=reason,automatic_dispatch_enabled=False,
                physical_rest_confirmed=False,manual_authority_granted=False)
            self.save()
        raise FiperInputsUnavailable(reason)

    def attach(self, env):
        import torch
        torch.set_num_threads(4)
        self.env = env
        self.chain = FullRecoveryChain(self, env, self.upstream)
        trace = self.chain.trace
        robot = env.bimanual_dex
        self.ledger = SynchronousDispatchLedger(trace.trial_id,recovery_enabled=self.scenario=='fault-b')
        context = detector_context_reference(self.chain.context,self.record['garment'])
        self.adapter = OfficialPreAdapter(trace,package_dir=self.config['package_directory'],
            encoder_weights=self.config['encoder_weights'],context_reference=context,
            journal_path=self.output/'official-workflow-events.jsonl')
        if self.adapter.runtime.detector is None:
            self.halt('MODEL_LOAD_FAILED:'+str(self.adapter.runtime.error))
        meta = self.adapter.runtime.detector.meta
        self.config.update(context_reference=context,detector_metadata=meta,
            encoder_sha256=hashlib.sha256(Path(self.config['encoder_weights']).read_bytes()).hexdigest(),
            checkpoint_sha256=hashlib.sha256((Path(self.config['package_directory'])/'detector.pt').read_bytes()).hexdigest())
        self._save_config()
        # Warm library kernels before using observation freshness deadlines.
        self.adapter.runtime.encoder.encode([trace.frames[-1]])
        self.record['final_control_state'] = 'MONITORING'
        original_observe = trace.observe

        def observe(phase, *, force=False):
            obs = original_observe(phase,force=force)
            if obs is not None and not self.monitor_suspended:
                self.consume(obs)
            return obs
        trace.observe = observe
        self.original_observe = original_observe
        self.original_hand = robot.set_both_hand_state
        self.original_left = robot.dexleft.dense_step_action

        # Guard actual SDK dispatch, including actions inside dense loops.
        for arm in trace.arms.values():
            controller = arm.get_articulation_controller()
            original_apply = controller.apply_action
            def apply(control_actions, _original=original_apply):
                if self.halted:
                    raise FiperInputsUnavailable(self.record.get('help_reason','HALTED'))
                if self.mode == 'MACRO':
                    if self.adapter.flow.state != 'RECOVERING':
                        self.halt('MACRO_WITHOUT_ACCEPTANCE')
                elif not self.ledger.normal_dispatch_allowed or self.pending is not None:
                    raise PendingObservationAlert('Unwind synchronous controller before recovery')
                with self.ledger.dispatch():
                    return _original(control_actions)
            controller.apply_action = apply

        for side, arm in trace.arms.items():
            original = arm.dense_step_action
            count = [0]
            def move(target_pos,target_ori=None,*args,_side=side,_original=original,_count=count,**kwargs):
                _count[0] += 1
                label = {1:'approach-pick',2:'lift',3:'transfer'}.get(_count[0],'scripted-move')
                if _side=='left' and _count[0]==1:
                    self.pick=np.array(target_pos)
                    self.patch=MaterialPatchGeometry.from_pick(env,self.pick)
                    self.record['intended_patch_vertex_ids']=self.patch.patch_ids.tolist()
                if _side=='left' and _count[0]==2:
                    self.lift=np.array(target_pos)
                self.control_event('NORMAL_ACTION_BEGIN',arm=_side,operation=label,
                    target_world_m=np.asarray(target_pos).tolist(),expected_hold=label in ('lift','transfer'))
                self.chain.phase=f'normal-{_side}-{label}'
                trace.boundary(self.chain.phase)
                if self.scenario=='fault-b' and _side=='left' and _count[0]==3 and not self.injected:
                    self.inject_fault()
                if self.pending is not None:
                    self.recover_at_boundary(_side,label,target_ori)
                try:
                    with self.ledger.controller():
                        result=_original(target_pos,target_ori,*args,**kwargs)
                except PendingObservationAlert:
                    self.recover_at_boundary(_side,label,target_ori)
                    # Discard the old dense trajectory and rebuild from current state.
                    with self.ledger.controller():
                        result=_original(target_pos,target_ori,*args,**kwargs)
                if self.pending is not None:
                    self.recover_at_boundary(_side,label,target_ori)
                self.control_event('NORMAL_ACTION_END',arm=_side,operation=label,sdk_result=bool(result))
                if not result:
                    self.halt('NORMAL_CONTROLLER_IK_FAILED')
                return result
            arm.dense_step_action=move

        def hand(*args,**kwargs):
            left=kwargs.get('left_hand_state',args[0] if args else 'None')
            right=kwargs.get('right_hand_state',args[1] if len(args)>1 else 'None')
            self.control_event('NORMAL_HAND_COMMAND',left=left,right=right,planned_release='open' in (left,right))
            if 'open' in (left,right):
                self.chain.phase='normal-planned-release'
            try:
                with self.ledger.controller():
                    return self.original_hand(*args,**kwargs)
            except PendingObservationAlert:
                self.halt('ALERT_AT_UNSUPPORTED_HAND_BOUNDARY')
        robot.set_both_hand_state=hand
        # Bimanual controller must also participate in nesting/queue evidence.
        original_both=robot.dense_move_both_ik
        def both(*args,**kwargs):
            try:
                with self.ledger.controller():
                    return original_both(*args,**kwargs)
            except PendingObservationAlert:
                self.halt('ALERT_AT_UNSUPPORTED_BIMANUAL_BOUNDARY')
        robot.dense_move_both_ik=both
        self.control_event('COLLECTION_STARTED',detector_loaded=True,recovery_enabled=self.scenario=='fault-b')

    def runtime_only(self, obs, phase):
        metadata=make_input(self.chain.trace,obs,controller_phase=phase,runtime=self.adapter.runtime)
        report=self.adapter.runtime.observe(self.chain.trace.frames[obs['frame_index']],metadata,
            generation=self.adapter.flow.generation,
            captured_wall_s=obs['camera_read_begin']['wall_monotonic_ns']/1e9,now_wall_s=time.monotonic())
        return metadata, report

    def consume(self, obs):
        key=obs['rendering_frame']
        if key in self.seen_frames or self.halted:
            return
        self.seen_frames.add(key)
        phase,source=controller_phase_at(self.controller_events,obs['rendering_time_s'])
        self.phase_counts[phase]+=1
        if self.adapter.flow.state=='RECOVERY_REQUESTED':
            metadata,report=self.runtime_only(obs,phase)
            request=None  # Keep the RND window current while measuring rest.
        else:
            metadata,report,request=self.adapter.observe(obs,controller_phase=phase,expected_holding=phase=='HOLD')
        self.report_counts[report['status']]+=1
        self.event('OFFICIAL_DETECTION',observation=metadata,report=report,request=request,
            controller_source_sequence=source['sequence'] if source else None)
        if request and request['kind']=='REQUEST_HALT_AND_HELP':
            self.halt(request['reason']+' / '+report['reason'])
        if request and request['kind']=='REQUEST_RECOVERY_PREFLIGHT':
            self.pending=request
            self.ledger.block_normal_dispatch()
            self.record.setdefault('alerts',[]).append(dict(observation_id=obs['observation_id'],
                observed_sim_s=obs['rendering_time_s'],score=report['score'],threshold=report['threshold'],
                dispatch_count=len(self.chain.trace.actions)))
            if self.scenario=='normal-a':
                self.halt('A_NORMAL_RUN_OBSERVATION_ALERT')

    def inject_fault(self):
        if self.pending is not None:
            self.halt('ALERT_BEFORE_B_INJECTION')
        self.injected=True
        self.record['injection']='early_open_after_first_lift'
        self.event('FAULT_INJECTION_BEGIN',kind_of_fault='early-open',detector_receives_injection=False)
        self.snapshot(self.env,'before-injection')
        # Use the saved method: an injected open is not a planned release event.
        with self.ledger.controller():
            self.original_hand(left_hand_state='open')
        self.event('FAULT_INJECTION_END')
        # Observation opportunity only. Expiry never requests a recovery macro.
        deadline=self.chain.trace.clock()['sim_time_s']+1.0
        while self.pending is None and self.chain.trace.clock()['sim_time_s']<deadline:
            self.env.step()
        if self.pending is None:
            self.event('NO_ALERT_IN_DIAGNOSTIC_OBSERVATION_WINDOW',window_sim_s=1.0,
                recovery_requested=False)

    def recover_at_boundary(self,side,label,orientation):
        if self.pending is None:
            return
        if side!='left' or label not in ('lift','transfer') or self.pick is None or self.lift is None:
            self.halt('ALERT_OUTSIDE_SUPPORTED_LEFT_SLEEVE_MACRO')
        if self.ledger.active_calls or self.ledger.dispatch_depth:
            self.halt('CONTROLLER_STACK_NOT_UNWOUND')
        proposal=self.chain.propose(self.pick,self.lift,np.asarray(orientation))
        rest=measure_rest(self.chain.trace,self.env.step,self.ledger)
        if not rest['passed']:
            self.halt('REST_UNCONFIRMED:'+rest['reason'])
        self.monitor_suspended=True
        macro=validate_macro_ik(self.env.bimanual_dex.dexleft,proposal,self.chain.trace)
        if not macro['passed']:
            self.halt('MACRO_PREFLIGHT_FAILED:'+macro['reason'])
        # Obtain an actually new render, not a new UUID pointing at old pixels.
        last=self.adapter.runtime.detector.last[1] if self.adapter.runtime.detector.last else None
        obs=None
        for _ in range(4):
            self.env.step()
            obs=self.chain.trace.observe('PREFLIGHT_REFRESH',force=True)
            if str(obs['rendering_frame'])!=last:
                break
        metadata,report,event=self.adapter.refresh_preflight(obs,controller_phase='HOLD')
        self.event('PREFLIGHT_REDETECTION',observation=metadata,report=report,request=event)
        if event['kind']!='PREFLIGHT_DETECTION_REFRESHED':
            self.halt('FRESH_ALERT_NOT_CONFIRMED:'+event['reason'])
        rest=refresh_rest(self.chain.trace,self.ledger,rest)
        permit=build_preflight(self.chain.trace,self.ledger,rest,macro,proposal)
        self.mode='MACRO'
        # Saved methods avoid normal phase logging during the macro.
        proxy=type('MacroRobot',(),{})()
        def macro_hand(**kwargs):
            with self.ledger.controller():
                return self.original_hand(**kwargs)
        proxy.set_both_hand_state=macro_hand
        def macro_move(*args,**kwargs):
            with self.ledger.controller():
                return self.original_left(*args,**kwargs)
        event=self.adapter.execute_macro(self.pending,chain=self.chain,proposal=proposal,
            robot=proxy,original_move=macro_move,preflight_evidence=permit)
        self.record['recovery_attempts']=self.adapter.flow.attempts
        self.mode='VERIFY'
        self.event('MACRO_RESULT',request=event)
        if event['kind']!='REQUEST_NEW_HOLD_OBSERVATIONS':
            self.halt('MACRO_NOT_CONFIRMED:'+event['reason'])
        profile={k:v for k,v in self.record['geometry_profile'].items() if k!='scope'}
        monitor=GeometryHoldMonitor(**profile)
        result=None
        for _ in range(30):
            self.env.step()
            sample=self.patch.capture(self.chain.trace,self.adapter.flow.generation)
            check=monitor.update(**sample)
            result=self.adapter.flow.verify(check,now_wall_s=time.monotonic())
            self.event('RECOVERY_CHECK',report=check,request=result)
            if result['kind']!='WAIT_FOR_OBSERVATION':
                break
        if result is None or result['kind']!='REQUEST_FIXED_CONTINUATION':
            self.halt('RECOVERY_HOLD_NOT_CONFIRMED')
        self.pending=None
        self.ledger.generation=self.adapter.flow.generation
        self.ledger.normal_blocked=False
        self.mode='NORMAL'
        self.monitor_suspended=False
        self.adapter.runtime.detector.reset()
        self.record['fixed_continuation_started']=True
        self.event('FIXED_CONTINUATION_ENABLED',generation=self.ledger.generation)

    def finish(self, env):
        if env is None or self.record['judgment'] is None:
            self.abort(RuntimeError('No final outcome recorded'))
            return
        if self.pending is not None:
            self.halt('UNRESOLVED_ALERT_AT_END')
        self.monitor_suspended=True
        self.chain.trace.boundary('final-evidence')
        self.snapshot(env,'final')
        self.record.update(final_control_state='MONITORED_CONTROLLER_COMPLETED',
            detection_status_counts=dict(self.report_counts),detection_phase_counts=dict(self.phase_counts),
            recovery_attempts=self.adapter.flow.attempts)
        self.event('FINAL_OUTCOME',judgment=self.record['judgment'],recovery_attempts=self.adapter.flow.attempts)
        self.chain.finish()
        marker=os.environ.get('ROBOTICS_PROBE_MARKER')
        if marker: Path(marker).write_text(str(self.output),encoding='utf-8')
        print('OFFICIAL_AB_COMPLETED',self.output,flush=True)

    def abort(self, error):
        self.monitor_suspended=True
        self.record.update(detection_status_counts=dict(self.report_counts),detection_phase_counts=dict(self.phase_counts))
        super().abort(error)
