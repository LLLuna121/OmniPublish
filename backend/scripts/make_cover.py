#!/usr/bin/env python3
"""OmniPublish - 封面制作 (YOLOv8 person 检测 + 头顶对齐裁剪算法)

检测模型：YOLOv8n (person class) — 侧脸/背影/遮挡均可检测
裁剪算法：移植自 mediapipe 版 smart_process（一步 lift_scale + 直接头高归一化 + 贴边定位）
"""

import argparse, os, sys
import cv2
import numpy as np

# ═══ YOLOv8 person detection ═══
_yolo_model = None
_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 人体比例常数：头部高度 ≈ 身高的 1/7.5（解剖学标准）
HEAD_RATIO = 1 / 7.5


def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        bundled = os.path.join(_SKILL_DIR, "yolov8n.pt")
        _yolo_model = YOLO(bundled if os.path.isfile(bundled) else "yolov8n.pt")
    return _yolo_model


def detect_face(img):
    """用 YOLOv8 person 检测定位人物，从人体框推算头部位置。

    返回与 mediapipe 版 get_face_data 兼容的 dict：
    - y: 头顶 Y（= person box 顶部）
    - h: 估算头部高度（用于 Pass 2 归一化）
    - cx: 人物水平中心
    """
    try:
        h, w = img.shape[:2]
        model = get_yolo_model()
        results = model(img, verbose=False, conf=0.4, classes=[0])  # class 0 = person
        boxes = results[0].boxes
        if len(boxes) == 0:
            return None
        best, best_area = None, 0
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            bw, bh = x2 - x1, y2 - y1
            if bw * bh > best_area:
                best_area = bw * bh
                # 从人体框推算头部区域
                head_h = bh * HEAD_RATIO
                best = {
                    'x': float(x1), 'y': float(y1),       # 头顶 = person box 顶部
                    'w': float(bw), 'h': float(head_h),    # 头部高度（非全身高度）
                    'cx': float((x1 + x2) / 2),
                    'cy': float(y1 + head_h / 2),
                    'chin_y': float(y1 + head_h),
                    'orig_w': w, 'orig_h': h,
                }
        return best
    except Exception as e:
        print(f"[WARN]  YOLO detection failed: {e}")
        return None


# ═══ Layout config (exported for cover_service.py) ═══
LAYOUT_CONFIG = {
    "single": {"count": 1, "width": 640, "height": 640, "panels": [(640, 640)]},
    "double": {"count": 2, "width": 1280, "height": 640, "panels": [(640, 640), (640, 640)]},
    "triple": {"count": 3, "width": 1300, "height": 640, "panels": [(433, 640), (434, 640), (433, 640)]},
}


def smart_process(img, target_w, target_h, head_margin_ratio=0.15, target_head_h=None):
    """头顶对齐裁剪（移植自 mediapipe 版算法，检测换用 YOLO）。

    Pass 1: 一步 lift_scale 确保头顶对齐到留白线
    Pass 2: target_head_h 驱动缩放，精确匹配多图头部大小
    """
    if img is None:
        return None, 0

    f = detect_face(img)
    head_target_y = target_h * head_margin_ratio

    if not f:
        # 无脸兜底：居中缩放裁剪
        scale = max(target_w / img.shape[1], target_h / img.shape[0])
        res = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
        rh, rw = res.shape[:2]
        y1 = (rh - target_h) // 2
        x1 = (rw - target_w) // 2
        return res[y1:y1 + target_h, x1:x1 + target_w], 0

    # 1. 缩放比例
    base_scale = max(target_w / f['orig_w'], target_h / f['orig_h'])

    if target_head_h:
        # Pass 2：由全局最大头高驱动缩放
        scale = max(base_scale, target_head_h / f['h'])
    else:
        # Pass 1：一步法 lift_scale，让头顶到达 head_target_y 且不露黑边
        required_bottom_space = target_h - head_target_y
        if f['orig_h'] > f['y']:
            lift_scale = required_bottom_space / (f['orig_h'] - f['y'])
            scale = max(base_scale, lift_scale)
        else:
            scale = base_scale

    # 执行缩放
    s_img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    sh, sw = s_img.shape[:2]
    sf = {k: v * scale for k, v in f.items() if k not in ('orig_w', 'orig_h')}

    # 2. 垂直定位：头顶对齐到留白线
    y1 = sf['y'] - head_target_y
    y1 = np.clip(y1, 0, sh - target_h)

    # 3. 水平定位：偏侧人脸贴边，居中人脸居中
    dist_l = f['cx']
    dist_r = f['orig_w'] - f['cx']
    if (dist_l > 2.5 * dist_r) or (dist_r > 2.5 * dist_l):
        x1 = 0 if dist_l < dist_r else sw - target_w
    else:
        x1 = sf['cx'] - target_w / 2
    x1 = np.clip(x1, 0, sw - target_w)

    # 4. 裁切
    crop = s_img[int(y1):int(y1 + target_h), int(x1):int(x1 + target_w)]
    if crop.shape[:2] != (target_h, target_w):
        crop = cv2.resize(crop, (target_w, target_h))

    return crop, sf['h']


