"""Compact U-Net (own implementation, no external segmentation library).

Input: (B, C, H, W) features from pipeline.feature_stack (before, after, difference, validity).
Output: (B, H, W) logits for 'newly cleared'.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class DoubleConv(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))

    def forward(self, x):
        return self.net(x)


class UNet(nn.Module):
    def __init__(self, in_channels: int, base: int = 24, depth: int = 4):
        super().__init__()
        chs = [base * 2 ** i for i in range(depth + 1)]
        self.inc = DoubleConv(in_channels, chs[0])
        self.downs = nn.ModuleList([DoubleConv(chs[i], chs[i + 1]) for i in range(depth)])
        self.ups = nn.ModuleList([DoubleConv(chs[i + 1] + chs[i], chs[i]) for i in reversed(range(depth))])
        self.out = nn.Conv2d(chs[0], 1, 1)

    def forward(self, x):
        skips = [self.inc(x)]
        for down in self.downs:
            skips.append(down(F.max_pool2d(skips[-1], 2)))
        x = skips.pop()
        for up in self.ups:
            s = skips.pop()
            x = F.interpolate(x, size=s.shape[-2:], mode="bilinear", align_corners=False)
            x = up(torch.cat([s, x], dim=1))
        return self.out(x).squeeze(1)


def dice_bce_loss(logits, target, pos_weight: float = 1.0):
    bce = F.binary_cross_entropy_with_logits(
        logits, target, pos_weight=torch.tensor(pos_weight, device=logits.device))
    p = torch.sigmoid(logits)
    inter = (p * target).sum(dim=(1, 2))
    dice = 1 - (2 * inter + 1) / (p.sum(dim=(1, 2)) + target.sum(dim=(1, 2)) + 1)
    return bce + dice.mean()
