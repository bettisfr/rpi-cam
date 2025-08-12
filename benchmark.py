import json
import os
import subprocess
from time import time
import numpy as np
import pandas as pd

# Raspberry Pi SSH details
# HOST = "192.168.1.197" # RPi5
HOST = "192.168.1.178" # RPi3
USER = "fra"
PRIVATE_KEY_PATH = "~/.ssh/id_rsa"
SCRIPT_FOLDER = "/home/fra/model-tests/exp_time_resource/"
SCRIPT_FILE = "main.py"
VENV_PATH = "/home/fra/antenv/bin/activate"
FNIRSI_BIN_PATH = "/home/fra/fnirsi/fnirsi_logger.py"
LOG_FILE_PATH = "/home/fra/fnirsi/log.txt"

avg_RAM = []
max_RAM = []
avg_CPU = []
max_CPU = []
avg_pre_processing = []
avg_inference = []
avg_post_processing = []

avg_W = []
max_W = []
avg_V = []
max_V = []
avg_A = []
max_A = []


def run_remote_script(mod, prec, form):
    argument = f"{mod} {prec} {form}"

    cmd = f"source {VENV_PATH} && cd {SCRIPT_FOLDER} && python3 {SCRIPT_FILE} {argument}"
    ssh_command = f"ssh -i {PRIVATE_KEY_PATH} {USER}@{HOST} '{cmd}'"

    # Record the start timestamp
    start_time = time()

    # Run the command using subprocess
    process = subprocess.Popen(ssh_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if stderr:
        print("Error:\n", stderr.decode())

    # Record the end timestamp
    end_time = time()

    try:
        data = json.loads(stdout.decode().split("RESULTS")[1])
        print(f"{argument} - {data}")

        max_ram = float(data["max_RAM_MB"])
        avg_ram = float(data["avg_RAM_MB"])
        max_cpu = float(data["max_CPU_percent"])
        avg_cpu = float(data["avg_CPU_percent"])
        pre_processing = float(data["pre_processing_ms"])
        inference = float(data["inference_ms"])
        post_processing = float(data["post_processing_ms"])

        max_RAM.append(max_ram)
        avg_RAM.append(avg_ram)
        max_CPU.append(max_cpu)
        avg_CPU.append(avg_cpu)
        avg_pre_processing.append(pre_processing)
        avg_inference.append(inference)
        avg_post_processing.append(post_processing)

    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)

    return start_time, end_time


# Function to process the output of the logger
def process_logger_output(start_time, end_time):
    voltage_vals = []
    current_vals = []
    power_vals = []

    # Open the log file
    with open(LOG_FILE_PATH, 'r') as log_file:
        for line in log_file:
            # Skip the header
            if line.startswith("timestamp"):
                continue

            # Extract the columns (assuming they are space-separated)
            columns = line.split()

            if len(columns) >= 9:
                timestamp = float(columns[0])  # timestamp
                voltage = float(columns[2])  # voltage_V
                current = float(columns[3])  # current_A
                # energy = float(columns[7])  # energy_Ws

                # Filter data based on timestamps
                if start_time <= timestamp <= end_time:
                    # Calculate instantaneous power (P = V * I)
                    power = voltage * current
                    power_vals.append(power)

                    # Add voltage and current for reporting
                    voltage_vals.append(voltage)
                    current_vals.append(current)

    # Calculate max and average power
    max_power = max(power_vals) if power_vals else 0.
    avg_power = np.mean(power_vals) if power_vals else 0.

    # Calculate max and average voltage and current for reporting
    max_voltage = max(voltage_vals) if voltage_vals else 0.
    avg_voltage = np.mean(voltage_vals) if voltage_vals else 0.

    max_current = max(current_vals) if current_vals else 0.
    avg_current = np.mean(current_vals) if current_vals else 0.

    max_W.append(max_power)
    avg_W.append(avg_power)

    max_V.append(max_voltage)
    avg_V.append(avg_voltage)

    max_A.append(max_current)
    avg_A.append(avg_current)


if __name__ == '__main__':
    exps = []
    starts = []
    ends = []

    # RPi5
    # mods = ["v10n", "v10s", "v10m", "v11n", "v11s", "v11m", "v9s", "v9m", "v9t"]

    # RPi3
    mods = ["v10n", "v10s", "v11n", "v11s", "v9s", "v9m"]

    # precs = ["FP32", "FP16", "INT8"]
    precs = ["FP32"]
    forms = ["openvino", "mnn", "tflite", "ncnn", "pytorch"]

    # Need this to be run first
    for mod in mods:
        for prec in precs:
            for form in forms:
                if prec == "INT8" and (form == "tflite" or form == "ncnn"):
                    continue

                if form == "pytorch" and prec != "FP32":
                    continue

                if "10" in mod and form == "ncnn":
                    continue

                exps.append(f"{mod} {prec} {form}")
                start_time, end_time = run_remote_script(mod, prec, form)

                starts.append(start_time)
                ends.append(end_time)

    # After all, iterate to read the log file for V, W, A
    for i in range(0, len(starts)):
        start_time = starts[i]
        end_time = ends[i]
        process_logger_output(start_time, end_time)

    # CSV and DataFrame
    csv = pd.DataFrame(columns=[
        "model", "precision", "format", "max_RAM", "avg_RAM", "max_CPU",
        "avg_CPU", "max_power", "avg_power", "max_voltage", "avg_voltage",
        "max_current", "avg_current", "avg_preprocessing", "avg_inference", "avg_postprocessing"
    ])
    csv_name = "overall_performance_assessment.csv"

    # Print and append to CSV
    for i in range(0, len(exps)):
        print(f"\nSummary for {exps[i]}...")
        print(f"Max RAM: {max_RAM[i]:.2f} MB, Avg RAM: {avg_RAM[i]:.2f} MB")
        print(f"Max CPU: {max_CPU[i]:.2f} %, Avg CPU: {avg_CPU[i]:.2f} %")
        print(f"Max Power: {max_W[i]:.2f} W, Avg Power: {avg_W[i]:.2f} W")
        print(f"Max Voltage: {max_V[i]:.2f} V, Avg Voltage: {avg_V[i]:.2f} V")
        print(f"Max Current: {max_A[i]:.2f} A, Avg Current: {avg_A[i]:.2f} A")
        print(f"Avg Pre-processing time: {avg_pre_processing[i]:.4f} ms")
        print(f"Avg Inference time: {avg_inference[i]:.3f} ms")
        print(f"Avg Post-processing time: {avg_post_processing[i]:.4f} ms")

        model, precision, format_type = exps[i].split(" ")
        csv.loc[len(csv)] = [
            model, precision, format_type,
            f"{max_RAM[i]:.2f}", f"{avg_RAM[i]:.2f}",
            f"{max_CPU[i]:.2f}", f"{avg_CPU[i]:.2f}",
            f"{max_W[i]:.2f}", f"{avg_W[i]:.2f}",
            f"{max_V[i]:.2f}", f"{avg_V[i]:.2f}",
            f"{max_A[i]:.2f}", f"{avg_A[i]:.2f}",
            f"{avg_pre_processing[i]:.4f}",
            f"{avg_inference[i]:.3f}",
            f"{avg_post_processing[i]:.4f}"
        ]

    csv.to_csv(csv_name, index=False)
    print(f"CSV {csv_name} saved.")

