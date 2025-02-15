import os
import ssl
import cv2
import json
import aiortc
import asyncio
import logging
import argparse
import numpy as np
import aiohttp_cors
from aiohttp import web
from aiortc.rtcrtpsender import RTCRtpSender
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack

ROOT = os.path.dirname(__file__)

relay = None
wecam = None
pcs = set()

def create_local_tracks(play_from, decode):
    global relay, webcam

    if play_from:
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video
    else:
        options = {"framerate": "30", "video_size": "640x480"}

        if relay is None:
            webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
            relay = MediaRelay()

        return None, relay.subscribe(webcam.video, buffered=False)

def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )

async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

async def config_json(request):
    content = open(os.path.join(ROOT, "config.json"), "r").read()
    return web.Response(content_type="application/json", text=content)


class VideoStream(VideoStreamTrack):
    def __init__(self, camera):
        super().__init__()
        self.camera = camera

    async def recv(self):
        video_frame = await self.camera.get_frame()
        pts, time_base = await self.next_timestamp()

        # Create a VideoFrame object directly from the OpenCV frame
        frame = aiortc.av.VideoFrame.from_ndarray(video_frame, format='rgb24')
        frame.pts = pts
        frame.time_base = time_base

        return frame

class Camera:
    def __init__(self):
        self.video_capture = cv2.VideoCapture(0)
        self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    async def get_frame(self):
        success, frame = self.video_capture.read()
        if not success:
            raise RuntimeError("Failed to read frame from camera")

        # Convert the frame to RGB format
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Return the frame as a numpy array
        return frame_rgb
    
async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed" :
            await pc.close()
            pcs.discard(pc)
        if pc.connectionState == "closed":
            pcs.discard(pc)

    camera = Camera()
    video_track = VideoStream(camera)
    pc.addTrack(video_track)

    # open media source
    # audio, video = create_local_tracks(
    #    args.play_from, decode=not args.play_without_decoding
    # )

    # if audio:
    #     audio_sender = pc.addTrack(audio)
    #     if args.audio_codec:
    #         force_codec(pc, audio_sender, args.audio_codec)
    #     elif args.play_without_decoding:
    #         raise Exception("You must specify the audio codec using --audio-codec")

    # if video:
    #     video_sender = pc.addTrack(video)
    #     if args.video_codec:
    #         force_codec(pc, video_sender, args.video_codec)
    #     elif args.play_without_decoding:
    #         raise Exception("You must specify the video codec using --video-codec")
    

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    os._exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Raspberry Pi5 webcam system")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--play-from", help="Read the media from a file and sent it."),
    parser.add_argument(
        "--play-without-decoding",
        help=(
            "Read the media without decoding it (experimental). "
            "For now it only works with an MPEGTS container with only H.264 video."
        ),
        action="store_true",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument(
        "--audio-codec", help="Force a specific audio codec (e.g. audio/opus)"
    )
    parser.add_argument(
        "--video-codec", help="Force a specific video codec (e.g. video/H264)"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    app = web.Application()
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
    })
    
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_get("/config.json", config_json)
    cors.add(app.router.add_post("/offer", offer))
    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)