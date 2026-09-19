#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文字渲染: 基于 Pillow, 支持中英文(自动选字体), 抗锯齿混合"""
import os
from PIL import Image, ImageDraw, ImageFont
from . import config as C
from .draw import rgb


def _first_font(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("未找到可用字体: %s" % paths)


class Text:
    def __init__(self, draw):
        self.draw = draw
        self.core = draw.core
        self._cache = {}
        self._font_cn = None
        self._font_ascii = None

    def _pick(self, s):
        """中文串用CJK字体, 纯ASCII用西文字体"""
        if any(ord(ch) > 0x7F for ch in s):
            if self._font_cn is None:
                self._font_cn = _first_font(C.FONT_CN)
            return self._font_cn
        if self._font_ascii is None:
            self._font_ascii = _first_font(C.FONT_ASCII)
        return self._font_ascii

    def _font(self, s, size):
        key = (self._pick(s), size)
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(key[0], size)
        return self._cache[key]

    def measure(self, s, size=24):
        f = self._font(s, size)
        x0, y0, x1, y1 = f.getbbox(s)
        return x1 - x0, y1 - y0

    def text(self, x, y, s, size=24, color=(255, 255, 255), bg=(0, 0, 0)):
        """绘制一行文字(自动混合背景色)"""
        f = self._font(s, size)
        x0, y0, x1, y1 = f.getbbox(s)
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0:
            return (x, y)
        # 渲染 alpha 遮罩
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).text((-x0, -y0), s, font=f, fill=255)
        # bytes 来自 rgb()，按显存顺序；tuple 使用通常的 RGB 顺序。
        def as_rgb(value):
            if isinstance(value, (bytes, bytearray)):
                channels = dict(zip(C.COLOR_ORDER, value))
                return tuple(channels[k] for k in ("R", "G", "B"))
            return tuple(value)
        foreground = Image.new("RGB", (w, h), as_rgb(color))
        background = Image.new("RGB", (w, h), as_rgb(bg))
        img = Image.composite(foreground, background, mask)
        self.draw.flush_area(x, y, w, h, img.tobytes())
        return (x + w, y)
