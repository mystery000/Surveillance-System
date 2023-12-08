var pcs = {};
var cameras = [];
function negotiate(camera) {
    pcs[camera].addTransceiver('video', {direction: 'recvonly'});
    pcs[camera].addTransceiver('audio', {direction: 'recvonly'});
    return pcs[camera].createOffer().then(function(offer) {
        return pcs[camera].setLocalDescription({...offer, camera});
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (pcs[camera].iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pcs[camera].iceGatheringState === 'complete') {
                        pcs[camera].removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pcs[camera].addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = pcs[camera].localDescription;
        return fetch('/offer', {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
                camera: camera
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        return pcs[camera].setRemoteDescription(answer);
    }).catch(function(e) {
        alert(e);
    });
}

function start() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    if (document.getElementById('use-stun').checked) {
        config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];
    }
    cameras.map((camera) => {
        pc = new RTCPeerConnection(config);
        // connect audio / video
        pc.addEventListener('track', function(evt) {
            if (evt.track.kind == 'video') {
                document.getElementById(`video-${camera}`).srcObject = evt.streams[0];
            } else {
                document.getElementById(`audio-${camera}`).srcObject = evt.streams[0];
            }
        });

        pcs[camera] = pc;
        negotiate(camera);
    })

    document.getElementById('start').style.display = 'none';
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('stop').style.display = 'none';

    // close peer connection
    setTimeout(function() {
        Object.values(pcs).map((pc) => pc.close());
    }, 500);
}

setInterval(() => {
    currentTime = Date. now(); 
    const test = currentTime;
    document.querySelector("#test").textContent = test;
}, (1));

(function() {
    fetch("/get_cameras")
    .then((res) => res.json())
    .then((data) => {
        cameras = data;
        const mediaDom = document.getElementById("vidoe-list");

        cameras.map((camera) => {
            const divDom = document.createElement("div");
            const h1Dom = document.createElement("h1");
            h1Dom.textContent = camera;
            const videoDom = document.createElement("video");
            videoDom.setAttribute("id", `video-${camera}`);
            videoDom.setAttribute("autoplay", true);
            videoDom.setAttribute("playsinline", true);
            const audioDom = document.createElement("audio");
            audioDom.setAttribute("id", `audio-${camera}`);
            divDom.append(h1Dom);
            divDom.append(videoDom);
            divDom.append(audioDom);
            mediaDom.append(divDom)
        })
    })
 })();