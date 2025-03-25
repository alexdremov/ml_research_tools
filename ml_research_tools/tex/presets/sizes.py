from collections import namedtuple

# Define a named tuple for the size
PaperSize = namedtuple("PaperSize", ["width", "height"])


def calculate_a_paper_sizes(num_sizes=10) -> dict[str, PaperSize]:
    width = int(1000 / 2 ** (1 / 4) + 0.5) / 25.4
    height = int(1000 * 2 ** (1 / 4) + 0.5) / 25.4

    result = dict()
    for i in range(11):
        result[f"A{i}"] = PaperSize(width, height)
        width, height = height, width
        width //= 2
    return result


PAPER_SIZES = calculate_a_paper_sizes()