def make_cover(folder, output, layout="triple", head_margin=0.15, quality=95):
    """Generate cover image from folder of images."""
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = sorted([
        os.path.join(folder, f) for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in exts
        and not f.startswith(".")
        and "_cover" not in f.lower()
    ])

    if not images:
        print("[ERROR] No images found in folder")
        return None

    cfg = LAYOUT_CONFIG.get(layout, LAYOUT_CONFIG["triple"])
    count = min(cfg["count"], len(images))
    selected = images[:count]

    while len(selected) < cfg["count"]:
        selected.append(selected[-1])

    print(f"[INFO]  Layout: {layout}, Images: {len(selected)}, Size: {cfg['width']}x{cfg['height']}")

    # Pass 1: 初步裁剪 + 获取头高
    panels = []
    head_heights = []
    for i, img_path in enumerate(selected):
        pw, ph = cfg["panels"][i]
        img = cv2.imread(img_path)
        if img is None:
            print(f"[WARN]  Cannot read: {img_path}")
            continue
        cropped, hh = smart_process(img, pw, ph, head_margin)
        panels.append((img_path, cropped))
        head_heights.append(hh)
        print(f"[INFO]  Panel {i+1}: {os.path.basename(img_path)} -> {pw}x{ph}, head_h={hh:.0f}")

    if not panels:
        print("[ERROR] No valid panels")
        return None

    # Pass 2: 头部大小归一化（直接头高驱动）
    max_hh = max(head_heights) if head_heights else 0
    if max_hh > 0:
        for i, (img_path, _) in enumerate(panels):
            if 0 < head_heights[i] < max_hh * 0.95:
                pw, ph = cfg["panels"][i]
                img = cv2.imread(img_path)
                refined, _ = smart_process(img, pw, ph, head_margin, target_head_h=max_hh)
                panels[i] = (img_path, refined)
                print(f"[INFO]  Panel {i+1}: re-processed for head size normalization")

    # 拼接
    parts = [panel_img for _, panel_img in panels]
    # 确保中间面板宽度正确 (triple: 433+434+433=1300)
    for i, (pw, ph) in enumerate(cfg["panels"]):
        if i < len(parts) and parts[i].shape[1] != pw:
            parts[i] = cv2.resize(parts[i], (pw, ph))

    canvas = np.hstack(parts)

    os.makedirs(output, exist_ok=True)
    folder_name = os.path.basename(os.path.normpath(folder))
    out_path = os.path.join(output, f"{folder_name}_cover.jpg")
    cv2.imwrite(out_path, canvas, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    print(f"[OK]    Cover saved: {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="OmniPublish Cover Maker")
    parser.add_argument("--folder", required=True, help="Input image folder")
    parser.add_argument("--output", default=None, help="Output directory (default: same as folder)")
    parser.add_argument("--layout", default="triple", choices=["single", "double", "triple"])
    parser.add_argument("--head-margin", type=float, default=0.15, help="Head top margin ratio (0-1)")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality")
    args = parser.parse_args()

    output = args.output or args.folder
    make_cover(args.folder, output, args.layout, args.head_margin, args.quality)


if __name__ == "__main__":
    main()
