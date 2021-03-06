import torch
import numpy as np

from mlx.od.centernet.utils import get_positions

def get_gaussian2d(positions, center, sigma):
    offsets = positions - center[:, None, None]
    return torch.exp(-(offsets ** 2).sum(0) / (2 * (sigma ** 2)))

# from https://github.com/xingyizhou/CenterNet/blob/819e0d0dde02f7b8cb0644987a8d3a370aa8206a/src/lib/utils/image.py
def gaussian_radius(det_size, min_overlap=0.7):
  height, width = det_size

  a1  = 1
  b1  = (height + width)
  c1  = width * height * (1 - min_overlap) / (1 + min_overlap)
  sq1 = np.sqrt(b1 ** 2 - 4 * a1 * c1)
  r1  = (b1 + sq1) / 2

  a2  = 4
  b2  = 2 * (height + width)
  c2  = (1 - min_overlap) * width * height
  sq2 = np.sqrt(b2 ** 2 - 4 * a2 * c2)
  r2  = (b2 + sq2) / 2

  a3  = 4 * min_overlap
  b3  = -2 * min_overlap * (height + width)
  c3  = (min_overlap - 1) * width * height
  sq3 = np.sqrt(b3 ** 2 - 4 * a3 * c3)
  r3  = (b3 + sq3) / 2
  return min(r1, r2, r3)

def encode(boxlists, positions, stride, num_labels, cfg):
    N = len(boxlists)
    device = boxlists[0].boxes.device
    h, w = positions.shape[1:]
    keypoint = torch.zeros((N, num_labels, h, w), device=device)
    reg = torch.zeros((N, 2, h, w), device=device)

    for n, boxlist in enumerate(boxlists):
        # skip offset for now
        boxes = boxlist.boxes
        labels = boxlist.get_field('labels')
        sizes = boxes[:, 2:] - boxes[:, 0:2]
        centers = boxes[:, 0:2] + sizes / 2

        # TODO vectorize this loop
        for center, size, label in zip(centers, sizes, labels):
            y, x = int(center[0] / stride), int(center[1] / stride)
            reg[n, :, y, x] = size
            keypoint[n, label, y, x] = 1.0

            mode = cfg.model.centernet.encoder.mode
            if mode == 'gaussian':
                radius = gaussian_radius(size.cpu().numpy())
                sigma = radius / 3
                gaussian2d = get_gaussian2d(positions, center, sigma)
                keypoint[n, label, :, :] = torch.max(keypoint[n, label, :, :], gaussian2d)
            elif mode == 'rectangle':
                radius = cfg.model.centernet.encoder.radius
                hrad = radius
                wrad = radius

                if radius < 0:
                    h, w = size
                    h, w = h.int().item(), w.int().item()
                    prop = 0.3
                    hrad = int(((h / stride) / 2.) * prop)
                    wrad = int(((w / stride) / 2.) * prop)
                min_y = max(0, y - hrad)
                min_x = max(0, x - wrad)
                max_y = min(h-1, y + hrad)
                max_x = min(w-1, x + wrad)

                keypoint[n, label, min_y:max_y+1, min_x:max_x+1] = 1.0

    return keypoint, reg
