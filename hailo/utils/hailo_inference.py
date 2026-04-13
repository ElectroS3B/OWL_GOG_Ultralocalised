import numpy as np
import cv2
import time
from hailo_platform import (HEF, VDevice, InferVStreams, ConfigureParams,
    InputVStreamParams, OutputVStreamParams, FormatType, HailoStreamInterface)

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -88, 88)))

def dfl_decode(box_dist, reg_max=16):
    H, W, _ = box_dist.shape
    box_dist = box_dist.reshape(H, W, 4, reg_max)
    e = np.exp(box_dist - box_dist.max(axis=-1, keepdims=True))
    box_dist = e / e.sum(axis=-1, keepdims=True)
    proj = np.arange(reg_max, dtype=np.float32)
    return (box_dist * proj).sum(axis=-1)

def make_anchors(H, W):
    sy, sx = np.meshgrid(np.arange(H), np.arange(W), indexing='ij')
    return np.stack([sx + 0.5, sy + 0.5], axis=-1).reshape(-1, 2).astype(np.float32)

def dist2bbox(ltrb, anchors, stride):
    x1 = (anchors[:, 0] - ltrb[:, 0]) * stride
    y1 = (anchors[:, 1] - ltrb[:, 1]) * stride
    x2 = (anchors[:, 0] + ltrb[:, 2]) * stride
    y2 = (anchors[:, 1] + ltrb[:, 3]) * stride
    return np.stack([x1, y1, x2, y2], axis=-1)

def nms(boxes, scores, iou_thr=0.45):
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:,0], boxes[:,1], boxes[:,2], boxes[:,3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2-xx1) * np.maximum(0, yy2-yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][iou <= iou_thr]
    return keep

class HailoInference:
    def __init__(self, model_path, confidence_threshold=0.25):
        self.confidence_threshold = float(confidence_threshold)
        self.dt = 0.0
        self.strides = [8, 16, 32]
        self.input_size = 640

        self.hef = HEF(model_path)
        self.target = VDevice()
        cfg = ConfigureParams.create_from_hef(hef=self.hef, interface=HailoStreamInterface.PCIe)
        self.network_group = self.target.configure(self.hef, cfg)[0]
        self.network_group_params = self.network_group.create_params()

        self.in_params = InputVStreamParams.make_from_network_group(
            self.network_group, format_type=FormatType.FLOAT32)
        self.out_params = OutputVStreamParams.make_from_network_group(
            self.network_group, format_type=FormatType.FLOAT32)

        self.input_info = self.hef.get_input_vstream_infos()[0]
        self.output_infos = self.hef.get_output_vstream_infos()

        self.act_ctx = self.network_group.activate(self.network_group_params)
        self.act_ctx.__enter__()
        self.pipeline = InferVStreams(self.network_group, self.in_params, self.out_params)
        self.pipeline.__enter__()

    def run(self, frame):
        t0 = time.perf_counter()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if rgb.shape[0] != self.input_size or rgb.shape[1] != self.input_size:
            rgb = cv2.resize(rgb, (self.input_size, self.input_size))
        inp = rgb.astype(np.float32) / 255.0
        input_data = {self.input_info.name: np.expand_dims(inp, 0)}
        raw = self.pipeline.infer(input_data)

        names = sorted([info.name for info in self.output_infos])
        pairs = [(names[0], names[1]), (names[2], names[3]), (names[4], names[5])]

        all_boxes, all_scores = [], []

        for (box_name, cls_name), stride in zip(pairs, self.strides):
            box_raw = raw[box_name][0]
            cls_raw = raw[cls_name][0]
            H, W = box_raw.shape[:2]

            ltrb = dfl_decode(box_raw).reshape(-1, 4)
            anchors = make_anchors(H, W)
            boxes_px = dist2bbox(ltrb, anchors, stride)

            nc = cls_raw.shape[-1] if cls_raw.ndim == 3 else 1
            cls_scores = sigmoid(cls_raw.reshape(-1, nc))
            conf = cls_scores.max(axis=-1)
            cls_id = cls_scores.argmax(axis=-1)

            mask = conf > self.confidence_threshold
            if mask.sum() == 0:
                continue
            all_boxes.append(boxes_px[mask])
            all_scores.append(np.stack([conf[mask], cls_id[mask].astype(np.float32)], axis=-1))

        if not all_boxes:
            self.dt = (time.perf_counter() - t0) * 1000
            return []

        all_boxes = np.concatenate(all_boxes, axis=0)
        all_scores = np.concatenate(all_scores, axis=0)
        keep = nms(all_boxes, all_scores[:, 0])

        detections = []
        S = float(self.input_size)
        for i in keep:
            x1, y1, x2, y2 = all_boxes[i]
            detections.append([y1/S, x1/S, y2/S, x2/S,
                                float(all_scores[i, 0]),
                                float(all_scores[i, 1])])
        self.dt = (time.perf_counter() - t0) * 1000
        return detections

    def __del__(self):
        try:
            self.pipeline.__exit__(None, None, None)
            self.act_ctx.__exit__(None, None, None)
        except:
            pass
