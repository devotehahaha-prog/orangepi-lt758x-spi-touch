#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GT911 电容触摸读取 (I2C, 汇顶 GT 系列)
用法:
    t = GT911()
    pts = t.read()      # 返回 [(x, y), ...], 无触点返回 []
"""
import time
import warnings
from smbus2 import SMBus, i2c_msg
from .panel import _gpio, _gpio_mode
from . import config as C


class GT911:
    def __init__(self, bus=C.I2C_BUS, addr=C.TOUCH_ADDR, reset=True):
        if addr not in (0x14, 0x5D):
            raise ValueError("GT911 address must be 0x14 or 0x5D")
        self.addr = addr
        self.i2c = SMBus(bus)
        try:
            if reset:
                self.hw_reset()
            self._product = self._read_product_id()
            # 复位后配置读取可能短暂异常，要求连续两次合法量程一致。
            previous = None
            confirmed = None
            for attempt in range(6):
                raw = self._read_reg(0x8047, 5)
                current = (raw[1] | raw[2] << 8, raw[3] | raw[4] << 8)
                if all(1 <= v <= 4096 for v in current):
                    if current == previous:
                        confirmed = current
                        break
                    previous = current
                else:
                    previous = None
                time.sleep(0.05)
            if confirmed is None:
                self.x_max, self.y_max = C.TOUCH_X_MAX, C.TOUCH_Y_MAX
                self.range_source = "config fallback"
                warnings.warn("GT911 range unstable; using configured range", RuntimeWarning)
            else:
                self.x_max, self.y_max = confirmed
                self.range_source = "controller"
            if self.x_max <= 0 or self.y_max <= 0:
                raise ValueError("touch range must be positive")
        except BaseException:
            self.i2c.close()
            raise

    def hw_reset(self):
        _gpio_mode(C.TOUCH_RST_WPI, "out")
        _gpio(C.TOUCH_RST_WPI, 0)
        try:
            _gpio_mode(C.TOUCH_INT_WPI, "out")
            _gpio(C.TOUCH_INT_WPI, int(self.addr == 0x14))
            time.sleep(0.02)
            _gpio(C.TOUCH_RST_WPI, 1)
            time.sleep(0.01)
            _gpio(C.TOUCH_INT_WPI, 0)
            time.sleep(0.05)
        finally:
            _gpio_mode(C.TOUCH_INT_WPI, "in")
        time.sleep(0.05)

    def _write_reg(self, reg16, data):
        self.i2c.i2c_rdwr(i2c_msg.write(self.addr, [reg16 >> 8, reg16 & 0xFF] + list(data)))

    def _read_reg(self, reg16, length):
        address = i2c_msg.write(self.addr, [reg16 >> 8, reg16 & 0xFF])
        result = i2c_msg.read(self.addr, length)
        self.i2c.i2c_rdwr(address, result)
        return bytes(result)

    def _read_product_id(self):
        product = self._read_reg(0x8140, 4).rstrip(b"\x00")
        if product != b"911":
            raise OSError("Unexpected GT911 product ID: %r" % product)
        return product.decode("ascii")

    def read(self):
        """读全部触点, 返回 [(x, y), ...](已转换为屏幕坐标)"""
        pts = []
        status = self._read_reg(0x814E, 1)[0]
        if status & 0x80:                            # 有新数据
            n = status & 0x0F
            if 0 < n <= 5:
                raw = self._read_reg(0x814F, n * 8)
                for i in range(n):
                    b = raw[i * 8:(i + 1) * 8]
                    x = b[1] | (b[2] << 8)
                    y = b[3] | (b[4] << 8)
                    x, y = self._transform(x, y)
                    pts.append((x, y))
            self._write_reg(0x814E, [0x00])          # 清除标志
        return pts

    def _transform(self, x, y):
        xmax, ymax = self.x_max, self.y_max
        if C.TOUCH_SWAP_XY:
            x, y = y, x
            xmax, ymax = ymax, xmax
        x = x * C.LCD_W // xmax
        y = y * C.LCD_H // ymax
        if C.TOUCH_MIRROR_X:
            x = C.LCD_W - 1 - x
        if C.TOUCH_MIRROR_Y:
            y = C.LCD_H - 1 - y
        return (max(0, min(C.LCD_W - 1, x)), max(0, min(C.LCD_H - 1, y)))

    def info(self):
        return {"product_id": self._product, "addr": hex(self.addr),
                "range": (self.x_max, self.y_max), "range_source": self.range_source}

    def close(self):
        self.i2c.close()
