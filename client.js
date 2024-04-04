var pcs = {};
var pis = [];

function negotiate(pi) {
    pcs[pi.name].addTransceiver('video', { direction: 'recvonly' });
    pcs[pi.name].addTransceiver('audio', { direction: 'recvonly' });

    return pcs[pi.name].createOffer().then(function (offer) {
        return pcs[pi.name].setLocalDescription(offer);
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
                document.getElementById(`video-${pi.name}`).srcObject = evt.streams[0];
            } else {
                document.getElementById(`audio-${pi.name}`).srcObject = evt.streams[0];
            }
        });

        pcs[pi.name] = pc;
        negotiate(pi);
    })

    document.getElementById('start').style.display = 'none';
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('stop').style.display = 'none';

    // close peer connection
    setTimeout(function () {
        Object.values(pcs).map((pc) => pc.close());
    }, 100);
}

setInterval(() => {
    currentTime = Date.now();
    document.querySelector("#test").textContent = currentTime;
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
                h1Dom.textContent = `${pi.name}`;
        
                headerDivDom.append(h1Dom);
        
                const videoDom = document.createElement("video");
                videoDom.setAttribute("id", `video-${pi.name}`);
                videoDom.setAttribute("autoplay", true);
                videoDom.setAttribute("playsinline", true);
                const audioDom = document.createElement("audio");
                audioDom.setAttribute("id", `audio-${pi.name}`);
        
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