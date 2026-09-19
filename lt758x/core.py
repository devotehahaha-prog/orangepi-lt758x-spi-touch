#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LT758x SPI 传输层
协议(锐显M-3例程/乐升LT758x一致):
  写寄存器地址: CS低 -> 0x00 + reg
  写数据:       CS低 -> 0x80 + data(可连续突发, 0x80前缀一次)
  读寄存器:     先写地址, CS低 -> 0xC0 + 读一字节
  读状态STSR:   CS低 -> 0x40 + 读一字节
"""
from pathlib import Path
import spidev
from . import config as C


class Core:
    def __init__(self, bus=C.SPI_BUS, cs=C.SPI_CS):
        bufsiz = int(Path("/sys/module/spidev/parameters/bufsiz").read_text())
        self.chunk_size = (min(bufsiz, 4096) - 1) // 3 * 3
        if self.chunk_size < 3:
            raise ValueError("SPI buffer too small for a pixel")
        self.spi = spidev.SpiDev()
        self.spi.open(bus, cs)
        self.spi.mode = 0
        self.spi.max_speed_hz = C.SPI_SPEED_REG

    def close(self):
        self.spi.close()

    # ---- 速度切换 ----
    def speed(self, hz):
        self.spi.max_speed_hz = hz

    def reg_speed(self):
        self.speed(C.SPI_SPEED_REG)

    def burst_speed(self):
        self.speed(C.SPI_SPEED_BURST)

    # ---- 基础原语 ----
    def cmd(self, reg):
        self.reg_speed()
        self.spi.xfer2([0x00, reg & 0xFF])

    def write_data(self, byte):
        self.reg_speed()
        self.spi.xfer2([0x80, byte & 0xFF])

    def read_data(self):
        self.reg_speed()
        return self.spi.xfer2([0xC0, 0x00])[1]

    def status(self):
        """读 STSR 状态寄存器"""
        self.reg_speed()
        return self.spi.xfer2([0x40, 0x00])[1]

    # ---- 寄存器 ----
    def write_reg(self, reg, val):
        self.cmd(reg)
        self.write_data(val)

    def read_reg(self, reg):
        self.cmd(reg)
        return self.read_data()

    def modify_reg(self, reg, sets=0, clrs=0):
        """读-改-写: 置位 sets, 清位 clrs"""
        v = self.read_reg(reg)
        v = (v | sets) & (~clrs & 0xFF)
        self.write_reg(reg, v)
        return v

    # ---- 显存突发写 ----
    def burst(self, payload):
        """每个独立 SPI 事务包含前缀，分块保持完整的24位像素。"""
        if len(payload) % 3:
            raise ValueError("24bpp payload must contain complete pixels")
        try:
            for start in range(0, len(payload), self.chunk_size):
                self.burst_speed()
                self.spi.writebytes2(b"\x80" + bytes(payload[start:start + self.chunk_size]))
                self.reg_speed()
                self.wait_fifo_empty()
        finally:
            self.reg_speed()

    # ---- STSR 位轮询 ----
    def wait_sdram_ready(self, timeout=2.0):
        """bit2: SDRAM ready"""
        import time
        t0 = time.monotonic()
        while (self.status() & 0x04) == 0:
            if time.monotonic() - t0 > timeout:
                raise TimeoutError("SDRAM not ready")
            time.sleep(0.001)

    def wait_fifo_empty(self, timeout=0.1):
        """bit6: 显存写 FIFO 空(写完标志)"""
        import time
        t0 = time.monotonic()
        while (self.status() & 0x40) == 0:
            if time.monotonic() - t0 > timeout:
                raise TimeoutError("write FIFO not empty")
            time.sleep(0.0005)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
