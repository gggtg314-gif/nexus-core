
"""
NexusCore PC Monitoring Agent

Existing telemetry:
- CPU usage
- RAM usage %
- Disk usage %
- Disk free space
- IP address
- Uptime
- Operating system

New hardware information:
- CPU model
- CPU cores / threads
- Total RAM
- RAM used / available
- GPU model
- GPU VRAM
- Storage model
- Storage type
- Storage total
- Storage used
- Manufacturer
- System model
- Motherboard
- BIOS version
- System architecture
- Battery percentage
- Battery charging status

Sends telemetry to Flask server using HTTP.
"""

import socket
import time
import requests
import platform
import logging
import shutil
import psutil
import subprocess
import json


# =========================================================
# CONFIGURATION
# =========================================================

SERVER_URL = "http://10.201.134.223:5000/api/update"
AGENT_INTERVAL = 1


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# IP ADDRESS
# =========================================================

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        s.connect(("8.8.8.8", 80))

        ip = s.getsockname()[0]

        s.close()

        return ip

    except Exception:
        return "127.0.0.1"


# =========================================================
# CPU USAGE
# =========================================================

def get_cpu():
    try:
        return round(
            psutil.cpu_percent(interval=1),
            1
        )

    except Exception as e:

        logger.error(
            f"CPU collection failed: {e}"
        )

        return 0.0


# =========================================================
# CPU HARDWARE INFORMATION
# =========================================================

def get_cpu_info():

    try:

        cpu_model = platform.processor()

        if not cpu_model:
            cpu_model = "Unknown"

        physical_cores = (
            psutil.cpu_count(logical=False)
            or 0
        )

        logical_cores = (
            psutil.cpu_count(logical=True)
            or 0
        )

        return {
            "model": cpu_model,
            "cores": physical_cores,
            "threads": logical_cores
        }

    except Exception as e:

        logger.warning(
            f"CPU hardware information unavailable: {e}"
        )

        return {
            "model": "Unknown",
            "cores": 0,
            "threads": 0
        }


# =========================================================
# RAM USAGE %
# =========================================================

def get_ram():

    try:

        ram = psutil.virtual_memory()

        return round(
            ram.percent,
            1
        )

    except Exception as e:

        logger.error(
            f"RAM collection failed: {e}"
        )

        return 0.0


# =========================================================
# RAM HARDWARE INFORMATION
# =========================================================

def get_ram_info():

    try:

        ram = psutil.virtual_memory()

        total_gb = round(
            ram.total / (1024 ** 3),
            2
        )

        used_gb = round(
            ram.used / (1024 ** 3),
            2
        )

        available_gb = round(
            ram.available / (1024 ** 3),
            2
        )

        return {
            "total": total_gb,
            "used": used_gb,
            "available": available_gb
        }

    except Exception as e:

        logger.warning(
            f"RAM hardware information unavailable: {e}"
        )

        return {
            "total": 0.0,
            "used": 0.0,
            "available": 0.0
        }


# =========================================================
# DISK USAGE
# =========================================================

def get_disk():

    try:

        # Existing C: drive monitoring
        usage = shutil.disk_usage("C:\\")

        used_percent = round(
            (usage.used / usage.total) * 100,
            1
        )

        free_gb = round(
            usage.free / (1024 ** 3),
            1
        )

        return (
            used_percent,
            f"{free_gb} GB"
        )

    except Exception as e:

        logger.error(
            f"Disk collection failed: {e}"
        )

        return (
            0.0,
            "0 GB"
        )


# =========================================================
# STORAGE HARDWARE INFORMATION
# =========================================================

def get_storage_info():

    try:

        powershell_command = """
        Get-PhysicalDisk |
        Select-Object -First 1 FriendlyName, MediaType, Size |
        ConvertTo-Json
        """

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                powershell_command
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            raise Exception(
                "PowerShell storage query failed"
            )

        if not result.stdout.strip():
            raise Exception(
                "No storage information returned"
            )

        data = json.loads(
            result.stdout
        )

        if isinstance(data, list):

            data = (
                data[0]
                if data
                else {}
            )

        model = (
            data.get("FriendlyName")
            or "Unknown"
        )

        storage_type = (
            data.get("MediaType")
            or "Unknown"
        )

        size = (
            data.get("Size")
            or 0
        )

        total_gb = round(
            int(size) / (1024 ** 3),
            2
        )

        return {
            "model": model,
            "type": storage_type,
            "total": total_gb
        }

    except Exception as e:

        logger.warning(
            f"Storage information unavailable: {e}"
        )

        return {
            "model": "Unknown",
            "type": "Unknown",
            "total": 0.0
        }


