import matplotlib
import matplotlib.axes
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np

from .sizes import PAPER_SIZES

_default_margins_mul = 1.1


def golden_figure(
    colwidth=PAPER_SIZES["A4"].width / 2 / _default_margins_mul,
    ratio=1.6180339887,
    figsize=None,
    layout="constrained",
    dpi=72,
    **kwargs,
) -> tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]:
    """
    Create a figure with a golden ratio aspect ratio.

    Parameters:
        figsize (tuple): Size of the figure in inches (width, height).
        colwidth (float): Column width in inches.
        ratio (float): Aspect ratio for the figure.
        **kwargs: Additional keyword arguments for plt.figure.

    Returns:
        Figure: A matplotlib figure object.
    """
    if figsize is None:
        figsize = (
            colwidth,
            colwidth / ratio,
        )  # width, height in inches

    fig, axs = golden_subplots(
        nrows=1,
        ncols=1,
        figsize=figsize,
        colwidth=colwidth,
        ratio=ratio,
        layout=layout,
        dpi=dpi,
        **kwargs,
    )
    if isinstance(axs, np.ndarray):
        axs = axs[0]
    return fig, axs


def golden_subplots(
    nrows=1,
    ncols=1,
    colwidth=PAPER_SIZES["A4"].width / 2 / _default_margins_mul,
    ratio=1.6180339887,
    figsize=None,
    layout="constrained",
    dpi=72,
    **kwargs,
) -> tuple[matplotlib.figure.Figure, np.ndarray]:
    """
    Create subplots with a golden ratio aspect ratio.

    Parameters:
        nrows (int): Number of rows of subplots.
        ncols (int): Number of columns of subplots.
        figsize (tuple): Size of the figure in inches (width, height).
        ratio (float): Aspect ratio for the figure.
        **kwargs: Additional keyword arguments for plt.subplots.

    Returns:
        tuple: Figure and array of Axes objects.
    """
    if figsize is None:
        figsize = (
            colwidth * ncols,
            colwidth / ratio * nrows,
        )  # width, height in inches
    return plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize, layout=layout, dpi=dpi, **kwargs)
