![OpenWrt on ZTE MF282](assets/banner.webp)

# OpenWrt on ZTE MF282 ("3HuiTube")

Installation guide for official OpenWrt 25.12.5 on the ZTE MF282 LTE router, sold by the
Austrian operator Drei as **3HuiTube**. OpenWrt is installed from the stock root shell,
without touching U-Boot.

The firmware images are unmodified official OpenWrt builds. They are attached to the
[Releases](../../releases/latest) page for convenience and are also available from
[downloads.openwrt.org](https://downloads.openwrt.org/releases/25.12.5/targets/ath79/nand/).

> **Unofficial guide. You do this at your own risk.** No stock firmware is available for
> download: take the full flash backup described below before writing anything.

> **Check the label first.** A unit labelled **"DreiTube"** is the MF282**+** (IPQ4019 +
> Marvell modem), a different device. This guide and these images do not apply to it.

## Hardware

| Component | Details |
|---|---|
| SoC | Qualcomm Atheros QCA9563, 775 MHz |
| RAM | 128 MiB |
| Flash | 8 MiB SPI-NOR (U-Boot, U-Boot env) + 128 MiB SPI-NAND |
| Ethernet | 1x Gigabit LAN |
| Wi-Fi | QCA9560 2.4 GHz 802.11n + QCA9880 5 GHz 802.11ac |
| LTE | ZTE ZM8630 / MF270 module, Cat 4, Qualcomm based, QMI |
| Stock firmware | `BD_H3GATZM8630V1.0.0B08`, U-Boot 1.1.4 |
| OpenWrt target | `ath79/nand`, profile `zte_mf282` |

The Wi-Fi calibration data has the `US` country code burned in. OpenWrt applies the stricter
of that and your configured country, so 5 GHz power stays at the US limit (30 dBm).

### Stock flash layout (SPI-NAND)

| Name | Size | Offset | Notes |
|---|---|---|---|
| `fota-flag` | 1280 KiB | `0x0000000` | |
| `caldata` | 1280 KiB | `0x0140000` | Wi-Fi calibration, unique per unit |
| `mac` | 1280 KiB | `0x0280000` | MAC addresses, unique per unit |
| `cfg-param` | 6 MiB | `0x03c0000` | settings, unique per unit |
| `oops` | 1280 KiB | `0x09c0000` | |
| `web` | 8 MiB | `0x0b00000` | |
| `kernel` | 3 MiB | `0x1300000` | |
| `rootfs` | 31 MiB | `0x1600000` | |
| `data` | 25 MiB | `0x3500000` | |
| `fota` | 50 MiB | `0x4e00000` | |

The SPI-NOR holds `uboot` (512 KiB) and `uboot-env` (128 KiB).

## Opening the case and serial console

1. Remove the battery cover and the 4 screws underneath.
2. Open the back cover, then remove the 4 board screws and the 2 antenna screws.
3. The UART pads are under the antenna. The **square pad is 3.3 V: do not connect it.** The
   pads next to it are RX, TX and GND.

Use a **3.3 V TTL** USB-serial adapter, **115200 8N1**. Connect GND, RX and TX only. The stock
firmware gives a **passwordless root shell** on the console.

Pinout source: the [OpenWrt forum thread](https://forum.openwrt.org/t/adding-openwrt-support-for-zte-mf282-aka-3-huitube/157177).
Disassembly: [aboehler.at](https://www.aboehler.at/doku/doku.php/projects:zte_mf28x).

## Tools

| File | Use |
|---|---|
| [`tools/tftpd.py`](tools/tftpd.py) | minimal TFTP server. Serves files from a directory, accepts uploads only into `<dir>/upload/`, never overwrites. `python3 tools/tftpd.py <bind_ip> <dir> [port]` |
| [`tools/mkenv.py`](tools/mkenv.py) | builds the U-Boot environment image used in step 2 |

## 1. Back up the flash

Do this before anything else. `caldata`, `mac` and `cfg-param` are unique to your unit and
there is no vendor firmware to download.

The stock BusyBox has `nanddump` and a `tftp` client but no `dd`. Start the TFTP server on
the PC on port 6969, then dump each partition to `/tmp` and upload it, one at a time:

```sh
# on the PC (192.168.0.100, stock LAN is 192.168.0.0/24)
python3 tools/tftpd.py 192.168.0.100 backup 6969

# on the router
cat /proc/mtd
# mtd0 (uboot) and mtd1 (uboot-env) are SPI-NOR:
cat /dev/mtd0 > /tmp/mtd0.bin
# mtd2 ... mtd11 are SPI-NAND:
nanddump -f /tmp/mtd3.bin /dev/mtd3
tftp -p -l /tmp/mtd3.bin -r mtd3.bin 192.168.0.100 6969
rm /tmp/mtd3.bin
```

Uploads land in `backup/upload/`. Read every partition twice and compare the hashes. All
partitions match except `cfg-param` and `fota`, which the stock system writes while it runs.
`oops` reports ECC errors when read, but both reads are identical.

## 2. Install from the stock root shell

U-Boot itself (`mtd0`) is never written. The OpenWrt initramfs goes into the unused `data`
partition, and U-Boot gets a one-shot boot command that loads it once and then restores the
stock boot command.

1. Build the environment image: `python3 tools/mkenv.py tftp/uboot-env.bin`. It contains the
   stock default variables plus this one-shot `bootcmd`:

   ```
   setenv bootcmd nboot 0x81000000 0 0x1300000; saveenv; nboot 0x81000000 0 0x3500000
   ```

   The environment is 64 KiB, with the CRC32 stored **big-endian**.
2. Copy `openwrt-25.12.5-ath79-nand-zte_mf282-initramfs-kernel.bin` to `tftp/openwrt.bin` and
   start the TFTP server on port 6969: `python3 tools/tftpd.py 192.168.0.100 tftp 6969`.
3. On the router (stock root shell):

   ```sh
   tftp -g -r openwrt.bin -l /tmp/openwrt.bin 192.168.0.100 6969
   tftp -g -r uboot-env.bin -l /tmp/env.bin 192.168.0.100 6969

   # data partition (NAND 0x3500000). mtd11 (fota) is mounted and mtd9 is the running root:
   # do not write those.
   flash_eraseall /dev/mtd10
   nandwrite -p /dev/mtd10 /tmp/openwrt.bin

   # U-Boot env on SPI-NOR
   flash_eraseall /dev/mtd1
   cat /tmp/env.bin > /dev/mtd1

   reboot
   ```

   Check the `mtd` numbers against `cat /proc/mtd` first. The old `flash_erase` in the stock
   BusyBox takes a block **count** as its last argument (0 erases nothing), so use
   `flash_eraseall`. Read each write back and compare its hash with the file on the PC
   before rebooting.
4. U-Boot restores the stock `bootcmd`, then boots OpenWrt from RAM. Give it an address on
   the stock subnet from the console:

   ```sh
   ip addr add 192.168.0.1/24 dev br-lan
   ```

5. Fetch the sysupgrade image (for example with `wget` from an HTTP server on the PC), check
   its SHA256, and flash it:

   ```sh
   sysupgrade -T /tmp/openwrt-25.12.5-ath79-nand-zte_mf282-squashfs-sysupgrade.bin
   sysupgrade -n /tmp/openwrt-25.12.5-ath79-nand-zte_mf282-squashfs-sysupgrade.bin
   ```

The first UBI attach prints many ECC errors from old data left on the NAND. That is expected:
OpenWrt reformats the area on first boot. The router then boots from flash with the UBIFS
overlay mounted, both radios and the modem detected.

## Default configuration after install

Standard OpenWrt defaults:

| Setting | Value |
|---|---|
| LAN | `192.168.1.1`, DHCP server |
| Login | `root`, no password. Set one first |
| Wi-Fi | disabled |
| LTE | not configured |

## LTE modem

In OpenWrt the modem shows up as `ttyUSB0` ... `ttyUSB2` and `cdc-wdm0` / `wwan0` (QMI).

## References

- OpenWrt commit [`590d1fd0e6`](https://github.com/openwrt/openwrt/commit/590d1fd0e636f627bbfeb988909ec36cc5450a3b) "ath79: add support for ZTE MF282"
- [OpenWrt forum thread](https://forum.openwrt.org/t/adding-openwrt-support-for-zte-mf282-aka-3-huitube/157177)
- [aboehler.at: ZTE MF28x](https://www.aboehler.at/doku/doku.php/projects:zte_mf28x)

## License

This guide is licensed under [CC BY 4.0](LICENSE). The scripts in [`tools/`](tools) are
licensed under the [MIT License](LICENSE-tools).

The firmware images on the Releases page are unmodified official OpenWrt 25.12.5 builds,
licensed under GPL-2.0. Source code:
[openwrt/openwrt @ v25.12.5](https://github.com/openwrt/openwrt/tree/v25.12.5).
