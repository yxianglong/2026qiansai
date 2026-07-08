import os
# 屏蔽RKNN冗余警告日志
os.environ["RKNN_LOG_LEVEL"] = "ERROR"
import cv2
import time
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QComboBox,
                             QPushButton, QLabel, QVBoxLayout, QHBoxLayout)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap

# 推理模块
from rknnpool.rknnpool_ld import rknnPoolExecutor
from func.func_yolov5_optimize import myFunc

# ---------------------- 推理子线程（新增类别列表入参） ----------------------
class InferThread(QThread):
    sig_status = pyqtSignal(str)
    sig_frame = pyqtSignal(object)
    sig_error = pyqtSignal()

    def __init__(self, model_path, cls_list):
        super().__init__()
        self._is_running = False
        self.pool = None
        self.cap = None
        self.modelPath = model_path
        self.cls_list = cls_list
        self.TPEs = 8
        self.video_dev = "/dev/video21"

    def run(self):
        self._is_running = True
        self.sig_status.emit("状态：初始化模型中...")
        try:
            # 将当前模型的类别列表传入rknn池，供给myFunc使用
            self.pool = rknnPoolExecutor(
                rknnModel=self.modelPath,
                TPEs=self.TPEs,
                func=lambda rknn, img: myFunc(rknn, img, self.cls_list)
            )
        except Exception as e:
            print("模型加载失败:", e)
            self.sig_status.emit("状态：模型加载失败")
            self.sig_error.emit()
            return

        self.cap = cv2.VideoCapture(self.video_dev)
        if not self.cap.isOpened():
            self.sig_status.emit("状态：摄像头打开失败")
            self.sig_error.emit()
            self.pool.release()
            self.pool = None
            return

        # 预填充帧
        for i in range(self.TPEs + 1):
            ret, frame = self.cap.read()
            if not ret:
                self.sig_status.emit("状态：无视频流")
                self._clean_resource()
                self.sig_error.emit()
                return
            self.pool.put(frame)

        frames, loopTime, initTime = 0, time.time(), time.time()
        self.sig_status.emit("状态：推理运行中")

        while self._is_running and self.cap.isOpened():
            frames += 1
            ret, frame = self.cap.read()
            if not ret:
                break
            self.pool.put(frame)
            frame, flag = self.pool.get()
            if flag is False:
                break

            frame = cv2.resize(frame, (1420, 800))
            self.sig_frame.emit(frame)

            if frames % 30 == 0:
                fps = 30 / (time.time() - loopTime)
                self.sig_status.emit(f"状态：推理中 30帧平均帧率 {fps:.1f}")
                loopTime = time.time()

        total_fps = frames / (time.time() - initTime)
        print("总平均帧率\t", total_fps)
        self._clean_resource()
        self.sig_status.emit("状态：待机")

    def stop_infer(self):
        self._is_running = False

    def _clean_resource(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.pool:
            self.pool.release()
            self.pool = None

# ---------------------- 主窗口（多模型+独立类别映射） ----------------------
class MainWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多模型缺陷检测平台")
        # 默认小窗口
        self.resize(900, 550)
        self.infer_thread = None
        self.is_fullscreen = False

        # ===================== 模型-类别映射，按你三个模型自行修改类别 =====================
        # 格式："下拉显示名": (模型文件路径, (类别1,类别2,...))
        self.model_config = {
            "芯片缺陷 best_chip": (
                "./rknnModel/best_chip.rknn",
                ("Contamination","Foreign_Material","Mark_defect","bump_defect","pad_defect","scratch",)  # 替换为该模型真实类别
            ),
            "晶圆缺陷 best_jingyuan": (
                "./rknnModel/best_jingyuan.rknn",
                ("crease", "scratch") # 该模型多类别示例
            ),
            "硅基缺陷 best_guiji": (
                "./rknnModel/best_guiji.rknn",
                ("defect", )
            )
        }

        self._create_ui()
        self._bind_slot()

    def _create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_h_layout = QHBoxLayout(central_widget)
        main_h_layout.setSpacing(12)
        main_h_layout.setContentsMargins(12, 12, 12, 12)

        # 左侧画面区
        self.lbl_display = QLabel("等待启动推理画面")
        self.lbl_display.setMinimumSize(640, 480)
        self.lbl_display.setAlignment(Qt.AlignCenter)
        self.lbl_display.setStyleSheet("border:1px solid #777;")
        main_h_layout.addWidget(self.lbl_display, stretch=7)

        # 右侧垂直控制栏
        right_v_layout = QVBoxLayout()
        right_v_layout.setSpacing(14)

        self.cbb_model = QComboBox()
        self.cbb_model.addItems(self.model_config.keys())
        self.cbb_model.setFixedHeight(34)
        right_v_layout.addWidget(self.cbb_model)

        self.btn_start = QPushButton("启动推理")
        self.btn_start.setFixedHeight(38)
        right_v_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("停止推理")
        self.btn_stop.setFixedHeight(38)
        right_v_layout.addWidget(self.btn_stop)

        # 全屏切换按钮
        self.btn_full = QPushButton("全屏显示画面")
        self.btn_full.setFixedHeight(38)
        right_v_layout.addWidget(self.btn_full)

        right_v_layout.addStretch()
        self.lbl_status = QLabel("状态：待机")
        right_v_layout.addWidget(self.lbl_status)

        main_h_layout.addLayout(right_v_layout, stretch=3)

    def _bind_slot(self):
        self.btn_start.clicked.connect(self.start_infer)
        self.btn_stop.clicked.connect(self.stop_infer)
        self.btn_full.clicked.connect(self.toggle_fullscreen)

    # 全屏/窗口切换
    def toggle_fullscreen(self):
        if not self.is_fullscreen:
            self.showFullScreen()
            self.btn_full.setText("退出全屏")
            self.is_fullscreen = True
        else:
            self.showNormal()
            self.btn_full.setText("全屏显示画面")
            self.is_fullscreen = False

    def start_infer(self):
        if self.infer_thread and self.infer_thread.isRunning():
            self.lbl_status.setText("状态：运行中，请先停止！")
            return
        # 获取当前选中模型的路径 + 对应类别列表
        select_name = self.cbb_model.currentText()
        model_path, cls_list = self.model_config[select_name]

        # 创建推理线程，传入该模型专属类别
        self.infer_thread = InferThread(model_path=model_path, cls_list=cls_list)
        self.infer_thread.sig_status.connect(lambda t: self.lbl_status.setText(t))
        self.infer_thread.sig_frame.connect(self.render_frame)
        self.infer_thread.sig_error.connect(self.stop_infer)
        self.infer_thread.finished.connect(self.clear_thread)
        self.infer_thread.start()

    def stop_infer(self):
        if self.infer_thread and self.infer_thread.isRunning():
            self.infer_thread.stop_infer()
            self.infer_thread.wait()

    def clear_thread(self):
        self.infer_thread = None

    def render_frame(self, cv_frame):
        h, w, ch = cv_frame.shape
        bytes_per_line = ch * w
        qt_img = QImage(cv_frame.data, w, h, bytes_per_line, QImage.Format_BGR888)
        pix = QPixmap.fromImage(qt_img).scaled(self.lbl_display.size(), Qt.KeepAspectRatio)
        self.lbl_display.setPixmap(pix)

    # 关闭窗口自动释放资源
    def closeEvent(self, event):
        self.stop_infer()
        event.accept()

# ---------------------- 程序入口 ----------------------
if __name__ == "__main__":
    # 本地显示屏xcb插件
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins"
    os.environ["DISPLAY"] = ":0"
    os.system("xhost +local:")

    app = QApplication(sys.argv)
    window = MainWin()
    window.show()
    sys.exit(app.exec_())