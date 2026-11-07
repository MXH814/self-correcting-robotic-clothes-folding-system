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
    def close(self, *args, **kwargs):
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
        original_init = BaseEnv.__init__

        def local_init(instance, *env_args, **env_kwargs):
            original_init(instance, *env_args, **env_kwargs)
            instance.physics.set_gpu_max_rigid_contact_count(262144)
            instance.physics.set_gpu_max_rigid_patch_count(262144)

        BaseEnv.__init__ = local_init
        print("LOCAL_FOLD_PROFILE: 4 CPU workers, 262144 GPU contact/patch budget", flush=True)


isaacsim.SimulationApp = LocalSimulationApp
sys.argv = [str(ROOT / "Env_StandAlone/Fold_Tops_Env.py")] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
