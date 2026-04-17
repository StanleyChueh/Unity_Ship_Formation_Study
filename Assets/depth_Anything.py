import time

import cv2
import numpy as np


class DepthAnythingEstimator:
    """Lazy Depth Anything wrapper for relative-depth testing.

    This returns relative depth values from the model output. They are useful
    for comparing "nearer vs farther" targets, but they are not metric meters
    unless you add a separate calibration step later.
    """

    def __init__(self, model_id="LiheYoung/depth-anything-small-hf", device="cpu"):
        self.model_id = model_id
        self.device = device
        self.available = False
        self.error = None
        self.processor = None
        self.model = None
        self.last_infer_sec = 0.0

        try:
            import torch
            from PIL import Image
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation

            self._torch = torch
            self._pil_image = Image
            self.processor = AutoImageProcessor.from_pretrained(model_id)
            self.model = AutoModelForDepthEstimation.from_pretrained(model_id)

            if device == "cuda" and torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"

            self.model.to(self.device)
            self.model.eval()
            self.available = True
        except Exception as exc:
            self.error = str(exc)

    def estimate(self, frame_bgr, bbox=None, input_max_size=320):
        if not self.available:
            return {
                "ok": False,
                "error": self.error or "Depth Anything is unavailable.",
            }

        try:
            height, width = frame_bgr.shape[:2]
            scale = 1.0
            if input_max_size is not None and max(height, width) > input_max_size:
                scale = float(input_max_size) / float(max(height, width))

            if scale < 1.0:
                infer_width = max(32, int(width * scale))
                infer_height = max(32, int(height * scale))
                infer_frame = cv2.resize(frame_bgr, (infer_width, infer_height), interpolation=cv2.INTER_AREA)
            else:
                infer_frame = frame_bgr
                infer_width = width
                infer_height = height

            image_rgb = cv2.cvtColor(infer_frame, cv2.COLOR_BGR2RGB)
            pil_image = self._pil_image.fromarray(image_rgb)

            start_time = time.time()
            inputs = self.processor(images=pil_image, return_tensors="pt")
            inputs = {key: value.to(self.device) for key, value in inputs.items()}

            with self._torch.no_grad():
                outputs = self.model(**inputs)
                predicted_depth = outputs.predicted_depth

            depth = self._torch.nn.functional.interpolate(
                predicted_depth.unsqueeze(1),
                size=(infer_height, infer_width),
                mode="bicubic",
                align_corners=False,
            ).squeeze()

            depth_map = depth.detach().cpu().numpy().astype(np.float32)
            self.last_infer_sec = time.time() - start_time

            depth_min = float(np.min(depth_map))
            depth_max = float(np.max(depth_map))
            depth_span = depth_max - depth_min

            if depth_span <= 1e-6:
                depth_norm = np.zeros_like(depth_map, dtype=np.float32)
            else:
                depth_norm = (depth_map - depth_min) / depth_span

            if depth_norm.shape[0] != height or depth_norm.shape[1] != width:
                depth_norm = cv2.resize(depth_norm, (width, height), interpolation=cv2.INTER_LINEAR)

            roi_bbox = None
            roi_depth_value = None
            roi_confidence = 0.0

            if bbox is not None:
                x1, y1, x2, y2 = bbox
                x1 = max(0, min(width - 1, int(x1)))
                y1 = max(0, min(height - 1, int(y1)))
                x2 = max(x1 + 1, min(width, int(x2)))
                y2 = max(y1 + 1, min(height, int(y2)))

                if x2 > x1 and y2 > y1:
                    roi = depth_norm[y1:y2, x1:x2]
                    if roi.size > 0:
                        roi_depth_value = float(np.median(roi))
                        roi_confidence = float(np.std(roi))
                        roi_bbox = (x1, y1, x2, y2)

            return {
                "ok": True,
                "relative_depth": roi_depth_value,
                "depth_confidence": roi_confidence,
                "bbox": roi_bbox,
                "inference_sec": self.last_infer_sec,
                "depth_map_norm": depth_norm,
            }
        except Exception as exc:
            self.error = str(exc)
            self.available = False
            return {
                "ok": False,
                "error": self.error,
            }

    @staticmethod
    def build_colormap(depth_map_norm):
        if depth_map_norm is None:
            return None

        depth_u8 = np.clip(depth_map_norm * 255.0, 0, 255).astype(np.uint8)
        return cv2.applyColorMap(depth_u8, cv2.COLORMAP_INFERNO)
