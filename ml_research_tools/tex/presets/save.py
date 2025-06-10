import matplotlib
import matplotlib.figure


def savefig(fig: matplotlib.figure.Figure, fname, *, transparent=None, **kwargs):
    kwargs.setdefault("bbox_inches", "tight")
    kwargs.setdefault("pad_inches", "layout")
    kwargs.setdefault("backend", "svglatex")
    kwargs.setdefault("dpi", 72)
    fig.savefig(fname=fname, transparent=transparent, **kwargs)
