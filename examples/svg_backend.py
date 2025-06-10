import matplotlib
import matplotlib.pyplot as plt

import ml_research_tools
from ml_research_tools.tex.backend import set_property as set_svg_property
from ml_research_tools.tex.presets import golden_figure, set_plot_area_aspect

matplotlib.rcParams.update(
    {
        "font.size": "10",
        "font.family": "cmr10",
    }
)

fig, ax = golden_figure(dpi=72)
ax.plot([0, 100, 10000], [0, 1, 2])
ax.set_xscale("log")
ax.set_xlabel("testing this font size aboba ababa baba lol", kerning_factor=5)

axim = ax.inset_axes([0.5, 0.5, 0.2, 0.2])
axim.imshow([[1, 2, 10], [3, 4, 10]])

set_plot_area_aspect(ax)
fig.savefig(
    "test_svg/images/test.svg",
    backend="module://ml_research_tools.tex.backend",
    bbox_inches="tight",
    pad_inches="layout",
)
fig.savefig("test_svg/images/test.png", bbox_inches="tight", pad_inches="layout")
print(fig.get_figwidth(), fig.get_figheight())
