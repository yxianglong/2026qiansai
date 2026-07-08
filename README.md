# RK3588 多模型缺陷检测监控平台
界面采用深蓝、青蓝高亮、细线描边和仪表盘风格，包含：

- 实时检测
- 系统资源
- 统计分析
- 模型管理
- 历史记录
- 告警中心
- 系统设置

## 1. 目录结构

```text
rk3588_defect_dashboard/
├── main.py
├── assets/style.qss
├── config/models.json
├── core/
│   ├── infer.py
│   ├── resource_monitor.py
│   └── history_store.py
├── ui/
│   ├── main_window.py
│   ├── widgets.py
│   └── pages/
├── legacy/
│   └── qt_main_camera_fps_v8.py
└── requirements.txt
```

## 2. 运行方式

安装通用依赖：

```bash
pip3 install -r requirements.txt
```

在普通 PC 上预览界面：

```bash
python3 main.py --demo
```

在 RK3588 上运行真实模型：

```bash
python3 main.py
```

## 3. 与 RKNN 工程连接

真实推理线程使用工程中的：

```python
from rknnpool.rknnpool_ld import rknnPoolExecutor
from func.func_yolov8_optimize import myFunc
```

模型路径和类别统一配置在：

```text
config/models.json
```

默认配置已经写入：

- 芯片缺陷：Contamination、Foreign_Material、Mark_defect、bump_defect、pad_defect、scratch
- 晶圆缺陷：crease、scratch
- 硅基缺陷：defect

## 4. 检测数量与类别统计接口

将 `myFunc()` 修改为返回以下任意一种格式即可：

```python
return result_frame, {
    "target_count": 5,
    "defect_count": 5,
    "max_confidence": 0.96,
    "class_counts": {
        "scratch": 2,
        "Contamination": 3
    }
}
```

推理线程会自动识别 `(frame, meta)` 结构，并将 `meta` 发送给实时检测页、统计页和历史记录模块。

## 5. RK3588 资源读取

系统资源线程会优先读取：

- `/proc/stat`
- `/proc/meminfo`
- `/proc/uptime`
- `/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq`
- `/sys/class/thermal/thermal_zone*/`
- `/sys/class/devfreq/*`


### 系统设置页

系统设置现在会真实写入 `config/models.json` 并影响程序：

- 摄像头设备、宽高：下次启动推理时生效。
- 置信度阈值、NMS阈值：下次启动推理时传入 `myFunc()`。
- TPE数量：下次启动推理时生效。
- 告警阈值：立即用于后续告警判断。
- NPU资源路径：立即用于资源监控线程。
- 缺陷自动截图：保存后立即生效。
