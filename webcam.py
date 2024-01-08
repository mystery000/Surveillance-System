import argparse
import asyncio
import json
import logging
import os
import platform
import ssl
import cv2
import aiohttp_cors
import psutil
import time
import signal
from datetime import datetime
import os

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCOutboundRtpStreamStats
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender

ROOT = os.path.dirname(__file__)


relay = {}
webcam = {}

camera_list = []
running_tasks = {}

pcs = {}

def signal_handler(signum, frame):
    raise TimeoutError

def create_local_tracks(camera, play_from, decode):
    global relay, webcam

    if play_from:
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video
    else:
        options = {"framerate": "15", "video_size": "640x480"}
        if camera not in relay.keys():
            webcam[camera] = MediaPlayer(camera, format="v4l2", options=options)
            relay[camera] = MediaRelay()
        return None, relay[camera].subscribe(webcam[camera].video, buffered=False)


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


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    camera = params["camera"]

    pc = RTCPeerConnection()
    pcs[camera] = pc

    @pc.on("datachannel")
    def on_datachannel(channel):
        print("Data channel opened on the server")
        # Start sending server information to the client
        task = asyncio.create_task(send_server_info(pc, channel, camera))
        running_tasks[camera] = task
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("----------Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            running_tasks[camera].cancel()
            del running_tasks[camera]

            try:
                await pcs[camera].close()
                del pcs[camera]
            except Exception as e:
                pass

            try:
                webcam[camera].video.stop()
                del webcam[camera]
            except Exception as e:
                pass

            del relay[camera]

            
            

    # open media source
    audio, video = create_local_tracks(
       camera, args.play_from, decode=not args.play_without_decoding
    )

    if audio:
        audio_sender = pc.addTrack(audio)
        if args.audio_codec:
            force_codec(pc, audio_sender, args.audio_codec)
        elif args.play_without_decoding:
            raise Exception("You must specify the audio codec using --audio-codec")

    if video:
        video_sender = pc.addTrack(video)
        if args.video_codec:
            force_codec(pc, video_sender, args.video_codec)
        elif args.play_without_decoding:
            raise Exception("You must specify the video codec using --video-codec")

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
    global pcs
    # close peer connections
    for key in pcs:
        await pcs[key].close()
    pcs = {}

def enumerate_cameras():
    for i in range(50):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            camera_list.append(f'/dev/video{i}')
            cap.release()
    return camera_list

async def get_cameras(request):
    global pcs, running_tasks, relay, camera_list, webcam
    # close peer connections

    for key in webcam:
        print(f"start stopping Camera {key}")
        try:
            signal.signal(signal.SIGALRM, signal_handler)
            signal.alarm(3)
            webcam[key].video.stop()
            signal.pause()
        except Exception as e:
            print(e)
            print(f"Timeout {key}")
        print(f"Video Player for Camera {key} Stopped")
    webcam = {}

    for key in pcs:
        print(f"PeerConnection start closing for Camera {key} Closed")
        await pcs[key].close()
        print(f"PeerConnection to Camera {key} Closed")
    pcs = {}

    for key in running_tasks:
        running_tasks[key].cancel()
        print(f"Task for Camera {key} Cancelled")
    running_tasks = {}


    # for key in relay:
    #     relay[key].stop_all()
    #     print(f"Realy for Camera {key} Stopped")
    relay = {}

    camera_list = []
    print("before enumerate")
    enumerate_cameras()
    print("after enumerate")

    return web.json_response(camera_list)

async def send_server_info(pc, data_channel, camera):
    prev_bytes_sent = 0
    prev_time = datetime.now()

    while True:
        try:
            bitrate_kbps = 0
            stats = await pc.getStats()
            for test in stats:
                stat = stats[test]
                if isinstance(stat, RTCOutboundRtpStreamStats) and stat.kind == "video":
                    # Find the stat with type "outbound-rtp" for video
                    bytes_sent = stat.bytesSent
                    # Calculate bitrate in bps
                    # print("stat", stat.timestamp, stat.timestamp.timestamp())
                    # print("prev", prev_time.timestamp, prev_time.timestamp())
                    # print(camera, (bytes_sent - prev_bytes_sent), (stat.timestamp.timestamp() - prev_time.timestamp()))
                    bitrate_bps = (bytes_sent - prev_bytes_sent) / (stat.timestamp.timestamp() - prev_time.timestamp())
                    # Convert bitrate to kbps for easier reading
                    bitrate_kbps = bitrate_bps * 8 / 1000

                    # Update previous values for the next iteration
                    prev_bytes_sent = stat.bytesSent
                    prev_time = stat.timestamp

                    break

            load1, load5, load15 = psutil.getloadavg()
            cpu_percent = (load15/os.cpu_count()) * 100

            total_memory, used_memory, free_memory = map(
            int, os.popen('free -t -m').readlines()[-1].split()[1:])
            ram_percent =  round((used_memory/total_memory) * 100, 2)

            # Create a JSON payload with the server information
            server_info = {
                "cpu_percent": cpu_percent,
                "ram_percent": ram_percent,
                "bitrate": bitrate_kbps,
                "camera": camera
            }

            # Send the JSON payload to the client
            data_channel.send(json.dumps(server_info))

        except Exception as e:
            print(e)
            #  print(f"Error fetching bandwidth info: {str(e)}")
        # Adjust the interval based on your requirements
        await asyncio.sleep(5)  # Send data every 5 seconds (adjust as needed)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam demo")
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
    cors.add(app.router.add_post("/offer", offer))
    cors.add(app.router.add_get("/get_cameras", get_cameras))
    camera_list = enumerate_cameras()
    print(camera_list)
    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
