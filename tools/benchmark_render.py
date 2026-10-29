"""Benchmark de pintura dos widgets animados, sem depender de logs historicos.

Mede o tempo de `render()` (paintEvent) em modo offscreen e pode salvar/comparar
uma imagem de referencia para garantir que a otimizacao nao muda os pixels.

Uso:
    python tools/benchmark_render.py                # mede os tres widgets
    python tools/benchmark_render.py --save logs/render_bench
    python tools/benchmark_render.py --compare logs/render_bench
    python tools/benchmark_render.py --frames 120 --only orbital

Saida: mediana em ms por widget. Codigo 0 sempre que conseguir medir; a
comparacao de imagem imprime a diferenca media por canal (0.0 = identico).
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PySide6.QtGui import QFontDatabase, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.briefing_scene import BriefingBackdrop  # noqa: E402
from ui.futuristic_face import FuturisticFaceWidget  # noqa: E402
from ui.neural_core import NeuralCoreWidget  # noqa: E402

CASES = {
    "orbital": (BriefingBackdrop, (1180, 720)),
    "face": (FuturisticFaceWidget, (690, 620)),
    "neural": (NeuralCoreWidget, (500, 500)),
}


def medir(classe, tamanho: tuple[int, int], frames: int, theme: str | None = None):
    widget = classe(None) if theme is None else classe(None, theme=theme)
    widget.resize(*tamanho)
    widget.show()
    app = QApplication.instance()
    app.processEvents()
    if hasattr(widget, "timer"):
        widget.timer.stop()
    for state in ("READY", "LISTENING", "PROCESSING", "SPEAKING", "ERROR"):
        widget.set_state(state)
    widget.set_state("SPEAKING")
    if hasattr(widget, "speech_level"):
        widget.speech_level = 0.4
    widget.phase = 1.25
    imagem = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)

    for frame in range(5):  # aquecimento
        widget.phase = 1.25 + frame * 0.01
        widget.render(imagem)

    tempos = []
    for frame in range(frames):
        widget.phase = 1.25 + frame * 0.01
        inicio = time.perf_counter()
        widget.render(imagem)
        tempos.append((time.perf_counter() - inicio) * 1000)

    # Repintura parcial: o timer real chama update(regiao), nao a tela toda.
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QRegion

    regiao = QRegion(QRect(0, 0, widget.width() // 2, widget.height() // 2).translated(
        widget.width() // 4, widget.height() // 4))
    tempos_regiao = []
    for frame in range(frames):
        widget.phase = 1.25 + 1.0 + frame * 0.01
        inicio = time.perf_counter()
        widget.render(imagem, QPoint(0, 0), regiao)
        tempos_regiao.append((time.perf_counter() - inicio) * 1000)

    widget.close()
    widget.deleteLater()
    app.processEvents()
    return widget, imagem, statistics.median(tempos), statistics.median(tempos_regiao)


def imagem_para_array(imagem: QImage) -> np.ndarray:
    return np.frombuffer(imagem.constBits(), dtype=np.uint8).astype(np.int16)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark de pintura dos widgets do V")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--only", choices=sorted(CASES), action="append")
    parser.add_argument("--save", type=Path, help="salva PNG de referencia nesta pasta")
    parser.add_argument("--compare", type=Path, help="compara com PNG salvo nesta pasta")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    for nome in ("segoeui.ttf", "segoeuib.ttf"):
        fonte = Path("C:/Windows/Fonts") / nome
        if fonte.exists():
            QFontDatabase.addApplicationFont(str(fonte))

    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
    if args.compare and not args.compare.exists():
        print(f"referencia inexistente: {args.compare} (rode com --save primeiro)")
        return 2

    widgets = args.only or list(CASES)
    pior = 0.0
    for nome in widgets:
        classe, tamanho = CASES[nome]
        _, imagem, mediana, mediana_regiao = medir(classe, tamanho, args.frames)
        linha = (
            f"{nome:8s} {tamanho[0]}x{tamanho[1]}  "
            f"tela_cheia={mediana:6.2f} ms  regiao={mediana_regiao:6.2f} ms  "
            f"({1000/mediana:5.1f} fps tela cheia)"
        )
        pior = max(pior, mediana)

        if args.save:
            destino = args.save / f"{nome}.png"
            imagem.save(str(destino))
            linha += f"  salvo={destino.name}"

        if args.compare:
            referencia = QImage(str(args.compare / f"{nome}.png"))
            if referencia.isNull():
                linha += "  referencia ilegivel"
            else:
                diff = np.abs(imagem_para_array(imagem) - imagem_para_array(referencia))
                linha += (
                    f"  diff_medio={diff.mean():.6f}"
                    f"  pixels_alterados={np.count_nonzero(diff) / diff.size * 100:.3f}%"
                )
        print(linha)

    print(f"\npior mediana: {pior:.2f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
