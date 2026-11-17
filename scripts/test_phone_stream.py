"""Phase 0 (task 0.6): read a phone camera stream and measure fps and delay.

Usage (from the project folder):
    python -m scripts.test_phone_stream http://192.168.1.2:8080
    python -m scripts.test_phone_stream http://192.168.1.2:8080 --seconds 20 --no-window

Measuring the delay: point the phone camera at the laptop screen so it films
this window. The window shows the laptop clock; the phone's picture of the
clock is older. Delay = clock in the corner - clock seen inside the video.
Press q to quit.
"""

import argparse
import threading
import time

import cv2

STREAM_PATHS = {"8080": "/video", "4747": "/video"}  # IP Webcam, DroidCam


class LatestFrameReader:
    """Reads frames in a thread and keeps only the newest one (no backlog)."""

    def __init__(self, url):
        self.cap = cv2.VideoCapture(url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = None
        self.count = 0
        self.running = True
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            with self.lock:
                self.frame = frame
                self.count += 1

    def latest(self):
        with self.lock:
            return self.frame, self.count

    def stop(self):
        self.running = False
        self.thread.join(timeout=2)  # let the thread finish its last read
        self.cap.release()


def stream_url(base):
    base = base.rstrip("/")
    port = base.rsplit(":", 1)[-1]
    if base.endswith("/video") or port not in STREAM_PATHS:
        return base
    return base + STREAM_PATHS[port]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="address shown by the phone app")
    parser.add_argument("--seconds", type=float, default=0, help="0 = until q")
    parser.add_argument("--no-window", action="store_true")
    args = parser.parse_args()

    url = stream_url(args.url)
    print(f"Connecting to {url} ...")
    reader = LatestFrameReader(url)

    start = time.time()
    while reader.latest()[0] is None:
        if time.time() - start > 10:
            reader.stop()
            raise SystemExit("No video after 10 s. Is the app's server running?")
        time.sleep(0.05)
    print(f"First frame after {time.time() - start:.2f} s")

    t0, n0 = time.time(), reader.latest()[1]
    window_fps, last_t, last_n = 0.0, t0, n0
    while True:
        frame, count = reader.latest()
        now = time.time()
        if now - last_t >= 1.0:
            window_fps = (count - last_n) / (now - last_t)
            last_t, last_n = now, count

        if not args.no_window:
            view = frame.copy()
            clock = time.strftime("%H:%M:%S", time.localtime(now))
            clock += f".{int(now * 1000) % 1000:03d}"
            cv2.putText(view, clock, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6,
                        (0, 255, 255), 3)  # fmt: skip
            cv2.putText(view, f"{window_fps:.1f} fps", (20, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)  # fmt: skip
            cv2.imshow("VehiGuard phone stream (q = quit)", view)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        else:
            time.sleep(0.02)

        if args.seconds and now - t0 >= args.seconds:
            break

    elapsed = time.time() - t0
    frames = reader.latest()[1] - n0
    h, w = frame.shape[:2]
    reader.stop()
    cv2.destroyAllWindows()
    print(f"Resolution: {w}x{h}")
    print(
        f"Frames: {frames} in {elapsed:.1f} s  ->  average {frames / elapsed:.1f} fps"
    )
    print("Target: >= 10 fps (task 0.6)", "PASS" if frames / elapsed >= 10 else "FAIL")


if __name__ == "__main__":
    main()
