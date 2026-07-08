from typing import Optional

from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.widgets import CoreUsageWidget, LineChart, MetricCard, SectionFrame


def _fmt_percent(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.0f}%"


def _fmt_temp(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.0f} ℃"


def _fmt_freq(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.0f} MHz"


def _numeric(value: Optional[float]) -> float:
    return 0.0 if value is None else float(value)


class ResourcePage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)

        title = QLabel("SYSTEM RESOURCES")
        title.setObjectName("PageTitle")
        main.addWidget(title)

        top = QHBoxLayout()
        cpu_frame = SectionFrame("CPU Core Load")
        cpu_grid = QGridLayout()
        cpu_grid.setSpacing(8)
        self.cpu_widgets = []
        for i in range(8):
            widget = CoreUsageWidget(i)
            self.cpu_widgets.append(widget)
            cpu_grid.addWidget(widget, i // 4, i % 4)
        cpu_container = QWidget()
        cpu_container.setLayout(cpu_grid)
        cpu_frame.add_widget(cpu_container)
        top.addWidget(cpu_frame, 7)

        npu_frame = SectionFrame("NPU Direct Monitor")
        npu_grid = QGridLayout()
        npu_grid.setSpacing(10)
        self.npu_load_cards = [
            MetricCard("NPU CORE 0", "N/A", "rknpu/load"),
            MetricCard("NPU CORE 1", "N/A", "rknpu/load"),
            MetricCard("NPU CORE 2", "N/A", "rknpu/load"),
        ]
        self.npu_freq = MetricCard("NPU Frequency", "N/A", "cur_freq")
        self.npu_temp = MetricCard("NPU Temperature", "N/A", "独立NPU温度节点")
        self.npu_total = MetricCard("NPU Total Load", "N/A", "core average")
        for i, card in enumerate(self.npu_load_cards):
            npu_grid.addWidget(card, 0, i)
        npu_grid.addWidget(self.npu_total, 1, 0)
        npu_grid.addWidget(self.npu_freq, 1, 1)
        npu_grid.addWidget(self.npu_temp, 1, 2)
        npu_container = QWidget()
        npu_container.setLayout(npu_grid)
        npu_frame.add_widget(npu_container)
        top.addWidget(npu_frame, 6)
        main.addLayout(top)

        cards = QGridLayout()
        cards.setSpacing(10)
        self.cpu_temp = MetricCard("CPU Temperature", "N/A", "NORMAL")
        self.gpu_temp = MetricCard("GPU Temperature", "N/A", "NORMAL")
        self.board_temp = MetricCard("Board Temperature", "N/A", "NORMAL")
        self.memory = MetricCard("Memory Usage", "0%", "0 / 0 GB")
        self.disk = MetricCard("Storage Usage", "0%", "0 / 0 GB")
        self.gpu = MetricCard("GPU Load", "N/A", "N/A")
        self.uptime = MetricCard("System Uptime", "00:00:00", "Load average 0.00")
        for i, card in enumerate(
            (
                self.cpu_temp,
                self.gpu_temp,
                self.board_temp,
                self.memory,
                self.disk,
                self.gpu,
                self.uptime,
            )
        ):
            cards.addWidget(card, i // 4, i % 4)
        main.addLayout(cards)

        charts = QHBoxLayout()
        self.cpu_chart = LineChart("CPU Usage / 60 s")
        self.npu_chart = LineChart("NPU Direct Load / 60 s")
        self.temp_chart = LineChart("NPU Temperature / 60 s", y_max=100)
        charts.addWidget(self.cpu_chart)
        charts.addWidget(self.npu_chart)
        charts.addWidget(self.temp_chart)
        main.addLayout(charts)

    @staticmethod
    def _thermal_state(temp: Optional[float]) -> str:
        if temp is None:
            return "UNAVAILABLE"
        temp = float(temp)
        if temp >= 85:
            return "CRITICAL"
        if temp >= 75:
            return "WARNING"
        if temp >= 65:
            return "ELEVATED"
        return "NORMAL"

    def update_metrics(self, data: dict) -> None:
        cores = list(data.get("cpu_cores", []))
        freqs = list(data.get("cpu_freqs_mhz", []))
        for i, widget in enumerate(self.cpu_widgets):
            usage = cores[i] if i < len(cores) else 0.0
            freq = freqs[i] if i < len(freqs) else 0.0
            widget.set_data(float(usage or 0.0), float(freq or 0.0))

        npu_loads = list(data.get("npu_loads", [None, None, None]))
        npu_sources = list(data.get("npu_load_sources", ["", "", ""]))
        for i, card in enumerate(self.npu_load_cards):
            value = npu_loads[i] if i < len(npu_loads) else None
            source = npu_sources[i] if i < len(npu_sources) and npu_sources[i] else "未配置独立节点"
            card.set_value(_fmt_percent(value), source)

        self.npu_total.set_value(
            _fmt_percent(data.get("npu_total_load")),
            data.get("npu_load_sources", [""])[0] if data.get("npu_load_sources") else "devfreq/load",
        )
        self.npu_freq.set_value(
            _fmt_freq(data.get("npu_freq_mhz")),
            data.get("npu_freq_source", "") or "未发现NPU频率节点",
        )
        self.npu_temp.set_value(
            _fmt_temp(data.get("npu_temp")),
            data.get("npu_temp_source", "") or "未发现独立NPU温度节点",
        )

        for card, key in (
            (self.cpu_temp, "cpu_temp"),
            (self.gpu_temp, "gpu_temp"),
            (self.board_temp, "board_temp"),
        ):
            value = data.get(key)
            card.set_value(_fmt_temp(value), self._thermal_state(value))

        self.memory.set_value(
            f"{data.get('memory_percent', 0):.0f}%",
            f"{data.get('memory_used_gb', 0):.1f} / {data.get('memory_total_gb', 0):.1f} GB",
        )
        self.disk.set_value(
            f"{data.get('disk_percent', 0):.0f}%",
            f"{data.get('disk_used_gb', 0):.1f} / {data.get('disk_total_gb', 0):.1f} GB",
        )
        self.gpu.set_value(
            _fmt_percent(data.get("gpu_usage")),
            _fmt_freq(data.get("gpu_freq_mhz")),
        )

        uptime = int(data.get("uptime_s", 0))
        hours, rem = divmod(uptime, 3600)
        minutes, seconds = divmod(rem, 60)
        self.uptime.set_value(
            f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            f"Load average {data.get('load_avg', 0):.2f}",
        )

        total_npu = data.get("npu_total_load")
        if total_npu is None:
            available = [_numeric(v) for v in npu_loads if v is not None]
            total_npu = sum(available) / len(available) if available else 0.0

        self.cpu_chart.append_value(float(data.get("cpu_total", 0.0) or 0.0))
        self.npu_chart.append_value(float(total_npu or 0.0))
        self.temp_chart.append_value(float(data.get("npu_temp") or 0.0))