# =========================================================
# GPU INFORMATION
# =========================================================

def get_gpu_info():

    try:

        powershell_command = """
        Get-CimInstance Win32_VideoController |
        Select-Object -First 1 Name, AdapterRAM |
        ConvertTo-Json
        """

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                powershell_command
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            raise Exception(
                "PowerShell GPU query failed"
            )

        if not result.stdout.strip():
            raise Exception(
                "No GPU information returned"
            )

        data = json.loads(
            result.stdout
        )

        if isinstance(data, list):

            data = (
                data[0]
                if data
                else {}
            )

        gpu_model = (
            data.get("Name")
            or "Unknown"
        )

        adapter_ram = (
            data.get("AdapterRAM")
            or 0
        )

        gpu_vram = round(
            int(adapter_ram) / (1024 ** 3),
            2
        )

        return {
            "model": gpu_model,
            "vram": gpu_vram
        }

    except Exception as e:

        logger.warning(
            f"GPU information unavailable: {e}"
        )

        return {
            "model": "Unknown",
            "vram": 0.0
        }


# =========================================================
# SYSTEM INFORMATION
# =========================================================

def get_system_info():

    try:

        powershell_command = """
        $cs = Get-CimInstance Win32_ComputerSystem
        $bios = Get-CimInstance Win32_BIOS
        $mb = Get-CimInstance Win32_BaseBoard

        [PSCustomObject]@{
            Manufacturer = $cs.Manufacturer
            Model = $cs.Model
            Motherboard = "$($mb.Manufacturer) $($mb.Product)"
            BIOS = $bios.SMBIOSBIOSVersion
        } | ConvertTo-Json
        """

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                powershell_command
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            raise Exception(
                "PowerShell system query failed"
            )

        if not result.stdout.strip():
            raise Exception(
                "No system information returned"
            )

        data = json.loads(
            result.stdout
        )

        return {
            "manufacturer":
                data.get("Manufacturer")
                or "Unknown",

            "model":
                data.get("Model")
                or "Unknown",

            "motherboard":
                data.get("Motherboard")
                or "Unknown",

            "bios":
                data.get("BIOS")
                or "Unknown"
        }

    except Exception as e:

        logger.warning(
            f"System information unavailable: {e}"
        )

        return {
            "manufacturer": "Unknown",
            "model": "Unknown",
            "motherboard": "Unknown",
            "bios": "Unknown"
        }


# =========================================================
# BATTERY INFORMATION
# =========================================================

def get_battery_info():

    try:

        battery = psutil.sensors_battery()

        if battery is None:

            return {
                "percent": None,
                "charging": None
            }

        return {
            "percent": round(
                battery.percent,
                1
            ),

            "charging":
                battery.power_plugged
        }

    except Exception as e:

        logger.warning(
            f"Battery information unavailable: {e}"
        )

        return {
            "percent": None,
            "charging": None
        }


# =========================================================
# UPTIME
# =========================================================

def get_uptime():

    try:

        uptime_seconds = int(
            time.time() - psutil.boot_time()
        )

        days = uptime_seconds // 86400

        hours = (
            uptime_seconds % 86400
        ) // 3600

        minutes = (
            uptime_seconds % 3600
        ) // 60

        return (
            f"{days}d "
            f"{hours}h "
            f"{minutes}m"
        )

    except Exception:

        return "N/A"


# =========================================================
# COLLECT ALL DATA
# =========================================================

