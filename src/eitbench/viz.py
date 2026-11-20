import numpy as np


def rasterize(mesh, conductivity, size=128):
    """Interpolate on the supplied triangles, retaining holes and nonconvex edges."""
    low, high = mesh.nodes.min(axis=0), mesh.nodes.max(axis=0)
    xs = np.linspace(low[0], high[0], size)
    ys = np.linspace(high[1], low[1], size)
    x, y = np.meshgrid(xs, ys)
    image = np.zeros((size, size))
    mask = np.zeros((size, size), dtype=bool)
    for triangle, gradient in zip(mesh.triangles, mesh.grad):
        points = mesh.nodes[triangle]
        columns = np.flatnonzero(
            (xs >= points[:, 0].min()) & (xs <= points[:, 0].max())
        )
        rows = np.flatnonzero((ys >= points[:, 1].min()) & (ys <= points[:, 1].max()))
        if not len(columns) or not len(rows):
            continue
        region = np.ix_(rows, columns)
        xy = np.stack((x[region], y[region]), axis=-1)
        barycentric = (xy - points[0]) @ gradient.T
        barycentric[..., 0] += 1
        inside = np.all(barycentric >= -1e-12, axis=-1)
        image[region] = np.where(
            inside, barycentric @ conductivity[triangle], image[region]
        )
        mask[region] |= inside
    return image, mask


def save_preview(path, image, mask, background):
    from PIL import Image

    t = np.clip((image - 0.05 * background) / (1.9 * background), 0.0, 1.0)
    rgb = np.stack(
        (np.minimum(2 * t, 1.0), 1.0 - np.abs(2 * t - 1), np.minimum(2 * (1 - t), 1.0)),
        axis=-1,
    )
    rgb[~mask] = 1.0
    Image.fromarray(np.uint8(rgb * 255)).resize((512, 512)).save(path)
