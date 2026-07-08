# 以下代码改自 Rockchip YOLO 示例，并针对多模型类别统计做了结构化输出。
import cv2
import numpy as np
from collections import Counter

OBJ_THRESH, NMS_THRESH, IMG_SIZE = 0.25, 0.45, 640


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def yolov5_post_process(input_data, img_size=640, conf_thres=0.25, nms_thres=0.45, class_count=None):
    """YOLOv5 RKNN 单输出后处理。

    支持常见输出 shape：
    - [1, 25200, 5 + nc]
    - [25200, 5 + nc]

    返回：
    - boxes: xyxy，坐标位于 letterbox 后的 img_size 空间
    - classes: int 类别索引
    - scores: float 置信度
    """
    if not input_data:
        return None, None, None

    pred = np.squeeze(input_data[0])
    if pred.ndim != 2 or pred.shape[1] < 6:
        return None, None, None

    # 只取当前模型类别数对应的输出，避免类别列表和模型类别数不一致时越界。
    cls_probs = pred[:, 5:]
    if class_count is not None and class_count > 0 and cls_probs.shape[1] >= class_count:
        cls_probs = cls_probs[:, :class_count]

    obj_conf = pred[:, 4:5]
    scores_all = obj_conf * cls_probs
    max_scores = np.max(scores_all, axis=1)
    classes = np.argmax(scores_all, axis=1)

    valid_mask = max_scores >= conf_thres
    if not np.any(valid_mask):
        return None, None, None

    pred = pred[valid_mask]
    max_scores = max_scores[valid_mask]
    classes = classes[valid_mask]

    xywh = pred[:, :4].astype(np.float32).copy()
    boxes_xyxy = np.zeros_like(xywh, dtype=np.float32)
    boxes_xyxy[:, 0] = xywh[:, 0] - xywh[:, 2] / 2.0
    boxes_xyxy[:, 1] = xywh[:, 1] - xywh[:, 3] / 2.0
    boxes_xyxy[:, 2] = xywh[:, 0] + xywh[:, 2] / 2.0
    boxes_xyxy[:, 3] = xywh[:, 1] + xywh[:, 3] / 2.0

    # cv2.dnn.NMSBoxes 需要 xywh 格式。
    nms_boxes = np.zeros_like(xywh, dtype=np.float32)
    nms_boxes[:, 0] = boxes_xyxy[:, 0]
    nms_boxes[:, 1] = boxes_xyxy[:, 1]
    nms_boxes[:, 2] = boxes_xyxy[:, 2] - boxes_xyxy[:, 0]
    nms_boxes[:, 3] = boxes_xyxy[:, 3] - boxes_xyxy[:, 1]

    keep = cv2.dnn.NMSBoxes(
        nms_boxes.tolist(),
        max_scores.astype(float).tolist(),
        float(conf_thres),
        float(nms_thres),
    )

    if keep is None or len(keep) == 0:
        return None, None, None

    keep = np.array(keep).reshape(-1)
    return boxes_xyxy[keep], classes[keep], max_scores[keep]


def draw_box_corner(draw_img, x1, y1, x2, y2, length, corner_color):
    cv2.line(draw_img, (x1, y1), (x1 + length, y1), corner_color, thickness=3)
    cv2.line(draw_img, (x1, y1), (x1, y1 + length), corner_color, thickness=3)

    cv2.line(draw_img, (x2, y1), (x2 - length, y1), corner_color, thickness=3)
    cv2.line(draw_img, (x2, y1), (x2, y1 + length), corner_color, thickness=3)

    cv2.line(draw_img, (x1, y2), (x1 + length, y2), corner_color, thickness=3)
    cv2.line(draw_img, (x1, y2), (x1, y2 - length), corner_color, thickness=3)

    cv2.line(draw_img, (x2, y2), (x2 - length, y2), corner_color, thickness=3)
    cv2.line(draw_img, (x2, y2), (x2, y2 - length), corner_color, thickness=3)


