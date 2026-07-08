from copy import deepcopy
from typing import Dict, List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    settings_saved = pyqtSignal(dict)

    def __init__(self, config: dict, models: List[Dict], parent=None) -> None:
        super().__init__(parent)
        self.config = deepcopy(config)
        self.models = models

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)

        title = QLabel("SYSTEM SETTINGS")
        title.setObjectName("PageTitle")
        main.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(12)

        camera_group = QGroupBox("摄像头设置")
        camera_form = QFormLayout(camera_group)
        self.camera_dev = QLineEdit()
        self.camera_width = QSpinBox()
        self.camera_width.setRange(320, 7680)
        self.camera_height = QSpinBox()
        self.camera_height.setRange(240, 4320)
        camera_form.addRow("设备节点", self.camera_dev)
        camera_form.addRow("宽度", self.camera_width)
        camera_form.addRow("高度", self.camera_height)
        grid.addWidget(camera_group, 0, 0)

        infer_group = QGroupBox("推理设置")
        infer_form = QFormLayout(infer_group)
        self.default_model = QComboBox()
        for model in models:
            self.default_model.addItem(model.get("display_name", model.get("name", "")), model.get("key", ""))
        self.tpes = QSpinBox()
        self.tpes.setRange(1, 12)
        self.conf = QDoubleSpinBox()
        self.conf.setRange(0.01, 0.99)
        self.conf.setSingleStep(0.01)
        self.conf.setDecimals(2)
        self.nms = QDoubleSpinBox()
        self.nms.setRange(0.01, 0.99)
        self.nms.setSingleStep(0.01)
        self.nms.setDecimals(2)
        self.auto_start = QCheckBox("程序启动后自动运行默认模型")
        self.auto_save = QCheckBox("检测到缺陷时自动保存截图")
        infer_form.addRow("默认模型", self.default_model)
        infer_form.addRow("RKNN TPE数量", self.tpes)
        infer_form.addRow("置信度阈值", self.conf)
        infer_form.addRow("NMS 阈值", self.nms)
        infer_form.addRow(self.auto_start)
        infer_form.addRow(self.auto_save)
        grid.addWidget(infer_group, 0, 1)

        alarm_group = QGroupBox("告警阈值")
        alarm_form = QFormLayout(alarm_group)
        self.cpu_warning = QSpinBox()
        self.cpu_warning.setRange(40, 120)
        self.npu_warning = QSpinBox()
        self.npu_warning.setRange(40, 120)
        self.memory_warning = QSpinBox()
        self.memory_warning.setRange(40, 100)
        self.fps_warning = QSpinBox()
        self.fps_warning.setRange(1, 120)
        alarm_form.addRow("CPU 温度", self.cpu_warning)
        alarm_form.addRow("NPU 温度", self.npu_warning)
        alarm_form.addRow("内存占用", self.memory_warning)
        alarm_form.addRow("FPS 下限", self.fps_warning)
        grid.addWidget(alarm_group, 0, 2)

        npu_group = QGroupBox("NPU 直接读取路径")
        npu_form = QFormLayout(npu_group)
        self.npu_total_load_path = QLineEdit()
        self.npu_freq_path = QLineEdit()
        self.npu_temp_path = QLineEdit()
        self.npu_core_load_paths = [QLineEdit() for _ in range(3)]
        self.npu_core_temp_paths = [QLineEdit() for _ in range(3)]
        npu_form.addRow("NPU总负载", self.npu_total_load_path)
        npu_form.addRow("NPU频率", self.npu_freq_path)
        npu_form.addRow("NPU温度", self.npu_temp_path)
        for i, edit in enumerate(self.npu_core_load_paths):
            npu_form.addRow(f"NPU负载{i}", edit)
        for i, edit in enumerate(self.npu_core_temp_paths):
            npu_form.addRow(f"NPU温度{i}", edit)
        grid.addWidget(npu_group, 1, 0, 1, 3)

        main.addLayout(grid)
        note = QLabel(
            "说明：系统资源页只显示这里配置或系统自动发现的板卡原始数据。"
            "若某个NPU核心负载/温度没有独立sysfs节点，将显示 N/A，不进行推测。"
        )
        note.setObjectName("SmallMuted")
        note.setWordWrap(True)
        main.addWidget(note)
        main.addStretch()

        actions = QHBoxLayout()
        self.reload_btn = QPushButton("从配置重新载入")
        self.save_btn = QPushButton("保存并应用")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setFixedWidth(140)
        actions.addStretch()
        actions.addWidget(self.reload_btn)
        actions.addWidget(self.save_btn)
        main.addLayout(actions)

        self.default_model.currentIndexChanged.connect(self._load_model_tpes)
        self.reload_btn.clicked.connect(lambda: self.load_config(self.config, self.models))
        self.save_btn.clicked.connect(self._emit_save)
        self.load_config(self.config, self.models)

    def load_config(self, config: dict, models: List[Dict]) -> None:
        self.config = deepcopy(config)
        self.models = models
        self.default_model.blockSignals(True)
        self.default_model.clear()
        for model in models:
            self.default_model.addItem(model.get("display_name", model.get("name", "")), model.get("key", ""))
        default_key = config.get("runtime", {}).get("default_model", models[0].get("key", "") if models else "")
        index = self.default_model.findData(default_key)
        self.default_model.setCurrentIndex(index if index >= 0 else 0)
        self.default_model.blockSignals(False)

        camera = config.get("camera", {})
        self.camera_dev.setText(camera.get("device", "/dev/video12"))
        self.camera_width.setValue(int(camera.get("width", 1920)))
        self.camera_height.setValue(int(camera.get("height", 1080)))

        thresholds = config.get("thresholds", {})
        self.conf.setValue(float(thresholds.get("confidence", 0.25)))
        self.nms.setValue(float(thresholds.get("nms", 0.45)))
        self.cpu_warning.setValue(int(thresholds.get("cpu_warning", 75)))
        self.npu_warning.setValue(int(thresholds.get("npu_warning", 80)))
        self.memory_warning.setValue(int(thresholds.get("memory_warning", 85)))
        self.fps_warning.setValue(int(thresholds.get("fps_warning", 15)))

        runtime = config.get("runtime", {})
        storage = config.get("storage", {})
        self.auto_start.setChecked(bool(runtime.get("auto_start", False)))
        self.auto_save.setChecked(bool(storage.get("auto_save_on_defect", False)))

        paths = config.get("resource_paths", {})
        self.npu_total_load_path.setText(paths.get("npu_load_total", "/sys/class/devfreq/fdab0000.npu/load"))
        self.npu_freq_path.setText(paths.get("npu_freq", "/sys/class/devfreq/fdab0000.npu/cur_freq"))
        self.npu_temp_path.setText(paths.get("npu_temp", ""))

        core_loads = list(paths.get("npu_core_loads", ["", "", ""]))
        core_temps = list(paths.get("npu_core_temps", ["", "", ""]))
        core_loads = (core_loads + ["", "", ""])[:3]
        core_temps = (core_temps + ["", "", ""])[:3]
        for i in range(3):
            self.npu_core_load_paths[i].setText(core_loads[i])
            self.npu_core_temp_paths[i].setText(core_temps[i])

        self._load_model_tpes()

    def _load_model_tpes(self) -> None:
        key = self.default_model.currentData()
        model = next((m for m in self.models if m.get("key") == key), None)
        self.tpes.setValue(int(model.get("tpes", 8)) if model else 8)

    def _emit_save(self) -> None:
        new_config = deepcopy(self.config)
        new_config.setdefault("camera", {})
        new_config["camera"]["device"] = self.camera_dev.text().strip() or "/dev/video12"
        new_config["camera"]["width"] = int(self.camera_width.value())
        new_config["camera"]["height"] = int(self.camera_height.value())

        new_config.setdefault("thresholds", {})
        new_config["thresholds"]["confidence"] = float(self.conf.value())
        new_config["thresholds"]["nms"] = float(self.nms.value())
        new_config["thresholds"]["cpu_warning"] = int(self.cpu_warning.value())
        new_config["thresholds"]["npu_warning"] = int(self.npu_warning.value())
        new_config["thresholds"]["memory_warning"] = int(self.memory_warning.value())
        new_config["thresholds"]["fps_warning"] = int(self.fps_warning.value())

        new_config.setdefault("runtime", {})
        new_config["runtime"]["default_model"] = self.default_model.currentData()
        new_config["runtime"]["auto_start"] = bool(self.auto_start.isChecked())

        new_config.setdefault("storage", {})
        new_config["storage"]["auto_save_on_defect"] = bool(self.auto_save.isChecked())

        new_config.setdefault("resource_paths", {})
        new_config["resource_paths"]["npu_load_total"] = self.npu_total_load_path.text().strip()
        new_config["resource_paths"]["npu_freq"] = self.npu_freq_path.text().strip()
        new_config["resource_paths"]["npu_temp"] = self.npu_temp_path.text().strip()
        new_config["resource_paths"]["npu_core_loads"] = [e.text().strip() for e in self.npu_core_load_paths]
        new_config["resource_paths"]["npu_core_temps"] = [e.text().strip() for e in self.npu_core_temp_paths]

        key = self.default_model.currentData()
        for model in new_config.get("models", []):
            if model.get("key") == key:
                model["tpes"] = int(self.tpes.value())

        self.config = deepcopy(new_config)
        self.settings_saved.emit(new_config)
