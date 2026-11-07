"""update.py — software_update generator: constant-rate mid-rate TCP.
Emulates a package download with steady ~8 Mbps, ~968B packets, no chunk
laddering. Pairs with classifier update-vs-streaming packet-size rule.
"""
import argparse, socket, threading, time

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dst',required=True); ap.add_argument('--port',type=int,required=True)
    ap.add_argument('--rate-mbps',type=float,default=8.0); ap.add_argument('--duration',type=float,default=30.0)
    ap.add_argument('--packet-size',type=int,default=968)
    a=ap.parse_args()
    payload=b'x'*a.packet_size
    s=socket.create_connection((a.dst,a.port),timeout=5)
    pps=int(a.rate_mbps*1e6/8/a.packet_size); interval=1.0/max(pps,1)
    end=time.time()+a.duration
    while time.time()<end:
        try: s.sendall(payload)
        except OSError: break
        time.sleep(interval)
    s.close()

if __name__=='__main__': main()
