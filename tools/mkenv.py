#!/usr/bin/env python3
# Build the 64 KiB U-Boot environment image for the ZTE MF282 (stock U-Boot 1.1.4).
# It holds the stock default variables plus a one-shot bootcmd: on the next boot U-Boot
# writes the stock bootcmd back, saves, and boots the OpenWrt initramfs from NAND 0x3500000.
# usage: mkenv.py [output]   (default: uboot-env.bin)
import struct, sys, zlib

ENV_SIZE = 0x10000

env_vars = [
    ("bootargs", "console=ttyS0,115200 root=31:9 rootfstype=cramfs init=/sbin/init "
                 "mtdparts=ath-nor0:512k(uboot),128k(uboot-env);ath-spi-nand:1280k(fota-flag),"
                 "1280k(caldata),1280k(mac),6m(cfg-param),1280k(oops),8m(web),3m(kernel),"
                 "31m(rootfs),25m(data),50m(fota)"),
    ("bootcmd", "setenv bootcmd nboot 0x81000000 0 0x1300000; saveenv; "
                "nboot 0x81000000 0 0x3500000"),
    ("bootdelay", "2"),
    ("baudrate", "115200"),
    ("ethaddr", "0x00:0xaa:0xbb:0xcc:0xdd:0xee"),
    ("ipaddr", "192.168.0.1"),
    ("serverip", "192.168.0.22"),
    ("dir", ""),
    ("lu", "tftp 0x80060000 ${dir}u-boot.bin&&erase_ext 0 $filesize&&write_ext $fileaddr 0 $filesize"),
    ("lf", "tftp 0x80060000 ${dir}zte-rootfs&&nand erase 0x1600000 0x1f00000&&nand write $fileaddr 0x1600000 $filesize"),
    ("lk", "tftp 0x80060000 ${dir}zte-kernel&&nand erase 0x1300000 0x300000&&nand write $fileaddr 0x1300000 $filesize"),
    ("lw", "tftp 0x80060000 ${dir}web.img&&nand erase 0xb00000 0x800000&&nand write $fileaddr 0xb00000 $filesize"),
    ("lrb", "tftp 0x80060000 ${dir}delta.mld&&nand erase 0x3500000 0x1900000&&nand write $fileaddr 0x3500000 $filesize"),
    ("lr", "tftp 0x80060000 ${dir}root_uImage&&nand erase 0xb00000 0x2a00000&&nand write $fileaddr 0xb00000 $filesize"),
]

body = b"".join(f"{k}={v}".encode() + b"\x00" for k, v in env_vars) + b"\x00"
if len(body) > ENV_SIZE - 4:
    sys.exit(f"environment too large: {len(body)} bytes")
body = body.ljust(ENV_SIZE - 4, b"\x00")
crc = zlib.crc32(body) & 0xFFFFFFFF
img = struct.pack(">I", crc) + body  # this U-Boot stores the CRC big-endian

out = sys.argv[1] if len(sys.argv) > 1 else "uboot-env.bin"
with open(out, "wb") as f:
    f.write(img)
print(f"{out}: {len(img)} bytes, CRC=0x{crc:08x}")
