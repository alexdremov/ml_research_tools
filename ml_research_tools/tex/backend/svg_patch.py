import codecs
import logging
import math
import re
from dataclasses import dataclass, field

import numpy as np
from matplotlib import cbook
from matplotlib import font_manager as fm
from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_mixed import MixedModeRenderer
from matplotlib.backends.backend_svg import FigureCanvasSVG, RendererSVG
from matplotlib.colors import rgb2hex
from matplotlib.transforms import Affine2DBase

logger = logging.getLogger(__name__)


def replace_texcmd(s):
    s = s.replace(r"\mathdefault", "").replace("\u2212", "-")
    return s


def _short_float_fmt(x):
    """
    Create a short string representation of a float, which is %f
    formatting with trailing zeros and the decimal point removed.
    """
    return f"{x:f}".rstrip("0").rstrip(".")


def _generate_css(attrib):
    return "; ".join(f"{k}: {v}" for k, v in attrib.items())


def _generate_transform(transform_list):
    parts = []
    for type, value in transform_list:
        if (
            type == "scale"
            and (value == (1,) or value == (1, 1))
            or type == "translate"
            and value == (0, 0)
            or type == "rotate"
            and value == (0,)
        ):
            continue
        if type == "matrix" and isinstance(value, Affine2DBase):
            value = value.to_values()
        parts.append("{}({})".format(type, " ".join(_short_float_fmt(x) for x in value)))
    return " ".join(parts)


def transform_text_between_dollars(text, transform_func):
    """
    Finds text enclosed between non-escaped dollar signs, applies the given
    transformation function to that text, and returns the transformed string.

    Args:
        text (str): The input text containing dollar-enclosed sections
        transform_func (callable): Function to apply to matched content

    Returns:
        str: Text with transformations applied to dollar-enclosed sections
    """

    def replace_func(match):
        # Extract the matched text (without the dollar signs)
        matched_text = match.group(1)
        # Apply the transformation
        transformed_text = transform_func(matched_text)
        # Return the transformed text surrounded by dollar signs
        return "$" + transformed_text + "$"

    # Pattern explanation:
    # (?<!\\)\$ - Match a dollar sign that is NOT preceded by a backslash
    # (.*?)     - Capture any characters (non-greedy) between the dollar signs
    # (?<!\\)\$ - Match a closing dollar sign that is NOT preceded by a backslash
    pattern = r"(?<!\\)\$(.*?)(?<!\\)\$"

    # Apply the transformation using re.sub with the replacement function
    result = re.sub(pattern, replace_func, text)

    return result


@dataclass
class SvgInkConfig:
    ignore_font_size: bool = field(default=False, metadata={"help": "Ignore font size"})
    ignore_weight: bool = field(default=False, metadata={"help": "Ignore font weight"})
    ignore_color: bool = field(default=False, metadata={"help": "Ignore text color"})
    ignore_alpha: bool = field(default=False, metadata={"help": "Ignore alpha channel"})
    ignore_style: bool = field(default=False, metadata={"help": "Ignore italic and oblique styles"})
    font_scale: float = field(default=1.0, metadata={"help": "Scale factor for font size"})


_config = SvgInkConfig()


