import matplotlib
import matplotlib.axes
import matplotlib.figure
import numpy as np


def set_plot_area_aspect(
    ax: (
        list[matplotlib.axes.Axes | matplotlib.figure.Figure]
        | matplotlib.figure.Figure
        | matplotlib.axes.Axes
    ),
    ratio: float = 1.6180339887,
    adjustable="box",
    anchor="NE",
):
    if isinstance(ax, matplotlib.axes.Axes):
        return _set_plot_area_aspect(ax, ratio, adjustable=adjustable, anchor=anchor)
    elif isinstance(ax, matplotlib.figure.Figure):
        return _set_plot_area_aspect(ax.get_axes(), ratio, adjustable=adjustable, anchor=anchor)
    elif isinstance(ax, list):
        return [_set_plot_area_aspect(a, ratio, adjustable=adjustable, anchor=anchor) for a in ax]
    elif isinstance(ax, np.ndarray):
        return [
            _set_plot_area_aspect(a, ratio, adjustable=adjustable, anchor=anchor)
            for a in np.ravel(ax)
        ]
    assert (
        False
    ), f"Invalid type for ax. Expected Axes, Figure, or list of Axes/Figures, got {type(ax) = }"


def _set_plot_area_aspect(ax: matplotlib.axes.Axes, ratio, adjustable, anchor):
    """
    Sets the aspect ratio of the plot area to the specified ratio.

    This function modifies a matplotlib Axes object to make the plot area
    have the desired width-to-height ratio, accounting for data limits.

    """
    # Get current data limits
    x_left, x_right = ax.get_xlim()
    y_low, y_high = ax.get_ylim()

    # Calculate the aspect value to achieve desired display ratio
    # set_aspect() expects a y/x ratio, but our ratio parameter is width/height (x/y)
    # So we need to use 1/ratio and adjust for the current data range
    x_mod, y_mod = (lambda x: x), (lambda y: y)
    if ax.get_xscale() == "log":
        x_mod = np.log10
    if ax.get_yscale() == "log":
        y_mod = np.log10
    aspect_value = (1 / ratio) * abs(
        (x_mod(x_right) - x_mod(x_left)) / (y_mod(y_high) - y_mod(y_low))
    )

    # Set the aspect ratio
    ax.set_aspect(aspect_value, adjustable=adjustable, anchor=anchor)

    return ax
