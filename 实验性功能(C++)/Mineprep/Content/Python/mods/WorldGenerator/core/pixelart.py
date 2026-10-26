"""Image-only palette selection and edge-aware grouping of actual block labels."""
import numpy as np

from .voxel import match_colors


def _palette(rgb, palette_rgb, count):
    """Greedily reduce Lab error using real block colours, with bounded fitting data."""
    import cv2
    sample_count = min(len(rgb), 16_384, max(1, 1_048_576//len(palette_rgb)))
    samples = rgb[np.linspace(0, len(rgb)-1, sample_count, dtype=int)]
    samples = cv2.cvtColor(samples.astype(np.float32)[None]/255., cv2.COLOR_RGB2LAB)[0]
    target = cv2.cvtColor(palette_rgb.astype(np.float32)[None]/255., cv2.COLOR_RGB2LAB)[0]
    distances = np.empty((sample_count, len(target)), np.float32)
    for start in range(0, len(target), 64):
        distances[:, start:start+64] = np.sum((samples[:, None]-target[None, start:start+64])**2, axis=2)
    selected = []
    best = None
    for _ in range(count):
        scores = (distances.mean(axis=0) if best is None else
                  -np.maximum(best[:, None]-distances, 0).mean(axis=0))
        scores[selected] = np.inf
        chosen = int(np.argmin(scores))
        if best is not None and scores[chosen] >= 0:
            break
        selected.append(chosen)
        distance = distances[:, chosen]
        best = distance if best is None else np.minimum(best, distance)
    return np.sort(selected)


def image_types(image, visible, palette_rgb, *, colors, smooth):
    """Return palette IDs for visible pixels; alpha/depth and source RGB stay intact."""
    rgb = image[visible, :3]
    if not len(rgb):
        return np.empty(0, np.uint16)
    chosen = (np.arange(len(palette_rgb)) if colors is None or colors >= len(palette_rgb)
              else _palette(rgb, palette_rgb, colors))
    ids = chosen[match_colors(rgb, palette_rgb[chosen])].astype(np.uint16)
    if smooth == 0:
        return ids

    import cv2
    data = cv2.cvtColor(image[..., :3].astype(np.float32)/255., cv2.COLOR_RGB2LAB)
    target = cv2.cvtColor(palette_rgb.astype(np.float32)[None]/255., cv2.COLOR_RGB2LAB)[0]
    height, width = visible.shape
    labels = np.zeros((height, width), np.uint16)
    labels[visible] = ids
    valid = np.pad(visible, 1)
    padded_data = np.pad(data, ((1, 1), (1, 1), (0, 0)), mode='edge')
    shifts = ((0, 1), (2, 1), (1, 0), (1, 2))
    neighbors_valid = [valid[y:y+height, x:x+width] for y, x in shifts]
    # Similar source colours prefer shared labels; strong source edges reduce this weight.
    weights = [mask*np.exp(-np.sum((padded_data[y:y+height, x:x+width]-data)**2, axis=2)/800.)
               for (y, x), mask in zip(shifts, neighbors_valid)]
    parity = np.indices(visible.shape).sum(axis=0) % 2
    for _ in range(2):
        for phase in (0, 1):
            padded = np.pad(labels, 1, mode='edge')
            neighbors = [np.where(mask, padded[y:y+height, x:x+width], labels)
                         for (y, x), mask in zip(shifts, neighbors_valid)]

            def cost(candidate):
                error = np.sum((target[candidate]-data)**2, axis=2)
                return error + smooth*800*sum(weight*(candidate != other)
                                              for weight, other in zip(weights, neighbors))

            best, result = cost(labels), labels.copy()
            for candidate in neighbors:
                error = cost(candidate)
                use = error < best-1e-5
                best = np.where(use, error, best)
                result = np.where(use, candidate, result)
            # Alternating grid parity avoids synchronous label-flipping on checkerboards.
            labels = np.where(visible & (parity == phase), result, labels)
    return labels[visible]
