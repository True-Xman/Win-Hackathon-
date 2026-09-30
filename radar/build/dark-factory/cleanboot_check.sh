#!/usr/bin/env bash
# Prove a service starts with ZERO outbound network (Dark Factory: "a service that doesn't start scores zero").
# Usage: cleanboot_check.sh "<start command>" <port> [health-path]     e.g. cleanboot_check.sh "node app/server.js" 8080 /
# Fresh network namespace (loopback only; raised via ioctl so no `ip` binary is needed), start service, curl localhost,
# and confirm an external connection FAILS. Exit 0 only if started AND isolated.
set -u
CMD="$1"; PORT="$2"; HPATH="${3:-/}"
export CMD PORT HPATH
unshare -rn python3 - <<'PY'
import os, socket, fcntl, struct, subprocess, time, sys, urllib.request
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
fl = struct.unpack('16sh', fcntl.ioctl(s, 0x8913, struct.pack('16sh', b'lo', 0)))[1]
fcntl.ioctl(s, 0x8914, struct.pack('16sh', b'lo', fl | 1))
p = subprocess.Popen(os.environ["CMD"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
url = f"http://127.0.0.1:{os.environ['PORT']}{os.environ['HPATH']}"
started = False
for _ in range(60):
    time.sleep(0.5)
    try:
        urllib.request.urlopen(url, timeout=1); started = True; break
    except urllib.error.HTTPError:
        started = True; break          # any HTTP answer = the service is up
    except Exception:
        pass
try:
    socket.create_connection(("1.1.1.1", 443), timeout=2); isolated = False
except Exception:
    isolated = True
p.kill()
print(f"started={started} isolated_from_network={isolated}")
sys.exit(0 if started and isolated else 1)
PY
