# -*- coding: utf-8 -*-
"""App models.
"""

import logging
import threading
import time

import cv2

from ..azure_iot.utils import get_iothub_module_client
from .exceptions import StreamOpenRTSPError

logger = logging.getLogger(__name__)

# Stream
KEEP_ALIVE_THRESHOLD = 10  # Seconds

# Stream Manager
STREAM_GC_TIME_THRESHOLD = 5  # Seconds
PRINT_STREAMS = False

class Stream():
    """Stream Class"""

    def __init__(self, rtsp, camera_id, part_id=None):
        if rtsp == '0':
            self.rtsp = 0
        elif rtsp == "1":
            self.rtsp = 1
        elif isinstance(rtsp, str) and rtsp.lower().find("rtsp") == 0:
            self.rtsp = "rtsp" + rtsp[4:]
        self.camera_id = camera_id
        self.part_id = part_id

        self.last_active = time.time()
        self.status = "init"
        self.last_img = None
        self.cur_img_index = 0
        self.last_get_img_index = 0
        self.id = id(self)

        self.mutex = threading.Lock()
        self.iot = get_iothub_module_client()
        self.keep_alive = time.time()
        self.cap = None
        logger.info("iot %s", self.iot)

        # test rtsp
        self.cap = cv2.VideoCapture(self.rtsp)
        if not self.cap.isOpened():
            raise StreamOpenRTSPError

    def update_keep_alive(self):
        """update_keep_alive.
        """
        self.keep_alive = time.time()

    def gen(self):
        """generator for stream.
        """
        self.status = "running"

        logger.info("start streaming with %s", self.rtsp)
        while self.status == "running" and (
                self.keep_alive + KEEP_ALIVE_THRESHOLD > time.time()):
            if not self.cap.isOpened():
                raise StreamOpenRTSPError
            has_img, img = self.cap.read()
            # Need to add the video flag FIXME
            if not has_img:
                self.cap = cv2.VideoCapture(self.rtsp)
                time.sleep(1)
                continue

            img = cv2.resize(img, None, fx=0.5, fy=0.5)
            self.last_active = time.time()
            self.last_img = img.copy()
            self.cur_img_index = (self.cur_img_index + 1) % 10000
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" +
                   cv2.imencode(".jpg", img)[1].tobytes() + b"\r\n")
        logger.info('%s releasing self...', self)
        self.cap.release()

    def get_frame(self):
        """get_frame.
        """
        logger.info("get frame %s", self)
        # b, img = self.cap.read()
        time_begin = time.time()
        while True:
            if time.time() - time_begin > 5:
                break
            if self.last_get_img_index == self.cur_img_index:
                time.sleep(0.01)
            else:
                break
        self.last_get_img_index = self.cur_img_index
        img = self.last_img.copy()
        # if b: return cv2.imencode('.jpg', img)[1].tobytes()
        # else : return None
        return cv2.imencode(".jpg", img)[1].tobytes()

    def close(self):
        """close.

        close the stream.
        """
        self.status = "stopped"
        try:
            self.cap.release()
            logger.info("Release cap success")
        except:
            logger.error("Release cap failed")

    def __str__(self):
        return f"<Stream id:{self.id} rtsp:{self.rtsp}>"

    def __repr__(self):
        return f"<Stream id:{self.id} rtsp:{self.rtsp}>"

class StreamManager():
    """StreamManager
    """

    def __init__(self):
        self.streams = []
        self.mutex = threading.Lock()
        self.gc()

    def add(self, stream: Stream):
        """add stream
        """
        self.streams.append(stream)

    def get_stream_by_id(self, stream_id):
        """get_stream_by_id
        """

        self.mutex.acquire()

        for i in range(len(self.streams)):
            stream = self.streams[i]
            if stream.id == stream_id:

                self.mutex.release()
                return stream

        self.mutex.release()
        return None

    def gc(self):
        """Garbage collector

        IMPORTANT, autoreloader will not reload threading,
        please restart the server if you modify the thread
        """

        def _gc(self):
            while True:
                self.mutex.acquire()
                if PRINT_STREAMS:
                    logger.info("streams: %s", self.streams)
                to_delete = []
                for stream in self.streams:
                    if (stream.last_active + STREAM_GC_TIME_THRESHOLD <
                            time.time()):

                        # stop the inactive stream
                        # (the ones users didnt click disconnect)
                        logger.info('stream %s inactive', stream)
                        stream.close()

                        # collect the stream, to delete later
                        to_delete.append(stream)

                for stream in to_delete:
                    self.streams.remove(stream)

                self.mutex.release()
                time.sleep(3)

        threading.Thread(target=_gc, args=(self,)).start()