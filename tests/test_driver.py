import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from lt758x import Core, Panel, Draw, GT911, rgb
from lt758x import config as C

class FakeSPI:
    def __init__(self):
        self.max_speed_hz = C.SPI_SPEED_REG
        self.packets = []
        self.fail = False
    def writebytes2(self, data):
        if self.fail:
            raise OSError("injected")
        assert self.max_speed_hz == C.SPI_SPEED_BURST
        self.packets.append(bytes(data))
    def xfer2(self, data):
        assert self.max_speed_hz == C.SPI_SPEED_REG
        return [0, 0x40]

class Capture:
    def __init__(self):
        self.blocks = []
        self.regs = {}
    def write_reg(self, r, v): self.regs[r] = v
    def cmd(self, r): pass
    def burst(self, data): self.blocks.append(bytes(data))

class DriverTests(unittest.TestCase):
    def test_spi_chunks_and_failure_cleanup(self):
        c = object.__new__(Core)
        c.spi = FakeSPI()
        c.chunk_size = 4095
        payload = bytes(range(255)) * 40
        c.burst(payload)
        self.assertTrue(all(p[0] == 0x80 and len(p) <= 4096 and (len(p)-1)%3 == 0 for p in c.spi.packets))
        self.assertEqual(b"".join(p[1:] for p in c.spi.packets), payload)
        c.spi.fail = True
        with self.assertRaises(OSError): c.burst(b"abc")
        self.assertEqual(c.spi.max_speed_hz, C.SPI_SPEED_REG)

    def test_multiband_image_and_flush(self):
        for image in (False, True):
            c = Capture(); d = Draw(Panel(c))
            if image: d.image(Image.new("RGB", (800,100), (255,0,0)), w=800,h=100)
            else: d.flush_area(0,0,800,100,bytes([255,0,0])*800*100)
            self.assertGreater(len(c.blocks),1)
            self.assertEqual(b"".join(c.blocks),rgb(255,0,0)*800*100)

    def test_clipped_source_stride(self):
        c = Capture(); d = Draw(Panel(c))
        pixels = bytes([1,0,0, 2,0,0, 3,0,0, 4,0,0, 5,0,0, 6,0,0])
        d.flush_area(-1,-1,3,2,pixels)
        self.assertEqual(b"".join(c.blocks),rgb(5,0,0)+rgb(6,0,0))
        self.assertEqual(c.regs[0x56],0)
        self.assertEqual(c.regs[0x58],0)
        c.blocks.clear(); d.fill_rect(-6,-1,13,3,rgb(1,2,3))
        self.assertEqual(b"".join(c.blocks),rgb(1,2,3)*14)
        with self.assertRaises(ValueError): d.flush_area(0,0,2,2,b"abc")

    def test_five_contacts_and_release(self):
        t = object.__new__(GT911); t.x_max=1024; t.y_max=600
        calls=[]
        def read(reg,n):
            calls.append((reg,n))
            return bytes([0x85]) if reg==0x814e else bytes([0,100,0,200,0,10,0,0])*5
        t._read_reg=read; t._write_reg=lambda *args: calls.append(args)
        self.assertEqual(t.read(),[(78,160)]*5)
        self.assertIn((0x814f,40),calls)
        self.assertEqual(calls[-1],(0x814e,[0]))
        t._read_reg=lambda reg,n: bytes([0x80])
        self.assertEqual(t.read(),[])
        with patch.object(C,"TOUCH_SWAP_XY",True):
            self.assertEqual(t._transform(512,300),(400,240))

    def test_combined_i2c_read(self):
        t=object.__new__(GT911); t.addr=0x14
        class Bus:
            def i2c_rdwr(self,*msgs):
                self.msgs=msgs
                for i in range(msgs[-1].len): msgs[-1].buf[i]=bytes([i])
        t.i2c=Bus()
        self.assertEqual(t._read_reg(0x814f,40),bytes(range(40)))
        a,b=t.i2c.msgs
        self.assertEqual(bytes(a),b"\x81\x4f")
        self.assertEqual(b.flags & 1,1)

    def test_invalid_touch_range_falls_back(self):
        with patch("lt758x.touch.SMBus") as bus, patch.object(GT911,"hw_reset"), patch.object(GT911,"_read_reg",side_effect=[b"911\x00"] + [bytes([0x82,0x20,3,0xc1,0xff])]*6):
            with self.assertWarns(RuntimeWarning): t=GT911()
            self.assertEqual((t.x_max,t.y_max),(C.TOUCH_X_MAX,C.TOUCH_Y_MAX))
            self.assertIn("fallback",t.info()["range_source"])
            t.close()

    def test_touch_range_recovers_after_bad_read(self):
        good=bytes([0x82,0x20,3,0xe0,1])
        bad=bytes([0x82,0x20,3,0xc1,0xff])
        with patch("lt758x.touch.SMBus"), patch.object(GT911,"hw_reset"), patch("lt758x.touch.time.sleep"), patch.object(GT911,"_read_reg",side_effect=[b"911\x00",bad,good,good]):
            t=GT911()
            self.assertEqual(t.info()["range"],(800,480))
            self.assertEqual(t._transform(400,240),(400,240))
            self.assertEqual(t._transform(799,479),(799,479))
            t.close()

    def test_display_and_canvas_same_address(self):
        c=Capture(); Panel(c).window_init()
        self.assertEqual([c.regs[0x20+i] for i in range(4)],[c.regs[0x50+i] for i in range(4)])

if __name__ == "__main__": unittest.main()
