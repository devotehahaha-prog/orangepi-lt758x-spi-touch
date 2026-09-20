#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LT758x SPI 显示/触摸驱动包 (800×480 @ Orange Pi 5 Pro)

快速上手:
    from lt758x import Panel, Draw, Text, GT911, rgb
    panel = Panel(); panel.init()
    d = Draw(panel); t = Text(d)
    d.clear(rgb(0, 0, 0))
    t.text(10, 10, "你好 Orange Pi", size=32, color=rgb(0,255,0), bg=rgb(0,0,0))
    panel.backlight(80)
"""
from .core import Core
from .panel import Panel
from .draw import Draw, rgb
from .text import Text
from .touch import GT911

__all__ = ["Core", "Panel", "Draw", "Text", "GT911", "rgb"]
