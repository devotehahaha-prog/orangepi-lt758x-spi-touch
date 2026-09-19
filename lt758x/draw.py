#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""绘图 API: 填充/线/框/像素/图片(BMP/PNG/JPG)
画布为24bpp(3字节/像素), 字节序见 config.COLOR_ORDER
"""
from PIL import Image
from . import config as C


def rgb(r, g, b):
    """返回显存字节序的 bytes"""
    m = {"R": r, "G": g, "B": b}
    return bytes(m[k] for k in C.COLOR_ORDER)


class Draw:
    def __init__(self, panel):
        self.panel = panel
        self.core = panel.core
        self.w = panel.w
        self.h = panel.h

    # ---- 底层窗口 ----
    def set_window(self, x, y, w, h):
        self.panel.active_xy(x, y)
        self.panel.active_wh(w, h)
        self.panel.goto_xy(x, y)
        self.core.cmd(0x04)                          # 指向显存写端口

    def _clip(self, x, y, w, h):
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(self.w, x + w), min(self.h, y + h)
        return x1, y1, max(0, x2 - x1), max(0, y2 - y1)

    # ---- 填充 ----
    def fill_rect(self, x, y, w, h, color):
        """color: rgb() 返回的 3 字节；自动裁剪到屏幕范围。"""
        if len(color) != 3:
            raise ValueError("color must contain three bytes")
        x, y, w, h = self._clip(x, y, w, h)
        if not w or not h:
            return
        band = max(1, 100_000 // (w * 3))
        for yy in range(0, h, band):
            n = min(band, h - yy)
            self.set_window(x, y + yy, w, n)
            self.core.burst(bytes(color) * (w * n))

    def clear(self, color):
        self.fill_rect(0, 0, self.w, self.h, color)

    # ---- 几何 ----
    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.fill_rect(x, y, 1, h, color)

    def rect(self, x, y, w, h, color, thickness=1):
        if w <= 0 or h <= 0 or thickness <= 0:
            return
        t = min(thickness, w, h)
        self.fill_rect(x, y, w, t, color)
        self.fill_rect(x, y + h - t, w, t, color)
        self.fill_rect(x, y + t, t, h - 2 * t, color)
        self.fill_rect(x + w - t, y + t, t, h - 2 * t, color)

    def put_pixel(self, x, y, color):
        self.fill_rect(x, y, 1, 1, color)

    # ---- 图片 ----
    def image(self, img: Image.Image, x=0, y=0, w=None, h=None):
        """推送 PIL Image(自动缩放到 w,h), 支持任意模式"""
        if w is None:
            w = self.w - x
        if h is None:
            h = self.h - y
        if w <= 0 or h <= 0:
            return
        if img.size != (w, h):
            img = img.convert("RGB").resize((w, h), Image.LANCZOS)
        self.flush_area(x, y, w, h, img.convert("RGB").tobytes())

    def image_file(self, path, x=0, y=0, w=None, h=None):
        with Image.open(path) as img:
            self.image(img, x, y, w, h)

    # ---- 帧缓冲风格整帧刷新(给 LVGL/软件层预留的接口) ----
    def flush_area(self, x, y, w, h, rgb888_bytes):
        """直接推送 RGB888 原始数据(行优先), 供上层渲染引擎对接"""
        if w <= 0 or h <= 0:
            return
        if len(rgb888_bytes) != w * h * 3:
            raise ValueError("RGB888 buffer size does not match width and height")
        cx, cy, cw, ch = self._clip(x, y, w, h)
        if not cw or not ch:
            return
        m = {"R": 0, "G": 1, "B": 2}
        order = tuple(m[k] for k in C.COLOR_ORDER)
        band = max(1, 100_000 // (cw * 3))
        source = memoryview(rgb888_bytes)
        for yy in range(0, ch, band):
            n = min(band, ch - yy)
            data = b"".join(source[((cy - y + yy + row) * w + cx - x) * 3:
                                  ((cy - y + yy + row) * w + cx - x + cw) * 3]
                            for row in range(n))
            out = bytearray(len(data))
            for di, si in enumerate(order):
                out[di::3] = data[si::3]
            self.set_window(cx, cy + yy, cw, n)
            self.core.burst(out)
