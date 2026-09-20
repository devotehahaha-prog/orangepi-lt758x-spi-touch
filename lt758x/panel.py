#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LT758x 面板控制: 复位/PLL/SDRAM/时序/窗口/背光/显示开关
初始化流程参考 LCD_800x480_Init, 已在板上验证通过
"""
import subprocess
import time
from . import config as C
from .core import Core


def _gpio(wpi, val):
    subprocess.run(["gpio", "write", str(wpi), str(val)], check=True)


def _gpio_mode(wpi, mode):
    subprocess.run(["gpio", "mode", str(wpi), mode], check=True)


class Panel:
    def __init__(self, core: Core = None):
        self.core = core or Core()
        self.w = C.LCD_W
        self.h = C.LCD_H

    # ---- 硬件复位 ----
    def hw_reset(self):
        _gpio_mode(C.RST_WPI, "out")
        _gpio(C.RST_WPI, 0)
        time.sleep(0.2)
        _gpio(C.RST_WPI, 1)
        time.sleep(0.2)

    # ---- PLL (寄存器值与官方例程一致, 模块晶振6MHz) ----
    def pll_init(self):
        c = self.core
        total = (C.HBPD + C.HFPD + C.HSPW + C.LCD_W) * \
                (C.VBPD + C.VFPD + C.VSPW + C.LCD_H) * 60
        t1 = total // 1000000
        pclk_m = t1 // 3 + (1 if t1 % 3 == 2 else 0)
        c.write_reg(0x05, (2 << 6) | (1 << 1))       # PCLK: OD=2, N=1
        c.write_reg(0x06, pclk_m & 0xFF)
        c.write_reg(0x07, (1 << 6) | (1 << 1))       # MCLK: OD=1, N=1
        c.write_reg(0x08, C.MCLK_M & 0xFF)
        c.write_reg(0x09, (1 << 6) | (1 << 1))       # CCLK: OD=1, N=1
        c.write_reg(0x0A, C.CCLK_M & 0xFF)
        c.write_reg(0x00, c.read_reg(0x00) | 0x80)   # PLL 启动
        t0 = time.monotonic()
        while (c.read_reg(0x00) & 0x80) == 0:
            if time.monotonic() - t0 > 1:
                raise TimeoutError("PLL lock timeout")
            time.sleep(0.0001)
        return C.MCLK_M * 6                          # MCLK = XI(6M)*M/N/OD

    # ---- 片内 SDRAM ----
    def sdram_init(self, mclk):
        c = self.core
        c.write_reg(0xE0, 0x29)
        c.write_reg(0xE1, 0x03)
        itv = (64000 * mclk) // 4096
        c.write_reg(0xE2, itv & 0xFF)
        c.write_reg(0xE3, itv >> 8)
        v = c.read_reg(0xE4)
        c.write_reg(0xE4, v | 0x04)
        c.write_reg(0xE0, 0x00)
        c.write_reg(0xE1, (8 << 4) | 7)
        c.write_reg(0xE2, (4 << 4) | 0)
        c.write_reg(0xE3, (2 << 4) | 6)
        c.write_reg(0xE4, v & 0xFB)
        c.write_reg(0xE4, c.read_reg(0xE4) | 0x01)   # 启动初始化
        c.wait_sdram_ready()
        time.sleep(0.1)

    # ---- 面板/时序配置 ----
    def panel_init(self):
        c = self.core
        c.modify_reg(0x01, clrs=0x01)                # 8位主机接口(SPI)
        c.modify_reg(0x02, clrs=0x06)                # 显存写入: 左->右, 上->下
        c.modify_reg(0x03, clrs=0x03)                # 显存选择: SDRAM
        c.modify_reg(0x01, clrs=0x18)                # RGB 24位输出
        c.modify_reg(0x5E, clrs=0x04)                # 画布块模式(XY寻址)
        c.modify_reg(0x5E, sets=0x02, clrs=0x01)     # 画布24bpp
        c.modify_reg(0x10, sets=0x08, clrs=0x04)     # 主视窗24bpp
        c.modify_reg(0x02, clrs=0xC0)                # 24bpp mode1
        c.modify_reg(0x10, clrs=0x01)                # Sync 模式
        c.modify_reg(0x12, sets=0x80)                # PCLK 下降沿
        c.modify_reg(0x12, clrs=0x08)                # 垂直扫描: 上->下
        c.modify_reg(0x12, clrs=0x07)                # PDATA 顺序 RGB
        c.modify_reg(0x13, clrs=0x80)                # HSYNC 低有效
        c.modify_reg(0x13, clrs=0x40)                # VSYNC 低有效
        c.modify_reg(0x13, clrs=0x20)                # DE 高有效

    def timing_init(self):
        c = self.core
        wreg = c.write_reg
        wreg(0x14, C.LCD_W // 8 - 1); wreg(0x15, C.LCD_W % 8)
        wreg(0x16, C.HBPD // 8 - 1);  wreg(0x17, C.HBPD % 8)
        wreg(0x18, C.HFPD // 8 - 1)
        wreg(0x19, C.HSPW // 8 - 1)
        wreg(0x1A, (C.LCD_H - 1) & 0xFF); wreg(0x1B, (C.LCD_H - 1) >> 8)
        wreg(0x1C, C.VBPD - 1);           wreg(0x1D, 0)
        wreg(0x1E, C.VFPD - 1)
        wreg(0x1F, C.VSPW - 1)

    def window_init(self):
        """主视窗/画布/工作窗口 = 全屏, 显示与绘制备指向 LAYER0"""
        c = self.core
        wreg = c.write_reg
        a = C.LAYER0
        # 主图起始地址 = LAYER0 (必须与画布一致, 否则显示与绘制错位!)
        wreg(0x20, a & 0xFF); wreg(0x21, (a >> 8) & 0xFF)
        wreg(0x22, (a >> 16) & 0xFF); wreg(0x23, (a >> 24) & 0xFF)
        wreg(0x24, C.LCD_W & 0xFF); wreg(0x25, C.LCD_W >> 8)
        for r in (0x26, 0x27, 0x28, 0x29):           # 主窗口XY = 0
            wreg(r, 0)
        a = C.LAYER0
        wreg(0x50, a & 0xFF); wreg(0x51, (a >> 8) & 0xFF)
        wreg(0x52, (a >> 16) & 0xFF); wreg(0x53, (a >> 24) & 0xFF)
        wreg(0x54, C.LCD_W & 0xFF); wreg(0x55, C.LCD_W >> 8)
        self.active_xy(0, 0)
        self.active_wh(C.LCD_W, C.LCD_H)
        self.goto_xy(0, 0)

    # ---- 一键初始化 ----
    def init(self, color_bar=False):
        self.hw_reset()
        mclk = self.pll_init()
        self.sdram_init(mclk)
        self.panel_init()
        self.timing_init()
        self.window_init()
        self.display_on()
        if color_bar:
            self.color_bar(True)

    # ---- 显示控制 ----
    def display_on(self):
        self.core.modify_reg(0x12, sets=0x40)

    def display_off(self):
        self.core.modify_reg(0x12, clrs=0x40)

    def color_bar(self, on):
        """彩条自检(不依赖显存内容)"""
        if on:
            self.core.modify_reg(0x12, sets=0x20)
        else:
            self.core.modify_reg(0x12, clrs=0x20)

    # ---- 背光 (LT758x PWM1, 模块 LED- 经 PWM 驱动) ----
    def backlight(self, level):
        """0~100, 0=熄灭"""
        c = self.core
        level = max(0, min(100, int(level)))
        period = 6000
        duty = level * 60
        c.write_reg(0x84, 1)                         # 预分频 1~256
        c.modify_reg(0x85, sets=0x08, clrs=0x04 | 0xC0)  # 选PWM1, 时钟/1
        c.write_reg(0x8E, period & 0xFF)             # 周期低
        c.write_reg(0x8F, period >> 8)               # 周期高
        c.write_reg(0x8C, duty & 0xFF)               # 占空低
        c.write_reg(0x8D, duty >> 8)                 # 占空高
        c.modify_reg(0x86, sets=0x10)                # 启动 PWM1

    # ---- 工作窗口辅助(绘图用) ----
    def active_xy(self, x, y):
        c = self.core
        c.write_reg(0x56, x & 0xFF); c.write_reg(0x57, x >> 8)
        c.write_reg(0x58, y & 0xFF); c.write_reg(0x59, y >> 8)

    def active_wh(self, w, h):
        c = self.core
        c.write_reg(0x5A, w & 0xFF); c.write_reg(0x5B, w >> 8)
        c.write_reg(0x5C, h & 0xFF); c.write_reg(0x5D, h >> 8)

    def goto_xy(self, x, y):
        c = self.core
        c.write_reg(0x5F, x & 0xFF); c.write_reg(0x60, x >> 8)
        c.write_reg(0x61, y & 0xFF); c.write_reg(0x62, y >> 8)
