# Minimal pix2struct.metrics shim for DePlot evaluation.
# Only implements anls_metric, which deplot/metrics.py uses.

from Levenshtein import distance as levenshtein_distance  # from python-Levenshtein


def anls_metric(prediction: str, target: str, text_theta: float = 0.5) -> float:
    """Approximate ANLS similarity (as used in Pix2Struct/DePlot).

    Returns a value in [0, 1], where 1 is an exact match.

    - Compute normalized Levenshtein distance between prediction and target.
    - If distance > text_theta, treat as completely wrong (similarity 0).
    - Otherwise similarity = 1 - distance.
    """
    prediction = prediction or ""
    target = target or ""
    if not prediction and not target:
        return 1.0

    max_len = max(len(prediction), len(target))
    if max_len == 0:
        return 1.0

    dist = levenshtein_distance(prediction, target) / max_len
    if dist > text_theta:
        return 0.0
    return 1.0 - dist
