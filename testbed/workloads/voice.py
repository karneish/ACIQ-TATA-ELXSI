"""voice.py — voice-only generator: low-rate small-packet UDP voice.
Emulates a voice call at ~0.06 Mbps, ~160B packets, 50 pps. Reuses call.py
shape but exposes a distinct workload kind for scenario wiring.
"""
import argparse, socket, time
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dst',required=True); ap.add_argument('--port',type=int,required=True)
    ap.add_argument('--duration',type=float,default=30.0)
    a=ap.parse_args()
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    end=time.time()+a.duration
    while time.time()<end:
        try: s.sendto(b'\x00'*160,(a.dst,a.port))
        except OSError: break
        time.sleep(0.02)
    s.close()
if __name__=='__main__': main()
