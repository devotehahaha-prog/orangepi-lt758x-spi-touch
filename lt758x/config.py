#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""硬件配置 —— 全部引脚/时序/色深参数的唯一来源 (M70-3 @ Orange Pi 5 Pro)"""

# ---- SPI ----
SPI_BUS, SPI_CS = 0, 0
SPI_SPEED_REG = 5_000_000        # 寄存器读写频率
SPI_SPEED_BURST = 32_000_000     # 显存批量写入频率(上限50MHz)

# ---- GPIO (wiringOP wPi 编号, 用 gpio readall 查看) ----
RST_WPI = "13"                   # 物理22脚 GPIO1_B0 -> 模块 RST
TOUCH_RST_WPI = "8"              # 物理15脚 GPIO1_B6 -> 触摸 RST (T-CS)
TOUCH_INT_WPI = "7"              # 物理13脚 GPIO4_B3 -> 触摸 INT

# ---- 面板 (锐显 M70-3, 800x480@60Hz, 官方例程时序) ----
LCD_W, LCD_H = 800, 480
HBPD, HFPD, HSPW = 46, 210, 20   # 水平后廊/前廊/同步宽
VBPD, VFPD, VSPW = 23, 22, 3     # 垂直后廊/前廊/同步宽
MCLK_M, CCLK_M = 30, 25          # PLL M 值(模块晶振6MHz: PCLK=33M,MCLK=180M,CCLK=150M)
LAYER0 = 2181120                 # 图层0显存地址(字库区之后, 官方例程值)

# ---- 色彩 ----
BPP = 24                         # 画布色深
PIXEL_BYTES = 3                  # 每像素字节数
# 显存字节序: 官方例程 24bpp 模式按 (低,中,高)字节写出 = B,G,R
COLOR_ORDER = ("B", "G", "R")

# ---- 触摸 GT911 (汇顶电容屏, I2C) ----
I2C_BUS = 1
TOUCH_ADDR = 0x14                # INT=高复位时为0x14, 低为0x5D
TOUCH_SWAP_XY = False            # 屏幕旋转时改这里
TOUCH_MIRROR_X = False
TOUCH_MIRROR_Y = False
TOUCH_X_MAX = 800                # 实机配置确认的原始量程；读取异常时备用
TOUCH_Y_MAX = 480

# ---- 字体(按顺序取第一个存在的) ----
FONT_CN = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]
FONT_ASCII = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
