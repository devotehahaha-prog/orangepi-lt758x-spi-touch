# LT758x SPI 触控屏驱动框架 (锐显 M70-3 @ Orange Pi 5 Pro)

7 寸 800×480 SPI 电容触摸屏(LT758x 主控 + GT911 触摸)的用户态驱动框架。
无需编写专用内核驱动或安装内核头文件（依赖系统现有 spidev/I2C 驱动）, 全部通过 `/dev/spidev0.0` + `/dev/i2c-1` + wiringOP GPIO 实现。

## 环境准备

实测环境：Orange Pi 5 Pro、Ubuntu 22.04、Python 3.10。需提前启用下方接线章节的 SPI/I2C overlay 并重启，确认 `/dev/spidev0.0` 与 `/dev/i2c-1` 存在。

需安装适配 Orange Pi 5 Pro 的 wiringOP，确认 `gpio readall` 可用；中文演示还需字体，例如 `sudo apt install fonts-noto-cjk`。`setup.sh` 安装 Python 依赖并将 SPI/I2C 设备权限设为0666，适用于本地开发板演示；它不会安装 wiringOP 或修改设备树。

## 快速开始

```bash
git clone https://github.com/devotehahaha-prog/orangepi-lt758x-spi-touch.git
cd orangepi-lt758x-spi-touch
bash setup.sh          # 装依赖 + 配设备权限(只需一次)
python3 main.py        # 自检画面 + 触摸坐标演示
```

## 架构

```
main.py                  应用/演示
   │
lt758x/
   ├── panel.py          面板: 复位→PLL→SDRAM→时序→窗口→背光   (init 一键完成)
   ├── draw.py           绘图: clear/fill/线/框/图片/flush_area
   ├── text.py           文字: 中英文抗锯齿渲染(Pillow)
   ├── touch.py          触摸: GT911 I2C 读点
   ├── core.py           SPI 传输层: 0x00/0x80/0xC0/0x40 协议 + 突发写
   └── config.py         全部硬件参数(改引脚/时序/色深只动这里)
```

数据通路: `SPI(32MHz突发) → LT758x 显存(芯片自刷新) → RGB → 屏`
静态画面由控制器显存维持；更新画面和读取显示状态时仍会产生 SPI 流量。

## API 速查

```python
from lt758x import Panel, Draw, Text, GT911, rgb

panel = Panel()
panel.init()                  # 一键初始化(也可 color_bar=True 看彩条)
panel.backlight(85)           # 背光 0~100
panel.display_on()/off()

d = Draw(panel)
d.clear(rgb(0,0,0))           # 清屏
d.fill_rect(x,y,w,h,rgb(...)) # 填充
d.rect(x,y,w,h,rgb(...),2)    # 描框
d.hline/vline/put_pixel
d.image_file("x.png", 0,0)    # 贴图(自动缩放, 支持PNG/JPG/BMP)
d.flush_area(x,y,w,h,rgb888)  # 整块RGB888数据直推(给LVGL等上层引擎)

t = Text(d)
t.text(10,10,"中文English", size=28, color=rgb(255,255,0), bg=rgb(0,0,0))
t.measure(s, size)            # 测量文字尺寸

ts = GT911()
pts = ts.read()               # [(x,y),...] 或 []
```

## 接线 (模块 CON2 15针 → 香橙派40pin)

| 模块 | 信号 | 香橙派 | 脚号 |
|---|---|---|---|
| 1 GND | VSS | GND | 6 |
| 2 VDD | 5V | 5V | 2 |
| 3 CS | SCS | SPI0_CS0 | 24 |
| 4 SDO | MISO | SPI0_MISO | 21 |
| 5 SDI | MOSI | SPI0_MOSI | 19 |
| 6 SCL | SCK | SPI0_CLK | 23 |
| 7 RST | 复位 | GPIO1_B0 | 22 |
| 11 T-SDI | 触摸SDA | I2C1_SDA | 3 |
| 12 T-CLK | 触摸SCL | I2C1_SCL | 5 |
| 13 T-CS | 触摸RST | GPIO1_B6 | 15 |
| 14 T-INT | 触摸中断 | GPIO4_B3 | 13 |

模块跳线: SPI-S="−", PSM2="+", PMS0="+" (4线SPI)。
/boot/orangepiEnv.txt: `overlays=... spi0-m2-cs0-spidev i2c1-m4`

## 已验证结论

- SPI mode0, 寄存器配置 5MHz / 显存突发配置 32MHz
- STSR 空闲态 0x54: bit2=SDRAM ready, bit6=写FIFO空
- 触摸 GT911 @ I2C1 地址 0x14 (INT=高复位)
- 模块晶振 6MHz: PCLK=33M(60Hz) MCLK=180M CCLK=150M

## 后续扩展路线

1. 触摸校准: 实测后改 config.py 的 TOUCH_* 参数
2. LVGL8 对接: 写 lv_port_disp, flush_cb 调 `d.flush_area()`
3. 开机自启: systemd unit 运行主程序
4. C 语言移植: core.py 的协议就是全部, spidev ioctl 直接对应

## 修复与验证（2026-09-19）

- SPI 按内核缓冲上限分包，每包包含 0x80 前缀，保持完整24位像素；寄存器和状态读取使用5MHz，每包写完等待FIFO。
- 图片/flush_area 修复跨块变黑，支持边界裁剪并校验RGB888长度。
- 文字统一走刷新接口；rgb() 返回的 bytes 使用显存顺序，普通 tuple 使用RGB顺序。
- GT911 使用16位地址组合I2C读事务，触点记录从0x814F读取，支持40字节五指数据。
- 默认执行触摸RST/INT地址选择时序。GT911(reset=False) 可跳过复位。
- 量程只接受1~4096；异常值回退到config中的量程并发出警告，info()报告来源。回退参数仍需实际触摸校准。
- 回归测试：`python3 -B -m unittest discover -s tests -v`。
- 单线程使用；面板扫描频率与SPI应用刷新帧率不同。

## 实机验收结果（2026-09-19）

用户已确认演示运行成功，显示与触摸交互可用。

- 板上显示写入结束后状态寄存器为 `0x54`。
- GT911 产品标识为 `911`，I2C 地址为 `0x14`，最终读取量程为 `800×480`。
- 实际读取到触点坐标；8项自动化回归测试全部通过。
- 运行 `python3 main.py` 后，触摸位置显示橙色小十字，底部更新坐标；滑动会留下轨迹，松开后保留轨迹与最后一次坐标。
- 左上角为 `(0,0)`，右下角为 `(799,479)`。演示需保持运行，按 `Ctrl+C` 退出。

启动命令：

```bash
cd ~/orangepi-lt758x-spi-touch
python3 main.py
```

本次验收确认基本显示与触摸交互，不代表已完成五指实机测试、长时间稳定性测试或LVGL集成。

### 触摸比例偏差修复

实机GT911配置量程为800×480。初始化读取改为重复确认两次一致的合法值；备用量程由1024×600修正为800×480，避免异常读取后将触点向左上缩放。修改后需重启演示进程。


坐标比例修复后已通过自动化回归，运行日志确认采用800×480量程；修复后的四角触摸精度仍待人工复核。

## 发布范围

本仓库包含 Python 用户态驱动、演示与测试。初始化流程参考锐显 M-3 STM32 例程；厂商例程、手册和下载工具未随仓库分发。
