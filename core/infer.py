import time
from typing import Any, Dict, Iterable, Optional, Tuple

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal


class BaseInferThread(QThread):
    sig_status = pyqtSignal(str)
    sig_frame = pyqtSignal(object)
    sig_metrics = pyqtSignal(dict)
    sig_detection = pyqtSignal(dict)
    sig_error = pyqtSignal(str)

    def stop_infer(self) -> None:
        self._is_running = False


class RKNNInferThread(BaseInferThread):
    """真实 RKNN 推理线程。"""

    def __init__(
        self,
        model_path: str,
        cls_list: Iterable[str],
        video_dev: str = "/dev/video12",
        tpes: int = 8,
        conf_thres: float = 0.25,
        nms_thres: float = 0.45,
        camera_width: int = 0,
        camera_height: int = 0,
    ) -> None:
        super().__init__()
        self.model_path = model_path
        self.cls_list = tuple(cls_list)
        self.video_dev = video_dev
        self.tpes = max(1, int(tpes))
        self.conf_thres = float(conf_thres)
        self.nms_thres = float(nms_thres)
        self.camera_width = int(camera_width or 0)
        self.camera_height = int(camera_height or 0)
        self._is_running = False
        self.pool = None
        self.cap = None

    @staticmethod
    def _normalize_result(result: Any) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """兼容 frame、(frame, meta) 和 {"frame": ..., ...} 三种结果。"""
        if isinstance(result, dict):
            frame = result.get("frame")
            meta = {k: v for k, v in result.items() if k != "frame"}
            return frame, meta
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
            return result[0], result[1]
        return result, {}

    def run(self) -> None:
        self._is_running = True
        self.sig_status.emit("初始化模型")
        try:
            from rknnpool.rknnpool_ld import rknnPoolExecutor
            from func.func_yolov5_optimize import myFunc
        except Exception as exc:
            self.sig_error.emit(f"RKNN模块导入失败：{exc}")
            self.sig_status.emit("模型模块不可用")
            return

        try:
            self.pool = rknnPoolExecutor(
                rknnModel=self.model_path,
                TPEs=self.tpes,
                func=lambda rknn, img: myFunc(
                    rknn,
                    img,
                    self.cls_list,
                    conf_thres=self.conf_thres,
                    nms_thres=self.nms_thres,
                    draw_result=True,
                ),
            )
        except Exception as exc:
            self.sig_error.emit(f"模型加载失败：{exc}")
            self.sig_status.emit("模型加载失败")
            return

        self.cap = cv2.VideoCapture(self.video_dev)
        if self.camera_width > 0:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
        if self.camera_height > 0:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)

        if not self.cap.isOpened():
            self.sig_error.emit(f"摄像头打开失败：{self.video_dev}")
            self._clean_resource()
            return

        try:
            for _ in range(self.tpes + 1):
                ok, frame = self.cap.read()
                if not ok:
                    raise RuntimeError("预填充阶段未读取到视频帧")
                self.pool.put(frame)

            frames = 0
            period_frames = 0
            start_time = time.perf_counter()
            period_start = start_time
            latency_acc = 0.0
            self.sig_status.emit("推理运行中")

            while self._is_running and self.cap.isOpened():
                ok, frame = self.cap.read()
                if not ok:
                    self.sig_error.emit("视频流读取失败")
                    break

                self.pool.put(frame)
                infer_start = time.perf_counter()
                raw_result, flag = self.pool.get()
                latency_ms = (time.perf_counter() - infer_start) * 1000.0

                if not flag:
                    self.sig_error.emit("RKNN线程池返回失败")
                    break

                result_frame, meta = self._normalize_result(raw_result)
                if result_frame is None:
                    continue

                frames += 1
                period_frames += 1
                latency_acc += latency_ms

                self.sig_frame.emit(result_frame)
                if meta:
                    self.sig_detection.emit(meta)

                now = time.perf_counter()
                if now - period_start >= 1.0:
                    elapsed = now - period_start
                    fps = period_frames / max(elapsed, 1e-6)
                    avg_latency = latency_acc / max(period_frames, 1)
                    self.sig_metrics.emit(
                        {
                            "fps": fps,
                            "latency_ms": avg_latency,
                            "frames": frames,
                            "runtime_s": now - start_time,
                        }
                    )
                    period_start = now
                    period_frames = 0
                    latency_acc = 0.0
        except Exception as exc:
            self.sig_error.emit(f"推理异常：{exc}")
        finally:
            self._clean_resource()
            self.sig_status.emit("待机")

    def _clean_resource(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.pool is not None:
            try:
                self.pool.release()
            finally:
                self.pool = None


class DemoInferThread(BaseInferThread):
    """普通PC上的界面演示线程，不调用RKNN。"""

    def __init__(self, model_name: str, classes: Iterable[str]) -> None:
        super().__init__()
        self.model_name = model_name
        self.classes = tuple(classes)
        self._is_running = False

    def run(self) -> None:
        self._is_running = True
        self.sig_status.emit("演示推理运行中")
        frame_idx = 0
        start = time.perf_counter()
        last_metrics = start

        while self._is_running:
            tick = time.perf_counter()
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame[:] = (18, 31, 53)

            for x in range(0, 1280, 80):
                cv2.line(frame, (x, 0), (x, 720), (38, 67, 92), 1)
            for y in range(0, 720, 80):
                cv2.line(frame, (0, y), (1280, y), (38, 67, 92), 1)

            cx = int(640 + 260 * np.sin(frame_idx / 45.0))
            cy = int(360 + 120 * np.cos(frame_idx / 60.0))
            cv2.rectangle(frame, (cx - 110, cy - 80), (cx + 110, cy + 80), (88, 215, 255), 2)
            cls_name = self.classes[frame_idx % len(self.classes)] if self.classes else "defect"
            cv2.putText(
                frame,
                f"{cls_name}  0.94",
                (cx - 110, cy - 92),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (88, 215, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"MODEL: {self.model_name}",
                (40, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (210, 242, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                "RK3588 EDGE INSPECTION / DEMO MODE",
                (40, 690),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (115, 166, 196),
                2,
                cv2.LINE_AA,
            )

            self.sig_frame.emit(frame)
            frame_idx += 1

            now = time.perf_counter()
            if now - last_metrics >= 1.0:
                fps = 28.0 + 2.5 * np.sin(frame_idx / 30.0)
                latency = 34.0 + 3.0 * np.cos(frame_idx / 35.0)
                self.sig_metrics.emit(
                    {
                        "fps": float(fps),
                        "latency_ms": float(latency),
                        "frames": frame_idx,
                        "runtime_s": now - start,
                    }
                )

                counts = {name: 0 for name in self.classes}
                if cls_name:
                    counts[cls_name] = 1 + frame_idx % 3
                detections = [
                    {
                        "class_id": self.classes.index(cls_name) if cls_name in self.classes else 0,
                        "class_name": cls_name,
                        "confidence": 0.94,
                        "bbox": [cx - 110, cy - 80, cx + 110, cy + 80],
                    }
                ] * counts.get(cls_name, 1)

                self.sig_detection.emit(
                    {
                        "target_count": len(detections),
                        "defect_count": len(detections),
                        "max_confidence": 0.94,
                        "class_counts": counts,
                        "detections": detections,
                    }
                )
                last_metrics = now

            elapsed = time.perf_counter() - tick
            self.msleep(max(1, int((1.0 / 30.0 - elapsed) * 1000)))

        self.sig_status.emit("待机")
