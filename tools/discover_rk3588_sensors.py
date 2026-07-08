#!/usr/bin/env python3
from pathlib import Path
import glob

def read(path):
    try:
        return Path(path).read_text(errors="ignore").strip()
    except Exception:
        return ""

print("==== devfreq ====")
for d in sorted(glob.glob("/sys/class/devfreq/*")):
    name = read(f"{d}/name")
    load = read(f"{d}/load")
    cur = read(f"{d}/cur_freq")
    print(f"{d}")
    print(f"  name     : {name}")
    print(f"  load     : {load}")
    print(f"  cur_freq : {cur}")

print("\n==== thermal ====")
for z in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
    typ = read(f"{z}/type")
    temp = read(f"{z}/temp")
    print(f"{z}")
    print(f"  type : {typ}")
    print(f"  temp : {temp}")

print("\n说明：")
print("1. 如果能看到包含 npu/rknpu/fdab0000 的 devfreq 节点，可把 load/cur_freq 路径填入系统设置。")
print("2. 如果 thermal zone 的 type 中包含 npu，可把对应 temp 路径填入 NPU温度。")
print("3. 若没有 NPU_CORE0/1/2 的独立节点，系统会显示 N/A，不进行推测。")
