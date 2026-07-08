from typing import Dict, List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QAbstractItemView,
)

from ui.widgets import MetricCard, SectionFrame


class RealtimePage(QWidget):
    start_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()
    fullscreen_requested = pyqtSignal()
    snapshot_requested = pyqtSignal()

    def __init__(self, models: List[Dict], parent=None) -> None:
        super().__init__(parent)
        self.models = models
        self.class_rows: Dict[str, int] = {}

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("REAL-TIME INSPECTION")
        title.setObjectName("PageTitle")
        self.model_combo = QComboBox()
        for model in models:
            self.model_combo.addItem(model["display_name"], model["key"])
        self.camera_status = QLabel("CAMERA  STANDBY")
        self.camera_status.setObjectName("StatusChip")
        self.infer_status = QLabel("INFERENCE  IDLE")
        self.infer_status.setObjectName("StatusChip")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("MODEL"))
        header.addWidget(self.model_combo)
        header.addWidget(self.camera_status)
        header.addWidget(self.infer_status)
        main.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(12)

        display_frame = SectionFrame("Inspection View")
        self.display = QLabel("等待启动推理画面")
        self.display.setAlignment(Qt.AlignCenter)
        self.display.setMinimumSize(720, 460)
        self.display.setObjectName("VideoDisplay")
        display_frame.add_widget(self.display, 1)
        content.addWidget(display_frame, 7)

        side = QVBoxLayout()
        side.setSpacing(10)
        self.result_card = MetricCard("Detection Result", "STANDBY", "尚未接收检测结果")
        self.fps_card = MetricCard("Frame Rate", "-- FPS", "实时推理帧率")
        side.addWidget(self.result_card)
        side.addWidget(self.fps_card)

        class_frame = SectionFrame("Class Counter")
        self.class_table = QTableWidget(0, 2)
        self.class_table.setHorizontalHeaderLabels(["类别名称", "数量"])
        self.class_table.verticalHeader().setVisible(False)
        self.class_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.class_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.class_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.class_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.class_table.setMinimumHeight(240)
        self.class_table.setWordWrap(False)
        class_frame.add_widget(self.class_table)
        side.addWidget(class_frame, 1)
        side.addStretch()
        content.addLayout(side, 3)
        main.addLayout(content, 1)

        bottom = QHBoxLayout()
        self.start_btn = QPushButton("启动推理")
        self.start_btn.setObjectName("PrimaryButton")
        self.stop_btn = QPushButton("停止推理")
        self.snapshot_btn = QPushButton("保存截图")
        self.fullscreen_btn = QPushButton("全屏显示")

        bottom.addWidget(self.start_btn)
        bottom.addWidget(self.stop_btn)
        bottom.addWidget(self.snapshot_btn)
        bottom.addWidget(self.fullscreen_btn)
        bottom.addStretch()
        main.addLayout(bottom)

        preview = QGridLayout()
        preview.setSpacing(10)
        self.cpu_preview = MetricCard("CPU Total", "0%")
        self.npu_preview = MetricCard("NPU Load", "N/A")
        self.temp_preview = MetricCard("NPU Temperature", "N/A")
        self.memory_preview = MetricCard("Memory", "0%")
        preview.addWidget(self.cpu_preview, 0, 0)
        preview.addWidget(self.npu_preview, 0, 1)
        preview.addWidget(self.temp_preview, 0, 2)
        preview.addWidget(self.memory_preview, 0, 3)
        main.addLayout(preview)

        self.start_btn.clicked.connect(
            lambda: self.start_requested.emit(self.model_combo.currentData())
        )
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.fullscreen_btn.clicked.connect(self.fullscreen_requested.emit)
        self.snapshot_btn.clicked.connect(self.snapshot_requested.emit)
        self.model_combo.currentIndexChanged.connect(self._rebuild_class_labels)
        self._rebuild_class_labels()

    def update_models(self, models: List[Dict]) -> None:
        current = self.model_combo.currentData()
        self.models = models
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in models:
            self.model_combo.addItem(model["display_name"], model["key"])
        index = self.model_combo.findData(current)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)
        self._rebuild_class_labels()

    def _rebuild_class_labels(self) -> None:
        self.class_rows = {}
        current_key = self.model_combo.currentData()
        model = next((m for m in self.models if m["key"] == current_key), None)
        classes = model.get("classes", []) if model else []

        self.class_table.setRowCount(len(classes))
        for row, name in enumerate(classes):
            name_item = QTableWidgetItem(str(name))
            name_item.setToolTip(str(name))
            value_item = QTableWidgetItem("0")
            value_item.setTextAlignment(Qt.AlignCenter)
            self.class_table.setItem(row, 0, name_item)
            self.class_table.setItem(row, 1, value_item)
            self.class_rows[str(name)] = row

    def set_frame(self, frame) -> None:
        if frame is None:
            return
        h, w, ch = frame.shape
        image = QImage(frame.data, w, h, ch * w, QImage.Format_BGR888).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.display.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.display.setPixmap(pixmap)

    def set_infer_status(self, text: str, running: bool = False) -> None:
        self.infer_status.setText(f"INFERENCE  {text.upper()}")
        self.camera_status.setText("CAMERA  ONLINE" if running else "CAMERA  STANDBY")
        if not running and text.lower() in ("待机", "idle"):
            self.result_card.set_value("STANDBY", "尚未接收检测结果")

    def update_infer_metrics(self, metrics: Dict) -> None:
        self.fps_card.set_value(f"{metrics.get('fps', 0):.2f} FPS")

    def update_detection(self, meta: Dict) -> None:
        counts = meta.get("class_counts", {}) or {}
        total = int(meta.get("defect_count", 0))

        self.result_card.set_value(
            "ABNORMAL" if total > 0 else "NORMAL",
            f"当前帧检测到 {total} 个缺陷目标" if total > 0 else "当前帧未检测到缺陷",
        )

        for name, row in self.class_rows.items():
            item = self.class_table.item(row, 1)
            if item:
                item.setText(str(counts.get(name, 0)))

    def update_resource_preview(self, data: Dict) -> None:
        npu_load = data.get("npu_total_load")
        if npu_load is None:
            loads = [v for v in data.get("npu_loads", []) if v is not None]
            npu_load = sum(loads) / len(loads) if loads else None

        self.cpu_preview.set_value(f"{data.get('cpu_total', 0):.0f}%")
        self.npu_preview.set_value("N/A" if npu_load is None else f"{npu_load:.0f}%")
        npu_temp = data.get("npu_temp")
        self.temp_preview.set_value("N/A" if npu_temp is None else f"{npu_temp:.0f} ℃")
        self.memory_preview.set_value(f"{data.get('memory_percent', 0):.0f}%")
