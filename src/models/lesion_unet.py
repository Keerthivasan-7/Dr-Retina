"""U-Net(s) for the lesion segmentation head (P2.2).

Two variants:
- `LesionUNet` / `build_lesion_model`: compact from-scratch U-Net. Was the
  right call when the only data was IDRiD's 54 training images (a bigger
  encoder would overfit even faster). Still used for the Optic Disc-focused
  whole-image runs, where it already gets 0.842 dice.
- `build_pretrained_lesion_model`: U-Net with an ImageNet-pretrained
  ResNet-34 encoder (via segmentation_models_pytorch), for the merged
  IDRiD+DDR+e-ophtha lesion-only (MA/HE/EX/SE) model. With ~1300 training
  rows now available and microaneurysms specifically needing to discriminate
  subtle low-contrast texture from background, transfer learning from
  ImageNet features is worth the added parameters — this is standard
  practice in the literature for this exact problem (Attention U-Net,
  ResNet50-UNet, etc. per published microaneurysm-segmentation benchmarks),
  and still a compact CNN encoder (README ground rule #3 restricts
  transformer/foundation models for the *production grading* backbone, not
  segmentation encoder choice — ResNet-34 is the same CNN family already
  used for DR grading).
"""
from __future__ import annotations

import torch
import torch.nn as nn


def _conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
    )


class LesionUNet(nn.Module):
    def __init__(self, in_channels: int = 3, num_classes: int = 5, base_channels: int = 32):
        super().__init__()
        c = base_channels
        self.enc1 = _conv_block(in_channels, c)
        self.enc2 = _conv_block(c, c * 2)
        self.enc3 = _conv_block(c * 2, c * 4)
        self.enc4 = _conv_block(c * 4, c * 8)
        self.pool = nn.MaxPool2d(2)

        self.bottleneck = _conv_block(c * 8, c * 16)

        self.up4 = nn.ConvTranspose2d(c * 16, c * 8, 2, stride=2)
        self.dec4 = _conv_block(c * 16, c * 8)
        self.up3 = nn.ConvTranspose2d(c * 8, c * 4, 2, stride=2)
        self.dec3 = _conv_block(c * 8, c * 4)
        self.up2 = nn.ConvTranspose2d(c * 4, c * 2, 2, stride=2)
        self.dec2 = _conv_block(c * 4, c * 2)
        self.up1 = nn.ConvTranspose2d(c * 2, c, 2, stride=2)
        self.dec1 = _conv_block(c * 2, c)

        self.head = nn.Conv2d(c, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))

        d4 = self.dec4(torch.cat([self.up4(b), e4], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.head(d1)  # raw logits, one channel per lesion type


def build_lesion_model(num_classes: int = 5, base_channels: int = 32) -> LesionUNet:
    return LesionUNet(in_channels=3, num_classes=num_classes, base_channels=base_channels)


def build_pretrained_lesion_model(num_classes: int = 4, encoder_name: str = "resnet34") -> nn.Module:
    import segmentation_models_pytorch as smp
    return smp.Unet(
        encoder_name=encoder_name,
        encoder_weights="imagenet",
        in_channels=3,
        classes=num_classes,
        activation=None,  # raw logits — loss functions apply sigmoid themselves
    )
