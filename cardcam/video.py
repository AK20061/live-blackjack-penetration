import time

import cv2
import numpy as np


def open_video(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps:
        fps = 30
    return cap, fps


def frames_from_video(path, every=0.5):
    cap, fps = open_video(path)
    step = max(1, round(fps * every))
    i = 0
    while True:
        if i % step == 0:
            ok, frame = cap.read()
            if not ok:
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            yield t, frame
        else:
            ok = cap.grab()
            if not ok:
                break
        i += 1


def frame_at(path, t):
    cap, fps = open_video(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        return None
    return frame


def make_warp(corners, size=(1920, 1080)):
    w, h = size
    src = np.float32(corners)
    dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    matrix = cv2.getPerspectiveTransform(src, dst)

    def warp(image):
        return cv2.warpPerspective(image, matrix, size)

    return warp


def start_camera():
    from picamera2 import Picamera2

    cam = Picamera2()
    config = cam.create_still_configuration(main={"size": (2304, 1296), "format": "RGB888"})
    cam.configure(config)
    cam.start()
    time.sleep(2)
    return cam


def lock_camera(cam):
    cam.set_controls({"AfMode": 2})
    time.sleep(3)
    lens = cam.capture_metadata()["LensPosition"]
    cam.set_controls({
        "AfMode": 0,
        "LensPosition": lens,
        "AeEnable": False,
        "ExposureTime": 16667,
        "AnalogueGain": 2.0,
    })


def frames_from_camera(every=0.5, warp=None):
    cam = start_camera()
    lock_camera(cam)
    t0 = time.time()
    try:
        while True:
            frame = cam.capture_array()
            if warp is not None:
                frame = warp(frame)
            yield time.time() - t0, frame
            time.sleep(every)
    finally:
        cam.stop()
