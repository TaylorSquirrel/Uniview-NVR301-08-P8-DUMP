import os
import socket

DEST = os.path.expanduser("~/nvr-backup/rootfs.fs")
ADDR = ("0.0.0.0", 6969)
BLOCK = 512

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(ADDR)
s.settimeout(5)

print("Waiting for NVR upload on UDP port 6969...")
print("Destination:", DEST, flush=True)

while True:
    try:
        packet, peer = s.recvfrom(2048)
    except socket.timeout:
        print("Still waiting...", flush=True)
        continue

    if len(packet) < 4 or packet[:2] != b"\x00\x02":
        continue

    fields = packet[2:].split(b"\0")
    if len(fields) < 2 or fields[0] != b"rootfs.fs":
        s.sendto(b"\x00\x05\x00\x02Unsupported filename", peer)
        continue

    transfer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    transfer.settimeout(5)
    expected = 1
    last_ack = b"\x00\x04\x00\x00"
    size = 0

    try:
        with open(DEST, "wb") as f:
            transfer.sendto(last_ack, peer)

            while True:
                try:
                    data, sender = transfer.recvfrom(2048)
                except socket.timeout:
                    transfer.sendto(last_ack, peer)
                    continue

                if sender != peer or len(data) < 4:
                    continue

                opcode = int.from_bytes(data[:2], "big")
                block = int.from_bytes(data[2:4], "big")

                if opcode == 5:
                    raise RuntimeError("TFTP client reported an error")
                if opcode != 3:
                    continue

                if block == expected:
                    payload = data[4:]
                    f.write(payload)
                    size += len(payload)
                    last_ack = b"\x00\x04" + data[2:4]
                    transfer.sendto(last_ack, peer)
                    expected = (expected + 1) & 0xffff

                    if len(payload) < BLOCK:
                        break
                elif block == ((expected - 1) & 0xffff):
                    transfer.sendto(last_ack, peer)

        print("Transfer complete:", size, "bytes", flush=True)
    except Exception as e:
        print("Transfer failed:", e, flush=True)
        try:
            os.remove(DEST)
        except OSError:
            pass
    finally:
        transfer.close()
        s.close()
        break
