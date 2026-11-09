"""Run the upstream Fold_Tops demo with a small, explicitly recorded local profile."""
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(os.environ["ROBOTICS_PROJECT_ROOT"]).resolve()
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import isaacsim
from isaacsim import SimulationApp as OriginalSimulationApp


class LocalSimulationApp(OriginalSimulationApp):
    active_instance = None

    def close(self, *args, **kwargs):
        if getattr(self, "_fold_recovery_evidence", None) is not None:
            evidence = self._fold_recovery_evidence
            self._fold_recovery_evidence = None
            evidence.finish(self._fold_env)
        if getattr(self, "_fold_camera_evidence", None) is not None:
            evidence = self._fold_camera_evidence
            self._fold_camera_evidence = None
            evidence.finish(self._fold_env)
        if (os.environ.get("ROBOTICS_KEEP_OPEN") == "1"
                and os.environ.get("ROBOTICS_HEADLESS", "1") == "0"
                and not getattr(self, "_local_preview_held", False)):
            self._local_preview_held = True
            print("LOCAL_FOLD_PREVIEW: run completed; close the window to exit", flush=True)
            while self.is_running():
                self.update()
        return super().close(*args, **kwargs)

    def __init__(self, launch_config=None, *args, **kwargs):
        config = dict(launch_config or {})
        config.update({"headless": os.environ.get("ROBOTICS_HEADLESS", "1") == "1", "width": 960, "height": 720, "multi_gpu": False})
        config["extra_args"] = list(config.get("extra_args", [])) + [
            "--/plugins/carb.tasking.plugin/threadCount=4",
            "--/plugins/omni.tbb.globalcontrol/maxThreadCount=4",
            "--/persistent/physics/numThreads=4",
        ]
        super().__init__(config, *args, **kwargs)
        from Env_StandAlone.BaseEnv import BaseEnv
        self._fold_env = None
        self._fold_camera_evidence = None
        self._fold_recovery_evidence = None
        LocalSimulationApp.active_instance = self
        if os.environ.get("ROBOTICS_FOLD_CAMERA") == "1":
            from fold_camera_evidence import FoldCameraEvidence
            self._fold_camera_evidence = FoldCameraEvidence(Path(os.environ["ROBOTICS_OUTPUT_ROOT"]), BaseEnv)
        if os.environ.get("ROBOTICS_FOLD_RECOVERY") == "1":
            from fold_recovery_evidence import FoldRecoveryEvidence
            if os.environ.get("ROBOTICS_FIPER_PRE_SCENARIO"):
                scenario = os.environ["ROBOTICS_FIPER_PRE_SCENARIO"]
                if scenario == "official-missing-inputs":
                    from official_pre_evidence import OfficialPreEvidence
                    FoldRecoveryEvidence = OfficialPreEvidence
                elif scenario == "missing-inputs":
                    from fiper_pre_evidence import FiperPreEvidence
                    FoldRecoveryEvidence = FiperPreEvidence
                elif scenario in ("normal-a", "fault-b"):
                    from official_ab_evidence import OfficialABEvidence
                    FoldRecoveryEvidence = OfficialABEvidence
                else:
                    raise ValueError("Unsupported FIPER Pre scenario: " + scenario)
                if os.environ.get("ROBOTICS_PRE_NORMAL_COLLECTION") == "1":
                    raise ValueError("Detection and detector-disabled collection are mutually exclusive")
            if os.environ.get("ROBOTICS_PRE_NORMAL_COLLECTION") == "1":
                from pre_observation_evidence import PreObservationEvidence
                FoldRecoveryEvidence = PreObservationEvidence
            self._fold_recovery_evidence = FoldRecoveryEvidence(
                Path(os.environ["ROBOTICS_OUTPUT_ROOT"]), ROOT, BaseEnv)
        original_init = BaseEnv.__init__

        def local_init(instance, *env_args, **env_kwargs):
            original_init(instance, *env_args, **env_kwargs)
            instance.physics.set_gpu_max_rigid_contact_count(262144)
            instance.physics.set_gpu_max_rigid_patch_count(262144)
            self._fold_env = instance

        BaseEnv.__init__ = local_init
        print("LOCAL_FOLD_PROFILE: 4 CPU workers, 262144 GPU contact/patch budget", flush=True)


isaacsim.SimulationApp = LocalSimulationApp
sys.argv = [str(ROOT / "Env_StandAlone/Fold_Tops_Env.py")] + sys.argv[1:]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
except BaseException as error:
    app = LocalSimulationApp.active_instance
    evidence = getattr(app, "_fold_recovery_evidence", None)
    if evidence is not None:
        try:
            evidence.abort(error)
        except Exception as save_error:
            print("PARTIAL_EVIDENCE_SAVE_FAILED", repr(save_error), flush=True)
        app._fold_recovery_evidence = None
    if app is not None:
        try:
            app.close()
        except Exception as close_error:
            print("SIMULATOR_CLOSE_FAILED", repr(close_error), flush=True)
    raise
