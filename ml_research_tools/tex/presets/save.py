import os

import matplotlib
import matplotlib.figure


def savefig(fig: matplotlib.figure.Figure, fname, *, transparent=None, **kwargs):
    fname = os.path.expanduser(fname)
    kwargs.setdefault("bbox_inches", "tight")
    kwargs.setdefault("pad_inches", "layout")
    if fname.endswith(".svg"):
        kwargs.setdefault("backend", "svglatex")
    kwargs.setdefault("dpi", 72)
    fig.savefig(fname=fname, transparent=transparent, **kwargs)
