"""Command line:

  sachet run SOURCE      results as JSON lines (stdout or --out) and a summary at the end
  sachet bench SOURCE    frames per second on this machine (does it keep up with the camera?)

SOURCE is a video file, an RTSP/HTTP URL, or a camera index (0).
"""
import argparse
import json
import os
import sys
import time


def _cfg(path):
    from .config import Config
    return Config.load(path)


def _line(r):
    if r["kind"] == "sets":
        return (f"{r['t0']:9.1f}s  sets   {r['label']:25s} sets={r['sets']} sachets={r['sachets']}"
                f"{'  ALERT ' + r['alert'] if r['alert'] != 'none' else ''}")
    return (f"{r['t']:9.1f}s  sachet {r['verdict']:14s}{'  no tray' if r['no_tray'] else ''}"
            f"{'  double strip' if r['double_strip'] else ''}{'  hung first' if r['hung_in_chute_before_falling'] else ''}"
            f"{'  ALERT ' + r['alert'] if r['alert'] != 'none' else ''}")


def cmd_run(a):
    from .pipeline import SachetPipeline
    from .summary import summarize
    pipe = SachetPipeline(_cfg(a.config))
    out = open(a.out, "w") if a.out else sys.stdout
    results = []
    for r in pipe.run(a.source, realtime=a.realtime, start_s=a.start, duration_s=a.duration):
        results.append(r)
        out.write(json.dumps(r) + "\n")
        out.flush()
        if a.out and (a.verbose or r["alert"] != "none"):
            print(_line(r), file=sys.stderr)
    print(json.dumps(summarize(results) | {"last_alert": None}, indent=1), file=sys.stderr)


def cmd_bench(a):
    from .pipeline import SachetPipeline
    pipe = SachetPipeline(_cfg(a.config))
    t0 = time.time()
    for _ in pipe.run(a.source, duration_s=a.seconds):
        pass
    wall = time.time() - t0
    s = pipe.stats
    n = max(1, s["frames"])
    fps = s["frames"] / wall
    print(f"machine: {os.uname().nodename}  cpu cores: {os.cpu_count()}")
    print(f"{s['frames']} frames in {wall:.1f} s = {fps:.0f} fps (incl. decoding)")
    print(f"  signals {s['signal_ms'] / n:.1f} ms/frame, checker {s['engine_ms'] / n:.2f} ms/frame")
    cam = pipe.cfg.fps
    print(f"camera runs at {cam:.0f} fps -> {fps / cam:.1f}x real time on one core")


def main(argv=None):
    from .config import DEFAULT_CONFIG
    p = argparse.ArgumentParser(prog="sachet", description="Scavenger sachet check")
    p.add_argument("--config", default=os.environ.get("SACHET_CONFIG", DEFAULT_CONFIG))
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="results as JSON lines")
    r.add_argument("source")
    r.add_argument("--out", help="write JSON lines here (default: stdout)")
    r.add_argument("--start", type=float, default=0.0, help="start this many seconds into a file")
    r.add_argument("--duration", type=float, default=None, help="stop after this many seconds")
    r.add_argument("--realtime", action="store_true", help="pace a video file at camera speed")
    r.add_argument("-v", "--verbose", action="store_true", help="with --out: print every result, not just alerts")
    r.set_defaults(fn=cmd_run)

    b = sub.add_parser("bench", help="speed on this machine")
    b.add_argument("source")
    b.add_argument("--seconds", type=float, default=300.0, help="how much video to time")
    b.set_defaults(fn=cmd_bench)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
