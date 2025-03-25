from matplotlib.backend_bases import _Backend

from .svg_patch import FigureCanvasInkSVG, FigureManagerInkSVG, _config


@_Backend.export
class _BackendSvgTeX(_Backend):
    FigureCanvas = FigureCanvasInkSVG
    FigureManager = FigureManagerInkSVG


def set_property(key, value):
    setattr(_config, key, value)
