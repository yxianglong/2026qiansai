import glob
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QThread, pyqtSignal

try:
    import psutil
except Exception:
    psutil = None


def _read_text(path: str, default: str = "") -> str:
    try:
        if not path:
            return default
        return Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return default


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _normalize_path_list(value, length: int = 3) -> List[str]:
    if isinstance(value, list):
        items = [str(v) for v in value]
    else:
        items = []
    return (items + [""] * length)[:length]


class ResourceMonitorThread(QThread):
    sig_resource = pyqtSignal(dict)

    def __init__(
        self,
        interval_ms: int = 1000,
        demo_mode: bool = False,
        config: Optional[Dict] = None,
    ) -> None:
        super().__init__()
        self.interval_ms = max(250, int(interval_ms))
        self.demo_mode = demo_mode
        self.config = config or {}
        self._running = False
        self._prev_cpu: List[Tuple[int, int]] = []
        self._prepare_privileged_read_paths()

    def stop(self) -> None:
        self._running = False

    def update_config(self, config: Dict) -> None:
        self.config = config or {}
        self._prepare_privileged_read_paths()

    def _prepare_privileged_read_paths(self) -> None:
        """
        尝试把调试节点设为当前用户可读。

        说明：
        - /sys/kernel/debug/rknpu/load 是 RK3588 RKNPU 三核心负载的真实接口。
        - 某些系统该节点默认只有 root 可读。
        - 这里使用 sudo -n，不会卡住等待密码；如果系统没有免密sudo，则静默失败，
          后续读取函数仍会尝试普通读取和 sudo -n cat。
        """
        paths = [
            "/sys/kernel/debug/rknpu/load",
        ]

        # cpuinfo_cur_freq 在部分镜像中需要 root 权限，尽量提前放开；
        # 如果失败，程序会自动回退到 scaling_cur_freq。
        paths.extend(glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_cur_freq"))

        for path in paths:
            try:
                if not path or not Path(path).exists():
                    continue
                if os.access(path, os.R_OK):
                    continue

                # root 或具有权限时直接 chmod。
                try:
                    os.chmod(path, 0o444)
                except Exception:
                    pass

                if not os.access(path, os.R_OK):
                    subprocess.run(
                        ["sudo", "-n", "chmod", "444", path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=0.8,
                        check=False,
                    )
            except Exception:
                # 权限准备失败不能影响界面启动。
                continue

    def run(self) -> None:
        self._running = True
        phase = 0.0
        while self._running:
            try:
                metrics = self._demo_metrics(phase) if self.demo_mode else self._collect()
                self.sig_resource.emit(metrics)
            except Exception as exc:
                metrics = self._empty_metrics()
                metrics["monitor_error"] = str(exc)
                self.sig_resource.emit(metrics)
            phase += 0.16
            self.msleep(self.interval_ms)

    def _collect(self) -> Dict:
        cpu_cores, cpu_total = self._cpu_usage()
        cpu_freqs = self._cpu_freqs(len(cpu_cores))
        thermal = self._thermal()
        npu = self._read_npu_direct()
        gpu = self._read_gpu_direct()
        memory = self._memory()
        disk = self._disk()
        uptime = self._uptime()

        cpu_temp_candidates = [
            self._parse_temp_c(_read_text("/sys/class/thermal/thermal_zone0/temp", "")),
            self._parse_temp_c(_read_text("/sys/class/thermal/thermal_zone1/temp", "")),
            thermal.get("cpu"),
            thermal.get("soc"),
        ]
        cpu_temp_values = [float(v) for v in cpu_temp_candidates if v is not None]
        cpu_temp = max(cpu_temp_values) if cpu_temp_values else None

        return {
            "cpu_total": cpu_total,
            "cpu_cores": cpu_cores,
            "cpu_freqs_mhz": cpu_freqs,
            "cpu_temp": cpu_temp,
            "npu_temp": npu.get("npu_temp"),
            "npu_core_temps": npu.get("npu_core_temps", [None, None, None]),
            "gpu_temp": thermal.get("gpu"),
            "board_temp": thermal.get("board") or thermal.get("soc"),

            # 只展示直接读取到的板卡值，不用FPS/延迟估算。
            "npu_loads": npu.get("npu_loads", [None, None, None]),
            "npu_total_load": npu.get("npu_total_load"),
            "npu_freq_mhz": npu.get("npu_freq_mhz"),
            "npu_load_sources": npu.get("npu_load_sources", ["", "", ""]),
            "npu_temp_source": npu.get("npu_temp_source", ""),
            "npu_freq_source": npu.get("npu_freq_source", ""),

            # 兼容旧界面字段。
            "npu_cores": npu.get("npu_loads", [None, None, None]),

            "gpu_usage": gpu.get("gpu_usage"),
            "gpu_freq_mhz": gpu.get("gpu_freq_mhz"),
            "memory_percent": memory["percent"],
            "memory_used_gb": memory["used_gb"],
            "memory_total_gb": memory["total_gb"],
            "disk_percent": disk["percent"],
            "disk_used_gb": disk["used_gb"],
            "disk_total_gb": disk["total_gb"],
            "uptime_s": uptime,
            "load_avg": os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0,
        }

    def _cpu_usage(self) -> Tuple[List[float], float]:
        if psutil is not None:
            per_core = psutil.cpu_percent(interval=None, percpu=True)
            total = psutil.cpu_percent(interval=None)
            return [float(v) for v in per_core], float(total)

        lines = _read_text("/proc/stat").splitlines()
        samples: List[Tuple[int, int]] = []
        for line in lines:
            if not line.startswith("cpu"):
                break
            parts = line.split()
            if parts[0] == "cpu":
                continue
            values = [int(v) for v in parts[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
            samples.append((total, idle))

        if not self._prev_cpu or len(self._prev_cpu) != len(samples):
            self._prev_cpu = samples
            return [0.0] * max(8, len(samples)), 0.0

        usages = []
        for (total, idle), (p_total, p_idle) in zip(samples, self._prev_cpu):
            dt = max(total - p_total, 1)
            di = idle - p_idle
            usages.append(max(0.0, min(100.0, 100.0 * (dt - di) / dt)))
        self._prev_cpu = samples
        return usages, sum(usages) / max(len(usages), 1)

    @staticmethod
    def _cpu_freqs(count: int) -> List[float]:
        """
        读取 CPU 当前频率，单位 MHz。

        优先读取 cpuinfo_cur_freq；如果权限不足或节点不可读，则回退到
        scaling_cur_freq。cpuinfo_cur_freq / scaling_cur_freq 通常单位为 kHz。
        """
        freqs = []
        for idx in range(max(count, 8)):
            cpuinfo_path = f"/sys/devices/system/cpu/cpu{idx}/cpufreq/cpuinfo_cur_freq"
            scaling_path = f"/sys/devices/system/cpu/cpu{idx}/cpufreq/scaling_cur_freq"

            raw = _read_text(cpuinfo_path, "")
            if not raw:
                raw = _read_text(scaling_path, "0")

            value = _safe_float(raw)
            if value > 10000:
                value = value / 1000.0
            freqs.append(value)

        return freqs

    @staticmethod
    def _memory() -> Dict[str, float]:
        if psutil is not None:
            vm = psutil.virtual_memory()
            return {
                "percent": float(vm.percent),
                "used_gb": vm.used / (1024**3),
                "total_gb": vm.total / (1024**3),
            }

        info = {}
        for line in _read_text("/proc/meminfo").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                info[key] = _safe_float(value.split()[0])
        total = info.get("MemTotal", 0.0) * 1024
        available = info.get("MemAvailable", 0.0) * 1024
        used = max(0.0, total - available)
        percent = 100.0 * used / total if total else 0.0
        return {
            "percent": percent,
            "used_gb": used / (1024**3),
            "total_gb": total / (1024**3),
        }

    @staticmethod
    def _disk() -> Dict[str, float]:
        total, used, _ = shutil.disk_usage("/")
        return {
            "percent": 100.0 * used / total if total else 0.0,
            "used_gb": used / (1024**3),
            "total_gb": total / (1024**3),
        }

    @staticmethod
    def _uptime() -> float:
        text = _read_text("/proc/uptime", "0")
        return _safe_float(text.split()[0] if text else "0")

    @staticmethod
    def _parse_load(text: str) -> Optional[float]:
        if not text:
            return None
        token = text.strip().split("@")[0].split()[0].replace("%", "")
        try:
            return max(0.0, min(100.0, float(token)))
        except Exception:
            return None

    @staticmethod
    def _parse_freq_mhz(text: str) -> Optional[float]:
        if not text:
            return None
        token = text.strip().lower().replace("hz", "")
        value = _safe_float(token, -1.0)
        if value < 0:
            return None
        if value > 1_000_000:
            return value / 1_000_000.0
        if value > 10_000:
            return value / 1000.0
        return value

    @staticmethod
    def _parse_temp_c(text: str) -> Optional[float]:
        if not text:
            return None
        value = _safe_float(text.split()[0], -9999.0)
        if value == -9999.0:
            return None
        if value > 1000:
            value /= 1000.0
        return value

    @staticmethod
    def _read_text_with_sudo_fallback(path: str, default: str = "") -> str:
        """
        读取可能需要权限的 sysfs/debugfs 节点。

        先普通读取；失败后使用 sudo -n cat 尝试读取。sudo -n 不会弹出密码输入，
        因此不会卡住 Qt 界面。若系统没有配置免密sudo，则返回 default。
        """
        if not path:
            return default

        text = _read_text(path, "")
        if text:
            return text

        try:
            proc = subprocess.run(
                ["sudo", "-n", "cat", path],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=0.8,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            pass

        return default

    def _read_rknpu_core_loads(self, path: str = "/sys/kernel/debug/rknpu/load") -> Tuple[List[Optional[float]], str]:
        """
        读取 RK3588 RKNPU debugfs 三核心负载。

        示例输出：
        NPU load:  Core0: 10%, Core1: 10%, Core2:  5%,
        """
        text = self._read_text_with_sudo_fallback(path, "")
        if not text:
            return [None, None, None], ""

        matches = re.findall(
            r"Core\s*([0-2])\s*:\s*([0-9.]+)\s*%",
            text,
            flags=re.IGNORECASE,
        )
        if not matches:
            return [None, None, None], ""

        loads: List[Optional[float]] = [None, None, None]
        for core_id, value in matches:
            idx = int(core_id)
            loads[idx] = max(0.0, min(100.0, _safe_float(value)))

        return loads, path


    def _thermal(self) -> Dict[str, Optional[float]]:
        result: Dict[str, Optional[float]] = {}
        for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
            zone_type = _read_text(f"{zone}/type", "unknown").lower()
            temp = self._parse_temp_c(_read_text(f"{zone}/temp", ""))
            if temp is None:
                continue

            if any(k in zone_type for k in ("cpu", "cluster")):
                result["cpu"] = max(result.get("cpu") or 0.0, temp)
            elif "npu" in zone_type:
                result["npu"] = max(result.get("npu") or 0.0, temp)
            elif "gpu" in zone_type:
                result["gpu"] = max(result.get("gpu") or 0.0, temp)
            elif any(k in zone_type for k in ("soc", "package")):
                result["soc"] = max(result.get("soc") or 0.0, temp)
            elif any(k in zone_type for k in ("board", "ambient")):
                result["board"] = max(result.get("board") or 0.0, temp)
        return result

    def _resource_paths(self) -> Dict:
        return self.config.get("resource_paths", {}) if isinstance(self.config, dict) else {}

    def _read_npu_direct(self) -> Dict:
        paths = self._resource_paths()
        core_load_paths = _normalize_path_list(paths.get("npu_core_loads", []), 3)
        core_temp_paths = _normalize_path_list(paths.get("npu_core_temps", []), 3)

        load_sources = ["", "", ""]
        loads: List[Optional[float]] = [None, None, None]
        temps: List[Optional[float]] = [None, None, None]

        # 1. 优先读取 RK3588 RKNPU debugfs 三核心真实负载。
        debug_load_path = str(paths.get("rknpu_debug_load", "") or "/sys/kernel/debug/rknpu/load")
        debug_loads, debug_source = self._read_rknpu_core_loads(debug_load_path)
        if any(v is not None for v in debug_loads):
            loads = debug_loads
            load_sources = [debug_source, debug_source, debug_source]

        # 2. 如果 debugfs 不可读，再读取用户在系统设置中指定的三核心负载路径。
        if not any(v is not None for v in loads):
            for i, path in enumerate(core_load_paths):
                if path:
                    loads[i] = self._parse_load(self._read_text_with_sudo_fallback(path, ""))
                    load_sources[i] = path

        # 3. 如果仍没有三核心路径，只保留板卡暴露的NPU总负载，不复制、不推测。
        total_load = None
        total_load_path = str(paths.get("npu_load_total", "") or "")
        if total_load_path:
            total_load = self._parse_load(_read_text(total_load_path, ""))
            if loads[0] is None:
                loads[0] = total_load
                load_sources[0] = total_load_path

        if total_load is None:
            # 自动查找 npu/rknpu devfreq 节点。
            for node in glob.glob("/sys/class/devfreq/*"):
                node_name = Path(node).name.lower()
                name_file = _read_text(f"{node}/name", "").lower()
                dev_name = f"{node_name} {name_file}"
                if "npu" in dev_name or "rknpu" in dev_name or "fdab0000" in dev_name:
                    path = f"{node}/load"
                    total_load = self._parse_load(_read_text(path, ""))
                    if loads[0] is None:
                        loads[0] = total_load
                        load_sources[0] = path
                    break

        # 如果能读取到三核心负载，用三核心平均值作为总负载，避免使用固定100的devfreq值。
        valid_loads = [float(v) for v in loads if v is not None]
        if valid_loads:
            total_load = sum(valid_loads) / len(valid_loads)

        # NPU频率：只读 cur_freq 或用户指定路径。
        freq_source = str(paths.get("npu_freq", "") or "")
        npu_freq_mhz = None
        if freq_source:
            npu_freq_mhz = self._parse_freq_mhz(_read_text(freq_source, ""))
        if npu_freq_mhz is None:
            for node in glob.glob("/sys/class/devfreq/*"):
                node_name = Path(node).name.lower()
                name_file = _read_text(f"{node}/name", "").lower()
                dev_name = f"{node_name} {name_file}"
                if "npu" in dev_name or "rknpu" in dev_name or "fdab0000" in dev_name:
                    freq_source = f"{node}/cur_freq"
                    npu_freq_mhz = self._parse_freq_mhz(_read_text(freq_source, ""))
                    break

        # NPU温度：只读用户指定的NPU温度路径或名称中含npu的thermal zone。
        temp_source = str(paths.get("npu_temp", "") or "")
        npu_temp = None
        if temp_source:
            npu_temp = self._parse_temp_c(_read_text(temp_source, ""))

        for i, path in enumerate(core_temp_paths):
            if path:
                temps[i] = self._parse_temp_c(_read_text(path, ""))

        if npu_temp is None:
            for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
                zone_type = _read_text(f"{zone}/type", "").lower()
                if "npu" in zone_type:
                    temp_source = f"{zone}/temp"
                    npu_temp = self._parse_temp_c(_read_text(temp_source, ""))
                    break

        return {
            "npu_loads": loads,
            "npu_total_load": total_load,
            "npu_freq_mhz": npu_freq_mhz,
            "npu_temp": npu_temp,
            "npu_core_temps": temps,
            "npu_load_sources": load_sources,
            "npu_freq_source": freq_source,
            "npu_temp_source": temp_source,
        }

    def _read_gpu_direct(self) -> Dict[str, Optional[float]]:
        result = {"gpu_usage": None, "gpu_freq_mhz": None}
        for node in glob.glob("/sys/class/devfreq/*"):
            node_name = Path(node).name.lower()
            name_file = _read_text(f"{node}/name", "").lower()
            dev_name = f"{node_name} {name_file}"
            if "gpu" in dev_name or "mali" in dev_name:
                result["gpu_usage"] = self._parse_load(_read_text(f"{node}/load", ""))
                result["gpu_freq_mhz"] = self._parse_freq_mhz(_read_text(f"{node}/cur_freq", ""))
                break
        return result

    @staticmethod
    def _empty_metrics() -> Dict:
        return {
            "cpu_total": 0.0,
            "cpu_cores": [0.0] * 8,
            "cpu_freqs_mhz": [0.0] * 8,
            "cpu_temp": None,
            "npu_temp": None,
            "npu_core_temps": [None, None, None],
            "gpu_temp": None,
            "board_temp": None,
            "npu_loads": [None, None, None],
            "npu_cores": [None, None, None],
            "npu_total_load": None,
            "npu_freq_mhz": None,
            "npu_load_sources": ["", "", ""],
            "npu_temp_source": "",
            "npu_freq_source": "",
            "gpu_usage": None,
            "gpu_freq_mhz": None,
            "memory_percent": 0.0,
            "memory_used_gb": 0.0,
            "memory_total_gb": 0.0,
            "disk_percent": 0.0,
            "disk_used_gb": 0.0,
            "disk_total_gb": 0.0,
            "uptime_s": 0.0,
            "load_avg": 0.0,
        }

    def _demo_metrics(self, phase: float) -> Dict:
        import math

        cpu = [35 + 28 * abs(math.sin(phase + i * 0.43)) for i in range(8)]
        npu = [58 + 22 * abs(math.sin(phase * 0.8 + i * 0.8)) for i in range(3)]
        return {
            "cpu_total": sum(cpu) / len(cpu),
            "cpu_cores": cpu,
            "cpu_freqs_mhz": [1416, 1416, 1608, 1608, 2016, 2016, 2256, 2256],
            "cpu_temp": 54 + 7 * abs(math.sin(phase * 0.45)),
            "npu_temp": 57 + 8 * abs(math.sin(phase * 0.37)),
            "npu_core_temps": [57 + i + 3 * abs(math.sin(phase + i)) for i in range(3)],
            "gpu_temp": 50 + 6 * abs(math.sin(phase * 0.52)),
            "board_temp": 45 + 4 * abs(math.sin(phase * 0.33)),
            "npu_loads": npu,
            "npu_cores": npu,
            "npu_total_load": sum(npu) / len(npu),
            "npu_freq_mhz": 1000.0,
            "npu_load_sources": ["demo", "demo", "demo"],
            "npu_temp_source": "demo",
            "npu_freq_source": "demo",
            "gpu_usage": 24 + 18 * abs(math.sin(phase)),
            "gpu_freq_mhz": 800.0,
            "memory_percent": 43 + 4 * abs(math.sin(phase * 0.3)),
            "memory_used_gb": 6.8,
            "memory_total_gb": 16.0,
            "disk_percent": 62.0,
            "disk_used_gb": 78.0,
            "disk_total_gb": 126.0,
            "uptime_s": 7 * 3600 + phase * 10,
            "load_avg": 2.18,
        }
