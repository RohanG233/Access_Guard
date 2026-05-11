/**
 * AccessGuard — shared client-side logic
 * Used by store.html and recognize.html
 */

// ── Face capture (browser webcam) ────────────────────────────────────────────

let _stream = null; // holds the active MediaStream so we can stop it

function captureFaceData() {
    // Build the modal overlay
    const overlay = document.createElement('div');
    overlay.id = 'faceOverlay';
    overlay.style.cssText = `
        position:fixed; inset:0; background:rgba(0,5,2,0.92);
        display:flex; flex-direction:column; align-items:center;
        justify-content:center; z-index:9999;
        font-family:'Share Tech Mono',monospace;
    `;

    const video = document.createElement('video');
    video.autoplay = true;
    video.playsInline = true;
    video.style.cssText = 'width:480px; max-width:90vw; border-radius:2px; border:2px solid #00ff64; box-shadow: 0 0 20px rgba(0,255,100,0.4);';

    const hint = document.createElement('p');
    hint.textContent = '> POSITION FACE IN FRAME — CLICK CAPTURE';
    hint.style.cssText = 'color:#7affb2; margin:14px 0 10px; font-size:0.8rem; letter-spacing:2px;';

    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex; gap:12px;';

    const btnCapture = document.createElement('button');
    btnCapture.innerHTML = '<i class="fas fa-camera"></i>&nbsp; CAPTURE';
    btnCapture.className = 'btn btn-primary';

    const btnCancel = document.createElement('button');
    btnCancel.innerHTML = 'CANCEL';
    btnCancel.className = 'btn btn-danger';

    btnRow.appendChild(btnCapture);
    btnRow.appendChild(btnCancel);
    overlay.appendChild(video);
    overlay.appendChild(hint);
    overlay.appendChild(btnRow);
    document.body.appendChild(overlay);

    // Start webcam
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            _stream = stream;
            video.srcObject = stream;
        })
        .catch(() => {
            closeOverlay(overlay);
            showAlert('Could not access webcam. Please allow camera permission and try again.');
        });

    // Capture snapshot
    btnCapture.addEventListener('click', () => {
        const canvas = document.createElement('canvas');
        // Cap resolution to 640px wide to keep payload small
        const maxW = 640;
        const scale = Math.min(1, maxW / video.videoWidth);
        canvas.width  = Math.round(video.videoWidth  * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);

        // Compress to JPEG at 0.6 quality — keeps file well under 200KB
        const base64 = canvas.toDataURL('image/jpeg', 0.6).split(',')[1];

        document.getElementById('face_data').value = base64;
        document.getElementById('faceStatus').innerHTML =
            '<span class="status-ok"><i class="fas fa-check-circle"></i> SCAN OK</span>';

        closeOverlay(overlay);
        checkFormCompletion();
    });

    btnCancel.addEventListener('click', () => closeOverlay(overlay));
}

function closeOverlay(overlay) {
    if (_stream) {
        _stream.getTracks().forEach(t => t.stop());
        _stream = null;
    }
    if (overlay && overlay.parentNode) overlay.remove();
}

// ── Voice capture (server-side mic) ──────────────────────────────────────────

function captureVoiceData() {
    const preview = document.getElementById('voicePreview');
    preview.style.display = 'block';
    fetch('/capture_voice_data')
        .then(r => r.json())
        .then(data => {
            preview.style.display = 'none';
            if (data.success) {
                document.getElementById('voice_data').value = data.voice_data;
                document.getElementById('voiceStatus').innerHTML =
                    '<span class="status-ok"><i class="fas fa-check-circle"></i> SAMPLE OK</span>';
                checkFormCompletion();
            } else {
                showAlert('Voice capture failed. Make sure your microphone is connected and try again.');
            }
        })
        .catch(() => {
            preview.style.display = 'none';
            showAlert('Voice capture request failed.');
        });
}

// ── Form gate ─────────────────────────────────────────────────────────────────

function checkFormCompletion() {
    const ready = document.getElementById('face_data').value &&
                  document.getElementById('voice_data').value;
    document.getElementById('submitButton').disabled = !ready;
}

// ── Alert helper ──────────────────────────────────────────────────────────────

function showAlert(message, type = 'danger') {
    const container = document.getElementById('alertContainer');
    if (!container) { alert(message); return; }
    const div = document.createElement('div');
    div.className = `alert alert-${type} alert-dismissible fade show`;
    div.role = 'alert';
    div.innerHTML = `${message}
        <button type="button" class="close" data-dismiss="alert" aria-label="Close">
            <span aria-hidden="true">&times;</span>
        </button>`;
    container.appendChild(div);
    setTimeout(() => div.remove(), 5000);
}