class RendererInkSVG(RendererSVG):
    def _draw_text_as_text(self, gc, x, y, s, prop, angle, ismath, mtext=None):
        writer = self.writer

        final_tex_text = replace_texcmd(s)

        color = rgb2hex(gc.get_rgb())
        if color != "#000000" and not _config.ignore_color:
            color = color.lstrip("#").upper()
            color = r"\color[HTML]{" + color + "}"
            final_tex_text = "{" + color + s + "}"

        alpha = gc.get_alpha() if gc.get_forced_alpha() else gc.get_rgb()[3]
        if alpha != 1 and not _config.ignore_alpha:
            alpha = r"\transparent{" + str(alpha) + "}"
            final_tex_text = "{" + alpha + s + "}"

        # Separate font style in their separate attributes
        if _config.ignore_style:
            pass
        elif prop.get_style() == "italic":
            final_tex_text = r"\emph{" + final_tex_text + "}"
        elif prop.get_style() == "oblique":
            final_tex_text = r"\textsl{" + final_tex_text + "}"

        if prop.get_variant() != "normal":
            logger.warning("variant not supported in SVG backend")

        weight = fm.weight_dict[prop.get_weight()]
        if weight > 400 and not _config.ignore_weight:
            final_tex_text = r"\textbf{" + final_tex_text + "}"
            f = lambda x: r"\bm{" + x + "}"
            final_tex_text = transform_text_between_dollars(final_tex_text, f)

        if not _config.ignore_font_size:
            scale = _config.font_scale
            font_size = _short_float_fmt(math.floor(prop.get_size() * scale))
            lineheight = _short_float_fmt(math.floor(prop.get_size() * scale * 1.2))
            font_size_modifier = (
                r"\fontsize{" + str(font_size) + "}{" + str(lineheight) + r"}\selectfont"
            )
            final_tex_text = "{" + font_size_modifier + " " + final_tex_text + "}"

        attrib = {}
        font_style = {}
        if prop.get_stretch() != "normal":
            font_style["font-stretch"] = prop.get_stretch()
        attrib["style"] = _generate_css({**font_style})

        if mtext and (angle == 0 or mtext.get_rotation_mode() == "anchor"):
            # If text anchoring can be supported, get the original
            # coordinates and add alignment information.

            # Get anchor coordinates.
            transform = mtext.get_transform()
            ax, ay = transform.transform(mtext.get_unitless_position())
            ay = self.height - ay

            # Don't do vertical anchor alignment. Most applications do not
            # support 'alignment-baseline' yet. Apply the vertical layout
            # to the anchor point manually for now.
            angle_rad = np.deg2rad(angle)
            dir_vert = np.array([np.sin(angle_rad), np.cos(angle_rad)])
            v_offset = np.dot(dir_vert, [(x - ax), (y - ay)])
            ax = ax + v_offset * dir_vert[0]
            ay = ay + v_offset * dir_vert[1]

            ha_mpl_to_svg = {"left": "start", "right": "end", "center": "middle"}
            font_style = {}
            font_style["text-anchor"] = ha_mpl_to_svg[mtext.get_ha()]

            attrib["x"] = _short_float_fmt(ax)
            attrib["y"] = _short_float_fmt(ay)
            attrib["style"] = _generate_css(
                {
                    **font_style,
                }
            )
            attrib["transform"] = _generate_transform([("rotate", (-angle, ax, ay))])

        else:
            attrib["transform"] = _generate_transform(
                [("translate", (x, y)), ("rotate", (-angle,))]
            )

        writer.element("text", final_tex_text, attrib=attrib)

    def draw_text(self, gc, x, y, s, prop, angle, ismath=False, mtext=None):
        clip_attrs = self._get_clip_attrs(gc)
        if clip_attrs:
            self.writer.start("g", **clip_attrs)

        if gc.get_url() is not None:
            self.writer.start("a", {"xlink:href": gc.get_url()})

        self._draw_text_as_text(gc, x, y, s, prop, angle, ismath, mtext)

        if gc.get_url() is not None:
            self.writer.end("a")

        if clip_attrs:
            self.writer.end("g")


class FigureCanvasInkSVG(FigureCanvasSVG):
    fixed_dpi = None

    def print_svg(self, filename, *, bbox_inches_restore=None, metadata=None, **kwargs):
        with cbook.open_file_cm(filename, "w", encoding="utf-8") as fh:
            if not cbook.file_requires_unicode(fh):
                fh = codecs.getwriter("utf-8")(fh)
            dpi = self.figure.dpi
            width, height = self.figure.get_size_inches()
            w, h = width * dpi, height * dpi
            renderer = MixedModeRenderer(
                self.figure,
                width,
                height,
                dpi,
                RendererInkSVG(w, h, fh, image_dpi=dpi, metadata=metadata),
                bbox_inches_restore=bbox_inches_restore,
            )
            self.figure.draw(renderer)
            renderer.finalize()


class FigureManagerInkSVG(FigureManagerBase):
    pass