def collect_data():

    hostname = socket.gethostname()

    # -----------------------------------------
    # Existing monitoring
    # -----------------------------------------

    disk_percent, disk_free = get_disk()

    cpu_usage = get_cpu()

    ram_usage = get_ram()

    # -----------------------------------------
    # New hardware information
    # -----------------------------------------

    cpu_info = get_cpu_info()

    ram_info = get_ram_info()

    gpu_info = get_gpu_info()

    storage_info = get_storage_info()

    system_info = get_system_info()

    battery_info = get_battery_info()

    # -----------------------------------------
    # Calculate storage used
    # -----------------------------------------

    storage_total = storage_info["total"]

    if storage_total > 0:

        storage_used = round(
            (
                disk_percent / 100
            ) * storage_total,
            2
        )

    else:

        storage_used = 0.0

    # -----------------------------------------
    # Final data
    # -----------------------------------------

    data = {

        # =========================
        # EXISTING DATA
        # =========================

        "computer_name":
            hostname,

        "ip_address":
            get_ip(),

        "cpu_usage":
            cpu_usage,

        "ram_usage":
            ram_usage,

        "disk_usage":
            disk_percent,

        "disk_free":
            disk_free,

        "uptime":
            get_uptime(),

        "operating_system":
            platform.system()
            + " "
            + platform.release(),

        # =========================
        # CPU HARDWARE
        # =========================

        "cpu_model":
            cpu_info["model"],

        "cpu_cores":
            cpu_info["cores"],

        "cpu_threads":
            cpu_info["threads"],

        # =========================
        # RAM HARDWARE
        # =========================

        "ram_total":
            ram_info["total"],

        "ram_used":
            ram_info["used"],

        "ram_available":
            ram_info["available"],

        # =========================
        # GPU
        # =========================

        "gpu_model":
            gpu_info["model"],

        "gpu_vram":
            gpu_info["vram"],

        # GPU usage will be added
        # separately later.

        "gpu_usage":
            0.0,

        # =========================
        # STORAGE
        # =========================

        "storage_model":
            storage_info["model"],

        "storage_type":
            storage_info["type"],

        "storage_total":
            storage_total,

        "storage_used":
            storage_used,

        # =========================
        # SYSTEM
        # =========================

        "manufacturer":
            system_info["manufacturer"],

        "system_model":
            system_info["model"],

        "motherboard":
            system_info["motherboard"],

        "bios_version":
            system_info["bios"],

        "architecture":
            platform.architecture()[0],

        # =========================
        # BATTERY
        # =========================

        "battery_percent":
            battery_info["percent"],

        "battery_charging":
            battery_info["charging"]
    }

    return data


# =========================================================
# SEND DATA TO FLASK
# =========================================================

def send_data(data):

    try:

        response = requests.post(
            SERVER_URL,
            json=data,
            timeout=10
        )

        if response.status_code == 200:

            logger.info(
                "Data sent successfully"
            )

            return True

        logger.error(
            f"Server error: "
            f"{response.status_code} "
            f"- {response.text}"
        )

        return False

    except requests.exceptions.RequestException as e:

        logger.error(
            f"Connection error: {e}"
        )

        return False


# =========================================================
# MAIN
# =========================================================

def main():

    logger.info("=" * 60)

    logger.info(
        "NexusCore Monitoring Agent"
    )

    logger.info("=" * 60)

    logger.info(
        f"Computer: "
        f"{socket.gethostname()}"
    )

    logger.info(
        f"IP: {get_ip()}"
    )

    logger.info(
        f"Server: {SERVER_URL}"
    )

    logger.info("=" * 60)

    while True:

        try:

            data = collect_data()

            # ---------------------------------
            # Monitoring log
            # ---------------------------------

            logger.info(
                f"CPU: "
                f"{data['cpu_usage']}% | "
                f"RAM: "
                f"{data['ram_usage']}% | "
                f"Disk: "
                f"{data['disk_usage']}% | "
                f"Free: "
                f"{data['disk_free']}"
            )

            # ---------------------------------
            # Hardware log
            # ---------------------------------

            logger.info(
                f"CPU Model: "
                f"{data['cpu_model']}"
            )

            logger.info(
                f"CPU Cores: "
                f"{data['cpu_cores']} | "
                f"Threads: "
                f"{data['cpu_threads']}"
            )

            logger.info(
                f"RAM: "
                f"{data['ram_total']} GB | "
                f"Used: "
                f"{data['ram_used']} GB | "
                f"Available: "
                f"{data['ram_available']} GB"
            )

            logger.info(
                f"GPU: "
                f"{data['gpu_model']} | "
                f"VRAM: "
                f"{data['gpu_vram']} GB"
            )

            logger.info(
                f"Storage: "
                f"{data['storage_model']} | "
                f"{data['storage_type']} | "
                f"{data['storage_total']} GB"
            )

            logger.info(
                f"System: "
                f"{data['manufacturer']} "
                f"{data['system_model']}"
            )

            logger.info(
                f"Motherboard: "
                f"{data['motherboard']}"
            )

            logger.info(
                f"BIOS: "
                f"{data['bios_version']}"
            )

            logger.info(
                f"Battery: "
                f"{data['battery_percent']}% | "
                f"Charging: "
                f"{data['battery_charging']}"
            )

            # ---------------------------------
            # Send to server
            # ---------------------------------

            send_data(data)

        except KeyboardInterrupt:

            logger.info(
                "Agent stopped by user"
            )

            break

        except Exception as e:

            logger.error(
                f"Unexpected error: {e}"
            )

        time.sleep(
            AGENT_INTERVAL
        )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()

