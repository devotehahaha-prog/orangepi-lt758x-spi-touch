#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LT758x 驱动框架演示: 自检画面 + 实时触摸坐标
运行: python3 main.py
"""
import time
from lt758x import Panel, Draw, Text, GT911, rgb

WHITE = rgb(255, 255, 255)
BLACK = rgb(0, 0, 0)
RED = rgb(220, 40, 40)
GREEN = rgb(40, 180, 60)
BLUE = rgb(50, 90, 220)
YELLOW = rgb(240, 200, 40)
GRAY = rgb(40, 40, 46)


def self_test(d, t):
    d.clear(rgb(18, 22, 30))
    d.rect(0, 0, d.w, 70, BLUE, 3)
    t.text(20, 14, "Orange Pi 5 Pro + LT758x", size=32, color=WHITE, bg=rgb(50, 90, 220))
    t.text(20, 80, "LT758x 驱动框架自检画面", size=28, color=rgb(120, 220, 120), bg=rgb(18, 22, 30))
    # 色块
    colors = [RED, GREEN, BLUE, YELLOW]
    for i, c in enumerate(colors):
        d.fill_rect(20 + i * 120, 130, 100, 100, c)
    t.text(20, 245, "填充 / 描框 / 文字 / 图片 API 就绪", size=22, color=WHITE, bg=rgb(18, 22, 30))
    d.rect(20, 280, 760, 90, WHITE, 2)
    t.text(32, 292, "触摸屏幕此区域查看坐标", size=26, color=rgb(255, 200, 60), bg=rgb(18, 22, 30))
    t.text(32, 330, "Ctrl+C 退出", size=20, color=rgb(150, 150, 160), bg=rgb(18, 22, 30))


def main():
    panel = Panel()
    touch = None
    try:
        print("初始化面板...")
        panel.init()
        panel.backlight(85)
        d = Draw(panel)
        t = Text(d)
        self_test(d, t)
    
        try:
            touch = GT911()
            print("触摸芯片:", touch.info())
        except OSError as e:
            touch = None
            print("触摸初始化失败:", e)
    
        while True:
            if touch is not None:
                pts = touch.read()
                if pts:
                    for (x, y) in pts:
                        d.fill_rect(x - 6, y - 1, 13, 3, rgb(255, 120, 40))
                        d.fill_rect(x - 1, y - 6, 3, 13, rgb(255, 120, 40))
                    info = "  ".join(f"({x},{y})" for x, y in pts)
                    d.fill_rect(24, 385, 750, 40, GRAY)
                    t.text(28, 392, "触摸: " + info, size=24,
                           color=rgb(255, 120, 40), bg=rgb(40, 40, 46))
            time.sleep(0.03)
    finally:
        if touch is not None:
            touch.close()
        panel.core.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n退出")
