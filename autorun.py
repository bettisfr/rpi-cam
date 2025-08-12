import subprocess
import time


host = "141.250.25.160"

# Function to ping the host for 1 minute
def ping_host(host, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = subprocess.run(["ping", "-c", "1", host], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if response.returncode == 0:
            return True
        time.sleep(1)
    return False

if ping_host(host):
    command = "source pyenv/bin/activate && cd rpi-cam && python client.py"
    subprocess.run(command, shell=True, executable="/bin/bash")
else:
    print("Ping failed, host unreachable.")


