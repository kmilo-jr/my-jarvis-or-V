"""Local object detection. No camera, network, storage or action execution here."""
from __future__ import annotations
from app_paths import ROOT

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
import unicodedata

import numpy as np
from PIL import Image

MODEL = ROOT / 'models/vision/yolox_nano.onnx'
MODEL_SHA256 = 'c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d'
LABELS = ('pessoa|bicicleta|carro|moto|avião|ônibus|trem|caminhão|barco|semáforo|hidrante|'
          'placa de pare|parquímetro|banco|pássaro|gato|cachorro|cavalo|ovelha|vaca|elefante|'
          'urso|zebra|girafa|mochila|guarda-chuva|bolsa|gravata|mala|frisbee|esquis|snowboard|'
          'bola|pipa|taco de beisebol|luva de beisebol|skate|prancha de surfe|raquete|garrafa|'
          'taça|copo|garfo|faca|colher|tigela|banana|maçã|sanduíche|laranja|brócolis|cenoura|'
          'cachorro-quente|pizza|rosquinha|bolo|cadeira|sofá|planta em vaso|cama|mesa|vaso sanitário|'
          'televisão|notebook|mouse|controle remoto|teclado|celular|micro-ondas|forno|torradeira|'
          'pia|geladeira|livro|relógio|vaso|tesoura|urso de pelúcia|secador de cabelo|escova de dentes').split('|')


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple[float, float, float, float]


from .vision_commands import vision_command


def summarize(detections):
    if not detections:
        return 'Não identifiquei objetos com confiança nesta imagem. Tente melhorar a luz ou aproximar o objeto.'
    counts = Counter(d.label for d in detections)
    parts = [f'{label} ({count})' for label, count in counts.items()]
    return 'Na imagem, detectei: ' + ', '.join(parts[:12]) + '.'


def decode(output, size, ratio, width, height, threshold=0.40):
    predictions = np.asarray(output, dtype=np.float32).copy()[0]
    grids, strides = [], []
    for stride in (8, 16, 32):
        x, y = np.meshgrid(np.arange(size // stride), np.arange(size // stride))
        grid = np.stack((x, y), axis=-1).reshape(-1, 2)
        grids.append(grid)
        strides.append(np.full((len(grid), 1), stride))
    grid, stride = np.concatenate(grids), np.concatenate(strides)
    if predictions.shape != (len(grid), 85):
        raise ValueError('Formato inesperado do modelo de visão.')
    predictions[:, :2] = (predictions[:, :2] + grid) * stride
    predictions[:, 2:4] = np.exp(np.clip(predictions[:, 2:4], -20, 20)) * stride
    scores = predictions[:, 4:5] * predictions[:, 5:]
    classes = scores.argmax(axis=1)
    confidence = scores.max(axis=1)
    valid = np.isfinite(predictions).all(axis=1) & (confidence >= threshold)
    predictions, confidence, classes = predictions[valid], confidence[valid], classes[valid]
    boxes = np.concatenate((predictions[:, :2] - predictions[:, 2:4] / 2,
                            predictions[:, :2] + predictions[:, 2:4] / 2), axis=1) / ratio
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, width)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, height)
    areas = np.maximum(0, boxes[:, 2] - boxes[:, 0]) * np.maximum(0, boxes[:, 3] - boxes[:, 1])
    order = np.argsort(confidence)[::-1]
    result = []
    while order.size and len(result) < 40:
        i = order[0]
        if areas[i] > 0:
            result.append(Detection(LABELS[int(classes[i])], float(confidence[i]), tuple(boxes[i])))
        rest = order[1:]
        intersection = np.maximum(0, np.minimum(boxes[i, 2:], boxes[rest, 2:]) -
                                  np.maximum(boxes[i, :2], boxes[rest, :2])).prod(axis=1)
        iou = intersection / np.maximum(areas[i] + areas[rest] - intersection, 1e-6)
        order = rest[(iou <= .45) | (classes[rest] != classes[i])]
    return result


class ObjectDetector:
    def __init__(self, model=MODEL):
        import onnxruntime as ort
        model = Path(model)
        if not model.is_file():
            raise RuntimeError('Modelo de objetos ausente: models/vision/yolox_nano.onnx.')
        if hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA256:
            raise RuntimeError('O modelo de objetos está corrompido ou foi substituído.')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        # Sleep between frames instead of keeping worker cores busy-waiting.
        options.add_session_config_entry('session.intra_op.allow_spinning', '0')
        options.add_session_config_entry('session.inter_op.allow_spinning', '0')
        self.session = ort.InferenceSession(str(model), sess_options=options,
                                           providers=['CPUExecutionProvider'])
        self.input = self.session.get_inputs()[0].name

    def detect(self, image: Image.Image):
        image = image.convert('RGB')
        width, height = image.size
        size = 416
        ratio = min(size / width, size / height)
        scaled = image.resize((max(1, int(width * ratio)), max(1, int(height * ratio))), Image.Resampling.BILINEAR)
        padded = np.full((size, size, 3), 114, dtype=np.uint8)
        padded[:scaled.height, :scaled.width] = np.asarray(scaled)[:, :, ::-1]
        tensor = np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32)
        output = self.session.run(None, {self.input: tensor})[0]
        return decode(output, size, ratio, width, height)
