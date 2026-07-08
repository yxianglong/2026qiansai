# Final UI/resource modifications

- RKNPU 三核心负载改为优先读取 `/sys/kernel/debug/rknpu/load`。
- 读取 debugfs 权限处理写入程序：启动时尝试 `sudo -n chmod 444`，读取时尝试 `sudo -n cat`，不会阻塞等待密码。
- CPU 频率优先读取 `cpuinfo_cur_freq`，失败后回退到 `scaling_cur_freq`。
- 统计分析页删除 Defect Rate、Current FPS 卡片，仅保留 Processed Frames、Detected Targets、Defect Targets、Average Confidence。
- Inference FPS Trend 调整为 14.00–16.00 区间，15.00 位于图表中心，显示两位小数。
- 删除模型管理页面。
- 顶部删除 DEVICE MODE 和 DEVICE ONLINE。
