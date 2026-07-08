import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import cv2
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.history_store import HistoryStore
from core.infer import DemoInferThread, RKNNInferThread
from core.resource_monitor import ResourceMonitorThread
from ui.pages.alarm import AlarmPage
from ui.pages.history import HistoryPage
from ui.pages.realtime import RealtimePage
from ui.pages.resource import ResourcePage
from ui.pages.settings import SettingsPage
from ui.pages.statistics import StatisticsPage


class MainWindow(QMainWindow):
    NAV_ITEMS = [
        ("实时检测", "RT"),
        ("系统资源", "SYS"),
        ("统计分析", "STA"),
        ("历史记录", "HIS"),
        ("告警中心", "ALM"),
        ("系统设置", "SET"),
    ]

    def __init__(self, demo_mode: bool = False) -> None:
        super().__init__()
        self.demo_mode = demo_mode
        self.config_path = Path(__file__).resolve().parents[1] / "config" / "models.json"
        self.config = self._load_config()
        self.models = self.config.get("models", [])
        self.model_map = {m["key"]: m for m in self.models}
        self.infer_thread = None
        self.last_frame = None
        self.current_model_key: Optional[str] = None
        self._fullscreen = False
        self._last_alarm = {}
        self._last_auto_snapshot_ts = 0.0

        self.setWindowTitle("RK3588 多模型缺陷检测监控平台")
        self.resize(1550, 920)
        self.setMinimumSize(1180, 720)

        self.history_store = HistoryStore()
        self._build_ui()
        self._wire_pages()
        self._start_resource_monitor()
        self._start_clock()
        self._apply_default_model_to_combo()

        if bool(self.config.get("runtime", {}).get("auto_start", False)):
            QTimer.singleShot(1000, self.start_default_inference)

    def _load_config(self) -> Dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def _write_config(self) -> None:
        self.config_path.write_text(
            json.dumps(self.config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar = QFrame()
        self.topbar.setObjectName("TopBar")
        top_layout = QHBoxLayout(self.topbar)
        top_layout.setContentsMargins(24, 0, 24, 0)
        self.brand = QLabel("RK3588  EDGE INSPECTION")
        self.brand.setObjectName("Brand")
        self.clock = QLabel("--:--:--")
        self.clock.setObjectName("Clock")
        top_layout.addWidget(self.brand)
        top_layout.addStretch()
        top_layout.addWidget(self.clock)
        self.topbar.setFixedHeight(58)
        root.addWidget(self.topbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("SideBar")
        self.sidebar.setFixedWidth(184)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(12, 18, 12, 18)
        side_layout.setSpacing(8)

        self.nav_buttons = []
        for index, (name, code) in enumerate(self.NAV_ITEMS):
            btn = QPushButton(f"{code}   {name}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=index: self.switch_page(i))
            side_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        side_layout.addStretch()
        version = QLabel("v1.1.0\nRK3588 / PyQt5")
        version.setObjectName("SmallMuted")
        version.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(version)

        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("PageStack")

        self.realtime_page = RealtimePage(self.models)
        self.resource_page = ResourcePage()
        self.statistics_page = StatisticsPage()
        self.history_page = HistoryPage(self.history_store)
        self.alarm_page = AlarmPage()
        self.settings_page = SettingsPage(self.config, self.models)

        for page in (
            self.realtime_page,
            self.resource_page,
            self.statistics_page,
            self.history_page,
            self.alarm_page,
            self.settings_page,
        ):
            wrapper = QWidget()
            layout = QVBoxLayout(wrapper)
            layout.setContentsMargins(18, 16, 18, 18)
            layout.addWidget(page)
            self.stack.addWidget(wrapper)

        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        self.switch_page(0)

    def _wire_pages(self) -> None:
        self.realtime_page.start_requested.connect(self.start_inference)
        self.realtime_page.stop_requested.connect(self.stop_inference)
        self.realtime_page.fullscreen_requested.connect(self.toggle_fullscreen)
        self.realtime_page.snapshot_requested.connect(self.save_snapshot)
        self.settings_page.settings_saved.connect(self.apply_settings)

    def _start_resource_monitor(self) -> None:
        self.resource_thread = ResourceMonitorThread(
            demo_mode=self.demo_mode,
            config=self.config,
        )
        self.resource_thread.sig_resource.connect(self.on_resource_update)
        self.resource_thread.start()

    def _start_clock(self) -> None:
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(
            lambda: self.clock.setText(datetime.now().strftime("%Y-%m-%d   %H:%M:%S"))
        )
        self.clock_timer.start(1000)
        self.clock_timer.timeout.emit()

    def _apply_default_model_to_combo(self) -> None:
        default_key = self.config.get("runtime", {}).get("default_model")
        if default_key:
            index = self.realtime_page.model_combo.findData(default_key)
            if index >= 0:
                self.realtime_page.model_combo.setCurrentIndex(index)

    def switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def start_default_inference(self) -> None:
        default_key = self.config.get("runtime", {}).get("default_model")
        if default_key:
            self.start_inference(default_key)

    def start_inference(self, model_key: str) -> None:
        if self.infer_thread is not None and self.infer_thread.isRunning():
            QMessageBox.information(self, "提示", "推理线程正在运行，请先停止当前模型。")
            return

        model = self.model_map.get(model_key)
        if not model:
            QMessageBox.warning(self, "错误", "未找到模型配置。")
            return

        self.current_model_key = model_key
        thresholds = self.config.get("thresholds", {})
        camera = self.config.get("camera", {})

        if self.demo_mode:
            thread = DemoInferThread(model["name"], model.get("classes", []))
        else:
            thread = RKNNInferThread(
                model_path=model["path"],
                cls_list=model.get("classes", []),
                video_dev=camera.get("device", "/dev/video12"),
                tpes=model.get("tpes", 8),
                conf_thres=thresholds.get("confidence", 0.25),
                nms_thres=thresholds.get("nms", 0.45),
                camera_width=camera.get("width", 0),
                camera_height=camera.get("height", 0),
            )

        self.infer_thread = thread
        thread.sig_status.connect(self.on_infer_status)
        thread.sig_frame.connect(self.on_frame)
        thread.sig_metrics.connect(self.on_infer_metrics)
        thread.sig_detection.connect(self.on_detection)
        thread.sig_error.connect(self.on_infer_error)
        thread.finished.connect(self.on_infer_finished)
        thread.start()
        self.alarm_page.add_alarm("INFO", f"启动模型：{model['name']}")

    def stop_inference(self) -> None:
        if self.infer_thread is not None and self.infer_thread.isRunning():
            self.infer_thread.stop_infer()
            self.infer_thread.wait(5000)
        self.realtime_page.set_infer_status("待机", False)

    def on_infer_status(self, text: str) -> None:
        running = "运行" in text or "推理" in text
        self.realtime_page.set_infer_status(text, running)

    def on_frame(self, frame) -> None:
        self.last_frame = frame.copy()
        self.realtime_page.set_frame(frame)

    def on_infer_metrics(self, metrics: Dict) -> None:
        self.realtime_page.update_infer_metrics(metrics)
        self.statistics_page.update_infer_metrics(metrics)
        fps_warning = self.config.get("thresholds", {}).get("fps_warning", 15)
        if metrics.get("fps", 0) < fps_warning:
            self._rate_limited_alarm("fps", "WARNING", f"推理帧率偏低：{metrics.get('fps', 0):.2f} FPS")

    def on_detection(self, meta: Dict) -> None:
        self.realtime_page.update_detection(meta)
        self.statistics_page.update_detection(meta)

        if int(meta.get("defect_count", 0)) > 0:
            model = self.model_map.get(self.current_model_key, {})
            class_counts = {k: v for k, v in (meta.get("class_counts", {}) or {}).items() if int(v) > 0}
            detections = meta.get("detections", []) or []
            boxes = "; ".join(
                f"{d.get('class_name')}:{d.get('bbox')}@{float(d.get('confidence', 0)):.2f}"
                for d in detections[:20]
            )
            record = {
                "model": model.get("name", ""),
                "classes": ", ".join(f"{k}:{v}" for k, v in class_counts.items()),
                "target_count": int(meta.get("target_count", 0)),
                "defect_count": int(meta.get("defect_count", 0)),
                "max_confidence": float(meta.get("max_confidence", 0)),
                "boxes": boxes,
                "note": "自动记录",
            }
            self.history_page.add_record(record)
            self._rate_limited_alarm(
                "detection",
                "CRITICAL",
                f"检测到缺陷：{record['classes'] or record['defect_count']}",
                seconds=2,
            )

            if bool(self.config.get("storage", {}).get("auto_save_on_defect", False)):
                now = datetime.now().timestamp()
                if now - self._last_auto_snapshot_ts >= 2.0:
                    self.save_snapshot(show_message=False)
                    self._last_auto_snapshot_ts = now

    def on_infer_error(self, message: str) -> None:
        self.alarm_page.add_alarm("CRITICAL", message)
        QMessageBox.warning(self, "推理错误", message)

    def on_infer_finished(self) -> None:
        self.infer_thread = None
        self.realtime_page.set_infer_status("待机", False)

    def on_resource_update(self, data: Dict) -> None:
        self.resource_page.update_metrics(data)
        self.realtime_page.update_resource_preview(data)
        thresholds = self.config.get("thresholds", {})

        cpu_temp = data.get("cpu_temp")
        npu_temp = data.get("npu_temp")
        mem = data.get("memory_percent", 0)

        if cpu_temp is not None and cpu_temp >= thresholds.get("cpu_warning", 75):
            self._rate_limited_alarm(
                "cpu_temp",
                "WARNING",
                f"CPU温度过高：{cpu_temp:.1f} ℃",
            )
        if npu_temp is not None and npu_temp >= thresholds.get("npu_warning", 80):
            self._rate_limited_alarm(
                "npu_temp",
                "WARNING",
                f"NPU温度过高：{npu_temp:.1f} ℃",
            )
        if mem >= thresholds.get("memory_warning", 85):
            self._rate_limited_alarm(
                "memory",
                "WARNING",
                f"内存占用过高：{mem:.1f}%",
            )

        if data.get("monitor_error"):
            self._rate_limited_alarm("monitor", "WARNING", f"资源监控异常：{data.get('monitor_error')}")

    def apply_settings(self, new_config: Dict) -> None:
        was_running = self.infer_thread is not None and self.infer_thread.isRunning()
        self.config = new_config
        self.models = self.config.get("models", [])
        self.model_map = {m["key"]: m for m in self.models}

        try:
            self._write_config()
            self.alarm_page.add_alarm("INFO", "系统设置已保存到 config/models.json")
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", f"配置文件写入失败：{exc}")
            return

        if hasattr(self, "resource_thread"):
            self.resource_thread.update_config(self.config)

        self.realtime_page.update_models(self.models)
        self.settings_page.load_config(self.config, self.models)
        self._apply_default_model_to_combo()

        if was_running:
            QMessageBox.information(
                self,
                "设置已保存",
                "配置已保存。摄像头、模型阈值和TPE数量将在停止并重新启动推理后生效；资源监控路径会立即生效。",
            )
        else:
            QMessageBox.information(self, "设置已保存", "配置已保存并应用。")

    def _rate_limited_alarm(
        self,
        key: str,
        level: str,
        message: str,
        seconds: int = 30,
    ) -> None:
        now = datetime.now().timestamp()
        if now - self._last_alarm.get(key, 0) >= seconds:
            self.alarm_page.add_alarm(level, message)
            self._last_alarm[key] = now

    def save_snapshot(self, show_message: bool = True) -> None:
        if self.last_frame is None:
            if show_message:
                QMessageBox.information(self, "提示", "当前没有可保存的视频帧。")
            return

        folder = Path(self.config.get("storage", {}).get("snapshot_dir", "data/snapshots"))
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        if cv2.imwrite(str(path), self.last_frame):
            self.alarm_page.add_alarm("INFO", f"截图已保存：{path}")
        elif show_message:
            QMessageBox.warning(self, "错误", "截图保存失败。")

    def toggle_fullscreen(self) -> None:
        if not self._fullscreen:
            self.showFullScreen()
            self.sidebar.hide()
            self.topbar.hide()
            self._fullscreen = True
        else:
            self.showNormal()
            self.sidebar.show()
            self.topbar.show()
            self._fullscreen = False

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape and self._fullscreen:
            self.toggle_fullscreen()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.stop_inference()
        if hasattr(self, "resource_thread"):
            self.resource_thread.stop()
            self.resource_thread.wait(3000)
        event.accept()
