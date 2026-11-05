#!/usr/bin/env python3
# Minimal TFTP server (RFC 1350 + blksize option). Reads are served from the root,
# writes go only to <root>/upload/ and never overwrite.
# usage: tftpd.py <bind_ip> <root_dir> [port]
import os, sys, socket, struct, threading

BIND, ROOT = sys.argv[1], os.path.abspath(sys.argv[2])
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 69


def serve(peer, fname, opts):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((BIND, 0))
    s.settimeout(2)
    path = os.path.abspath(os.path.join(ROOT, fname.lstrip('/')))
    if not path.startswith(ROOT + os.sep) or not os.path.isfile(path):
        s.sendto(struct.pack('!HH', 5, 1) + b'File not found\0', peer)
        print(f'{peer[0]} RRQ {fname}: not found', flush=True)
        return
    data = open(path, 'rb').read()
    bs = 512

    def xfer(pkt, want):
        for _ in range(8):
            s.sendto(pkt, peer)
            try:
                while True:
                    r, a = s.recvfrom(1024)
                    if a != peer:
                        continue
                    op, n = struct.unpack('!HH', r[:4])
                    if op == 4 and n == want:
                        return True
                    if op == 5:
                        return False
            except socket.timeout:
                continue
        return False

    if 'blksize' in opts:
        bs = max(8, min(int(opts['blksize']), 1468))
        oack = struct.pack('!H', 6) + b'blksize\0' + str(bs).encode() + b'\0'
        if not xfer(oack, 0):
            return
    blk = 1
    off = 0
    while True:
        chunk = data[off:off + bs]
        if not xfer(struct.pack('!HH', 3, blk & 0xffff) + chunk, blk & 0xffff):
            print(f'{peer[0]} {fname}: transfer aborted', flush=True)
            return
        off += bs
        blk += 1
        if len(chunk) < bs:
            break
    print(f'{peer[0]} {fname}: {len(data)} bytes sent', flush=True)


def receive(peer, fname, opts):
    """WRQ: store the file under <root>/upload/, never overwrite."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((BIND, 0))
    s.settimeout(10)
    updir = os.path.join(ROOT, 'upload')
    os.makedirs(updir, exist_ok=True)
    path = os.path.join(updir, os.path.basename(fname))
    if os.path.exists(path):
        s.sendto(struct.pack('!HH', 5, 6) + b'File exists\0', peer)
        print(f'{peer[0]} WRQ {fname}: already exists, refused', flush=True)
        return
    bs = 512
    if 'blksize' in opts:
        bs = max(8, min(int(opts['blksize']), 1468))
        s.sendto(struct.pack('!H', 6) + b'blksize\0' + str(bs).encode() + b'\0', peer)
    else:
        s.sendto(struct.pack('!HH', 4, 0), peer)
    want, total = 1, 0
    with open(path + '.part', 'wb') as f:
        while True:
            try:
                pkt, a = s.recvfrom(bs + 4)
            except socket.timeout:
                print(f'{peer[0]} {fname}: timeout, aborted', flush=True)
                return
            if a != peer:
                continue
            op, n = struct.unpack('!HH', pkt[:4])
            if op != 3:
                return
            if n == want & 0xffff:
                f.write(pkt[4:])
                total += len(pkt) - 4
                want += 1
            s.sendto(struct.pack('!HH', 4, n), peer)
            if n == (want - 1) & 0xffff and len(pkt) - 4 < bs:
                break
    os.rename(path + '.part', path)
    print(f'{peer[0]} {fname}: {total} bytes received', flush=True)


m = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
m.bind((BIND, PORT))
print(f'TFTP {BIND}:{PORT} root={ROOT}', flush=True)
while True:
    pkt, peer = m.recvfrom(1024)
    op = struct.unpack('!H', pkt[:2])[0]
    if op not in (1, 2):
        continue
    parts = pkt[2:].split(b'\0')
    fname = parts[0].decode(errors='replace')
    opts = {parts[i].decode().lower(): parts[i + 1].decode()
            for i in range(2, len(parts) - 1, 2) if parts[i]}
    print(f'{peer[0]} {"RRQ" if op == 1 else "WRQ"} {fname} {opts}', flush=True)
    threading.Thread(target=serve if op == 1 else receive,
                     args=(peer, fname, opts), daemon=True).start()
