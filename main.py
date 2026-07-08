import argparse
import os
import sys
from pathlib import Path

# 屏蔽RKNN冗余日志
os.environ.setdefault("RKNN_LOG_LEVEL", "ERROR")

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


def configure_qt_environment() -> None:
    """
    配置 Qt 显示环境。

    等价于终端执行：
    export DISPLAY=:0
    unset QT_QPA_PLATFORM

    同时修复 OpenCV 自带 Qt 插件路径覆盖 PyQt5 的问题。
    """

    system_qt_plugin_path = "/usr/lib/aarch64-linux-gnu/qt5/plugins"

    # 强制使用系统 Qt 插件，避免 cv2/qt/plugins 冲突
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = system_qt_plugin_path
    os.environ["QT_PLUGIN_PATH"] = system_qt_plugin_path

    # 清除 OpenCV 可能设置的字体路径
    os.environ.pop("QT_QPA_FONTDIR", None)

    # 等价于 export DISPLAY=:0
    os.environ["DISPLAY"] = ":0"

    # 等价于 unset QT_QPA_PLATFORM
    # 让 Qt 自动选择可用后端，不强制 xcb/wayland
    os.environ.pop("QT_QPA_PLATFORM", None)


def load_stylesheet(app: QApplication) -> None:
    qss_path = Path(__file__).parent / "assets" / "style.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="RK3588多模型缺陷检测监控平台")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用模拟视频与模拟推理指标，便于在非RK3588设备上预览界面",
    )
    args = parser.parse_args()

    configure_qt_environment()

    app = QApplication(sys.argv)
    app.setApplicationName("RK3588 Defect Dashboard")
    app.setOrganizationName("Edge AI Lab")
    load_stylesheet(app)

    window = MainWindow(demo_mode=args.demo)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
