# UI重构与真实数据接入说明

## 修改范围

1. 实时检测页
   - 删除“显示检测框”开关。
   - 删除实时页输出延时展示。
   - FPS显示精确到小数点后两位。
   - 删除实时页当前目标数、当前缺陷数、最高置信度卡片。
   - Class Counter改为表格，类别名完整显示。

2. myFunc输出
   - `func/func_yolov8_optimize.py` 的 `myFunc()` 已改为返回 `(frame, meta)`。
   - `meta` 包含 `target_count`、`defect_count`、`max_confidence`、`class_counts` 和 `detections`。
   - 统计分析页和历史记录页基于 `meta` 更新。

3. 系统资源页
   - NPU负载、频率和温度只使用板卡原始节点。
   - 不再使用FPS、延迟或其他推测值伪造NPU负载。
   - 未发现独立节点时显示 `N/A`。

4. 系统设置页
   - 保存后写入 `config/models.json`。
   - 置信度、NMS、TPE、摄像头参数在下次启动推理时生效。
   - 告警阈值、NPU资源路径、自动截图设置保存后生效。

## 查找NPU真实节点

在RK3588开发板上运行：

```bash
python3 tools/discover_rk3588_sensors.py
```

把输出中的真实NPU负载、频率、温度路径填入系统设置。
