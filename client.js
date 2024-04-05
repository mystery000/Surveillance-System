var pcs = {};
var pis = [];

function negotiate(pi) {
    pcs[pi.name].addTransceiver('video', { direction: 'recvonly' });
    pcs[pi.name].addTransceiver('audio', { direction: 'recvonly' });

    return pcs[pi.name].createOffer().then(function (offer) {
        camera = pi.camera
        return pcs[pi.name].setLocalDescription({ ...offer, camera });
    }).then(function () {
        // wait for ICE gathering to complete
        return new Promise(function (resolve) {
            if (pcs[pi.name].iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pcs[pi.name].iceGatheringState === 'complete') {
                        pcs[pi.name].removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pcs[pi.name].addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function () {
        var offer = pcs[pi.name].localDescription;
        return fetch(`http://${pi.ip}:${pi.port}/offer`, {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
                camera: pi.camera
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function (response) {
        return response.json();
    }).then(function (answer) {
        return pcs[pi.name].setRemoteDescription(answer);
    }).catch(function (e) {
        alert(e);
    });
}
function start() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    if (document.getElementById('use-stun').checked) {
        config.iceServers = [{ urls: ['stun:stun.l.google.com:19302'] }];
    }
    pis.map((pi) => {
        pc = new RTCPeerConnection(config);
        // connect audio / video
        pc.addEventListener('track', function (evt) {
            if (evt.track.kind == 'video') {
                const stream = evt.streams[0];
                const videoTrack = stream.getVideoTracks()[0];
                // Use setInterval to periodically check the video track's settings
                setInterval(() => {
                    const { width, height, frameRate } = videoTrack.getSettings();
                    if (width && height && frameRate) {
                        updateResolutionAndFPS(videoTrack, pi);
                    }
                }, 100);

                // setInterval(() => {
                //     pc.getStats(null).then(stats => {
                //         let statsOutput = "";
                
                //         stats.forEach(report => {
                //             if (report.type === 'inbound-rtp') {
                //                 if(report.kind === 'video') {
                //                     console.log(pi.name, pi.camera, "----", report.packetsLost);
                //                     statsOutput += `<strong>Packet Loss for video: </strong>${report.packetsLost}<br>\n`;
                //                 }
                //             }
                //         });
                //     });
                // }, 1000);

                setInterval(() => {
                    pc.getStats(null).then(stats => {
                        stats.forEach(report => {

                            if (report.type === 'inbound-rtp' && report.kind === 'video') {
                                console.log(`[${pi.name}-${pi.camera}] Packet Loss for video: ${report.packetsLost}`);
                            }
                        });
                    });
                }, 1000);

                document.getElementById(`video-${pi.name}-${pi.camera}`).srcObject = evt.streams[0];
            } else {
                document.getElementById(`audio-${pi.name}-${pi.camera}`).srcObject = evt.streams[0];
            }
        });

        const dataChannel = pc.createDataChannel("camera-status");

        dataChannel.onopen = () => {
            dataChannel.send("Hello, server!");
        };

        dataChannel.addEventListener("message", function (event) {
            const data = JSON.parse(event.data);
            document.getElementById(`bitrate-${data["name"]}-${data['camera']}`).textContent = data['bitrate'].toFixed(2) + " Kbps";
            document.getElementById(`cpu_percent`).textContent = data['cpu_percent'].toFixed(2) + " %";
        })
        pcs[pi.name] = pc;
        negotiate(pi);
    })

    document.getElementById('start').style.display = 'none';
    document.getElementById('stop').style.display = 'inline-block';
}

const updateResolutionAndFPS = (videoTrack, pi) => {
    document.getElementById(`resolution-${pi.name}-${pi.camera}`).textContent = videoTrack.getSettings().width + "x" + videoTrack.getSettings().height;
    document.getElementById(`fps-${pi.name}-${pi.camera}`).textContent = videoTrack.getSettings().frameRate.toFixed(2);
};

function stop() {
    document.getElementById('stop').style.display = 'none';

    // close peer connection
    setTimeout(function () {
        Object.values(pcs).map((pc) => pc.close());
    }, 500);
}

setInterval(() => {
    currentTime = Date.now();
    const test = currentTime;
    document.querySelector("#test").textContent = test;
}, (1));

(function () {
    const mediaDom = document.getElementById("video-list");

    fetch("./config.json")
        .then((res) => {
            if(!res.ok) {
                throw new Error(`HTTP error! Status: ${res.status}`)
            }
            return res.json()
        })
        .then((data) => {
            pis = data["pis"]
            pis.map((pi) => {
                const divDom = document.createElement("div");
        
                const headerDivDom = document.createElement("div");
                headerDivDom.classList.add("header-div")
        
                const h1Dom = document.createElement("h1");
                h1Dom.textContent = `${pi.name}${pi.camera}`;
        
                const fpsDom = document.createElement("span");
                fpsDom.setAttribute("id", `fps-${pi.name}-${pi.camera}`);
        
                const bitrateDom = document.createElement("span");
                bitrateDom.setAttribute("id", `bitrate-${pi.name}-${pi.camera}`);
        
                const resolutionDom = document.createElement("span");
                resolutionDom.setAttribute("id", `resolution-${pi.name}-${pi.camera}`);
        
                headerDivDom.append(h1Dom);
                headerDivDom.append(fpsDom);
                headerDivDom.append(resolutionDom);
                headerDivDom.append(bitrateDom);
        
                const videoDom = document.createElement("video");
                videoDom.setAttribute("id", `video-${pi.name}-${pi.camera}`);
                videoDom.setAttribute("autoplay", true);
                videoDom.setAttribute("playsinline", true);
                const audioDom = document.createElement("audio");
                audioDom.setAttribute("id", `audio-${pi.name}-${pi.camera}`);
        
                divDom.append(headerDivDom);
                divDom.append(videoDom);
                divDom.append(audioDom);
                mediaDom.append(divDom)
            })
        })
        .catch((error) => {
            console.error("Unable to fetch data:", error)
        })
})();