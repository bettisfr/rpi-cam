import os
from ultralytics import YOLO
import pandas as pd
from memory_profiler import memory_usage
import psutil
import time
import json
import threading
import shutil
import gc


def safe_remove(path):
    """Remove a file or directory safely."""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Failed to remove {path}: {e}")


def safe_rename(src, dst):
    """Rename (move) a file or directory safely."""
    try:
        if os.path.exists(dst):
            safe_remove(dst)
        os.rename(src, dst)
    except Exception as e:
        print(f"Failed to rename {src} to {dst}: {e}")


def convert2desired(m_path, d_path, format, type="FP32"):
    model = YOLO(m_path)
    if type == "FP32":
        model.export(format=format, data=d_path, batch=1, task="detect")
    elif type == "FP16":
        model.export(format=format, data=d_path, half=True, batch=1, task="detect")
    else:
        model.export(format=format, data=d_path, int8=True, batch=1, task="detect")
    return


def profile_function(func, *args, **kwargs):
    """Profiles memory and CPU usage of a function execution."""
    cpu_usage = []
    stop_event = threading.Event()

    def monitor_cpu():
        while not stop_event.is_set():
            cpu_usage.append(psutil.cpu_percent(interval=0.1))

    cpu_thread = threading.Thread(target=monitor_cpu)
    cpu_thread.start()

    # Force garbage collection before measurement
    gc.collect()

    result = None

    # Define a wrapper to capture the function result
    def wrapper():
        nonlocal result
        result = func(*args, **kwargs)

    # Measure memory while running the function
    mem_usage = memory_usage(wrapper)

    # Stop CPU monitoring thread
    stop_event.set()
    cpu_thread.join()

    # Calculate statistics
    avg_mem_usage = sum(mem_usage) / len(mem_usage)
    max_mem_usage = max(mem_usage)
    avg_cpu_usage = sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0
    max_cpu_usage = max(cpu_usage) if cpu_usage else 0

    return result, avg_mem_usage, max_mem_usage, avg_cpu_usage, max_cpu_usage


def convert_model(mod, prec, form):
    if prec == "INT8" and (form == "tflite" or form == "ncnn"):
        print("Not supported!!")
        return

    if form == "pytorch":
        print("PyTorch does not need conversion!!")
        return

    path_test = os.path.join("src", "learning", "test", "images")
    if os.path.exists(path_test):
        ims_list = os.listdir(path_test)
    else:
        ims_list = []

    yaml_path = os.path.join("src", "data.yaml")

    weights_dir = os.path.join("models", mod, "weights")
    models_dir = os.path.join(weights_dir, "best.pt")
    convert2desired(models_dir, yaml_path, form, prec)

    safe_remove(os.path.join(weights_dir, "best.onnx"))
    safe_remove(os.path.join(weights_dir, f"{mod}_{prec}_{form}"))

    if form == "openvino":
        if prec == "INT8":
            safe_rename(
                os.path.join(weights_dir, "best_int8_openvino_model"),
                os.path.join(weights_dir, f"{mod}_{prec}_{form}")
            )
        else:
            safe_rename(
                os.path.join(weights_dir, "best_openvino_model"),
                os.path.join(weights_dir, f"{mod}_{prec}_{form}")
            )
    elif form == "tflite":
        safe_rename(
            os.path.join(weights_dir, "best_saved_model"),
            os.path.join(weights_dir, f"{mod}_{prec}_{form}")
        )
    elif form == "mnn":
        safe_rename(
            os.path.join(weights_dir, "best.mnn"),
            os.path.join(weights_dir, f"{mod}_{prec}_{form}.mnn")
        )
    elif form == "ncnn":
        safe_rename(
            os.path.join(weights_dir, "best_ncnn_model"),
            os.path.join(weights_dir, f"{mod}_{prec}_{form}")
        )


def run_test(mod, prec, form):
    if prec == "INT8" and (form == "tflite" or form == "ncnn"):
        print("Not supported!!")
        return

    if form == "pytorch" and prec != "FP32":
        print("PyTorch only FP32!!")
        return

    if "10" in mod and form == "ncnn":
        print("YOLOv10 and NCNN is not supported")
        return

    path_test = os.path.join("src", "learning", "test", "images")
    ims_list = os.listdir(path_test)

    weights_directory = os.path.join("models", mod, "weights")

    new_model = ""

    if form == "pytorch":
        models_directory = os.path.join(weights_directory, "best.pt")
    elif form == "openvino":
        models_directory = os.path.join(weights_directory, f"{mod}_{prec}_{form}")
        if prec == "INT8":
            new_model = os.path.join(weights_directory, "best_int8_openvino_model")
        else:
            new_model = os.path.join(weights_directory, "best_openvino_model")

        safe_remove(new_model)
        shutil.copytree(models_directory, new_model)
    elif form == "tflite":
        models_directory = os.path.join(weights_directory, f"{mod}_{prec}_{form}")
        new_model = os.path.join(weights_directory, "best_saved_model")
        safe_remove(new_model)
        shutil.copytree(models_directory, new_model)
    elif form == "mnn":
        models_directory = os.path.join(weights_directory, f"{mod}_{prec}_{form}.mnn")
    elif form == "ncnn":
        models_directory = os.path.join(weights_directory, f"{mod}_{prec}_{form}")
        new_model = os.path.join(weights_directory, "best_ncnn_model")
        safe_remove(new_model)
        shutil.copytree(models_directory, new_model)

    if new_model == "":
        new_model = models_directory

    exported_model = YOLO(new_model, task="detect")

    # Start profiling before the loop
    results, avg_mem, max_mem, avg_cpu, max_cpu = profile_function(
        lambda: [exported_model(os.path.join(path_test, im), imgsz=640) for im in ims_list]
    )

    if form in ["openvino", "tflite"]:
        safe_remove(new_model)

    # Extract timing statistics
    speeds = [res[0].speed for res in results]  # Extracting `speed` from each result
    total_preprocessing = sum(s["preprocess"] for s in speeds) / len(speeds)
    total_inference = sum(s["inference"] for s in speeds) / len(speeds)
    total_postprocessing = sum(s["postprocess"] for s in speeds) / len(speeds)

    stats = {
        "max_RAM_MB": round(max_mem, 2),
        "avg_RAM_MB": round(avg_mem, 2),
        "max_CPU_percent": round(max_cpu, 2),
        "avg_CPU_percent": round(avg_cpu, 2),
        "pre_processing_ms": round(total_preprocessing, 4),
        "inference_ms": round(total_inference, 3),
        "post_processing_ms": round(total_postprocessing, 4),
    }

    print("RESULTS")
    print(json.dumps(stats, indent=4))
    print("RESULTS")


def convert_all():
    mods = ["v10m", "v10n", "v10s", "v11m", "v11n", "v11s", "v9m", "v9s", "v9t"]
    precs = ["FP32", "FP16", "INT8"]
    forms = ["tflite", "openvino", "mnn"]

    mods = ["v10m", "v10n", "v10s", "v11m", "v11n", "v11s", "v9m", "v9s", "v9t"]
    precs = ["FP16", "FP32"]
    forms = ["ncnn"]

    for mod in mods:
        for prec in precs:
            for form in forms:
                print(f"Doing: {mod} {prec} {form}")

                convert_model(mod, prec, form)

