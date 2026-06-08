from collections import namedtuple

# Define a named tuple for the size
PaperSize = namedtuple(
    "PaperSize", ["width", "height", "width_mm", "height_mm", "width_in", "height_in"]
)


def calculate_a_paper_sizes(max_size: int = 10) -> dict[str, PaperSize]:
    """
    Calculates ISO A-series paper sizes from A0 up to `max_size`.
    Returns dimensions in millimeters by default, or inches if `in_inches` is True.
    """
    # Calculate initial A0 size in millimeters
    width = int(1000 / 2 ** (1 / 4) + 0.5)
    height = int(1000 * 2 ** (1 / 4) + 0.5)

    result = {}
    for i in range(max_size + 1):
        width_in = width / 25.4
        height_in = height / 25.4
        result[f"A{i}"] = PaperSize(
            width_in,
            height_in,
            width,
            height,
            width_in,
            height_in,
        )

        # ISO 216 dictates halving the larger dimension and flooring to the nearest mm.
        width, height = height // 2, width

    return result


PAPER_SIZES = calculate_a_paper_sizes()