def draw_label_type(draw_img, x1, y1, label, label_color):
    label = str(label)
    font_scale = 0.65
    thickness = 2
    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]

    y_top = max(0, y1 - label_size[1] - 8)
    x_right = min(draw_img.shape[1] - 1, x1 + label_size[0] + 10)

    cv2.rectangle(draw_img, (x1, y_top), (x_right, y1), label_color, thickness=-1)
    cv2.putText(
        draw_img,
        label,
        (x1 + 5, max(label_size[1] + 2, y1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (0, 0, 0),
        thickness,
        cv2.LINE_AA,
    )


def _scale_box_to_original(box, ratio, padding, image_shape):
    x1, y1, x2, y2 = box
    pad_x, pad_y = padding

    x1 = int((x1 - pad_x) / ratio[0])
    y1 = int((y1 - pad_y) / ratio[1])
    x2 = int((x2 - pad_x) / ratio[0])
    y2 = int((y2 - pad_y) / ratio[1])

    h, w = image_shape[:2]
    x1 = max(0, min(w - 1, x1))
    y1 = max(0, min(h - 1, y1))
    x2 = max(0, min(w - 1, x2))
    y2 = max(0, min(h - 1, y2))

    return x1, y1, x2, y2


def draw_and_collect(image, boxes, scores, classes, ratio, padding, cls_list):
    detections = []
    if boxes is None:
        return detections

    for box, score, cl in zip(boxes, scores, classes):
        cl = int(cl)
        if 0 <= cl < len(cls_list):
            cls_name = str(cls_list[cl])
        else:
            cls_name = f"未知{cl}"

        x1, y1, x2, y2 = _scale_box_to_original(box, ratio, padding, image.shape)

        cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 255), 2)
        draw_box_corner(image, x1, y1, x2, y2, 15, (0, 255, 0))
        draw_label_type(image, x1, y1, f"{cls_name} {float(score):.2f}", (255, 0, 255))

        detections.append(
            {
                "class_id": cl,
                "class_name": cls_name,
                "confidence": float(score),
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
            }
        )

    return detections


def build_meta(detections, cls_list):
    class_counts = Counter(d["class_name"] for d in detections)
    max_conf = max((d["confidence"] for d in detections), default=0.0)

    return {
        "target_count": len(detections),
        "defect_count": len(detections),
        "max_confidence": float(max_conf),
        "class_counts": {name: int(class_counts.get(name, 0)) for name in cls_list},
        "detections": detections,
    }


def letterbox(im, new_shape=(640, 640), color=(0, 0, 0)):
    shape = im.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    ratio = r, r

    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]

    dw /= 2
    dh /= 2

    if shape[::-1] != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)

    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))

    im = cv2.copyMakeBorder(
        im,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=color,
    )

    return im, ratio, (left, top)


def myFunc(
    rknn_lite,
    IMG,
    cls_list,
    conf_thres=OBJ_THRESH,
    nms_thres=NMS_THRESH,
    draw_result=True,
):
    """执行单帧推理并返回画面 + 结构化检测结果。

    返回格式：
        return result_frame, meta

    meta:
        {
            "target_count": int,
            "defect_count": int,
            "max_confidence": float,
            "class_counts": {"scratch": 2, ...},
            "detections": [
                {
                    "class_id": 0,
                    "class_name": "scratch",
                    "confidence": 0.93,
                    "bbox": [x1, y1, x2, y2]
                }
            ]
        }
    """
    cls_list = tuple(cls_list)

    img_rgb = cv2.cvtColor(IMG, cv2.COLOR_BGR2RGB)
    img_input, ratio, padding = letterbox(img_rgb, new_shape=(IMG_SIZE, IMG_SIZE))
    img_input = np.expand_dims(img_input, 0)

    outputs = rknn_lite.inference(inputs=[img_input], data_format=["nhwc"])
    boxes, classes, scores = yolov5_post_process(
        outputs,
        img_size=IMG_SIZE,
        conf_thres=float(conf_thres),
        nms_thres=float(nms_thres),
        class_count=len(cls_list),
    )

    detections = []
    if boxes is not None and draw_result:
        detections = draw_and_collect(IMG, boxes, scores, classes, ratio, padding, cls_list)
    elif boxes is not None:
        for box, score, cl in zip(boxes, scores, classes):
            cl = int(cl)
            cls_name = cls_list[cl] if 0 <= cl < len(cls_list) else f"未知{cl}"
            bbox = _scale_box_to_original(box, ratio, padding, IMG.shape)
            detections.append(
                {
                    "class_id": cl,
                    "class_name": str(cls_name),
                    "confidence": float(score),
                    "bbox": [int(v) for v in bbox],
                }
            )

    meta = build_meta(detections, cls_list)
    return IMG, meta
