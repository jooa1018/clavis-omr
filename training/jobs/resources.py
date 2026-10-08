"""CPU policy injected into each queue Python process and its library APIs."""

import functools
import importlib
import importlib.util
import inspect
import os
import sys
from typing import Any

import psutil

THREAD_ENV = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)


def allowed_cpus(requested: int, available: list[int]) -> list[int]:
    if not 1 <= requested <= 8 or len(available) < 2:
        raise ValueError("CPU request must be 1..8; at least two logical CPUs must be available")
    capacity = max(1, len(available) - 1) if len(available) <= 8 else 8
    return available[: min(requested, capacity)]


def configure_library(name: str, library: Any, limit: int) -> None:
    if name == "torch":
        library.set_num_threads(limit)
        library.set_num_interop_threads(1)
    elif name == "cv2":
        library.setNumThreads(limit)
        library.ocl.setUseOpenCL(False)
    elif name == "onnxruntime":
        original = library.InferenceSession

        @functools.wraps(original)
        def session(*args: Any, **kwargs: Any) -> Any:
            values = list(args)
            options = values[1] if len(values) > 1 else kwargs.get("sess_options")
            options = options if options is not None else library.SessionOptions()
            options.intra_op_num_threads = limit
            options.inter_op_num_threads = 1
            if len(values) > 1:
                values[1] = options
            else:
                kwargs["sess_options"] = options
            if len(values) > 2:
                values[2] = ["CPUExecutionProvider"]
            else:
                kwargs["providers"] = ["CPUExecutionProvider"]
            if len(values) > 3:
                values[3] = None
            else:
                kwargs.pop("provider_options", None)
            return original(*values, **kwargs)

        library.InferenceSession = session
    elif name == "lightgbm":

        def cap(original: Any) -> Any:
            signature = inspect.signature(original)

            @functools.wraps(original)
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                bound = signature.bind(*args, **kwargs)
                params = dict(bound.arguments.get("params") or {})
                for alias in ("num_thread", "nthread", "nthreads", "n_jobs", "device"):
                    params.pop(alias, None)
                params.update(num_threads=limit, device_type="cpu")
                bound.arguments["params"] = params
                return original(*bound.args, **bound.kwargs)

            return wrapped

        library.Booster.__init__ = cap(library.Booster.__init__)
        library.Booster.reset_parameter = cap(library.Booster.reset_parameter)
        library.Dataset.__init__ = cap(library.Dataset.__init__)


def configure() -> dict[str, str | int]:
    limit = int(os.environ["CLAVIS_CPU_LIMIT"])
    if not 1 <= limit <= 8:
        raise ValueError("invalid injected CPU budget")
    for name in THREAD_ENV:
        os.environ[name] = str(limit)
    result: dict[str, str | int] = {"cpuLimit": limit}
    for name in ("torch", "cv2", "onnxruntime", "lightgbm"):
        if importlib.util.find_spec(name) is not None:
            configure_library(name, importlib.import_module(name), limit)
            result[name] = "configured"
        else:
            result[name] = "not-installed"
    return result


def constrain(process: psutil.Process, cpus: list[int]) -> None:
    process.cpu_affinity(cpus)
    if sys.platform == "win32":
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    else:
        process.nice(10)
