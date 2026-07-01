import json
import os
import threading
import time
import uuid

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from converter import CHARSET_PRESETS, AsciiVideoConverter

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024  # 4 GB max upload

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# job_id → { status, progress, output_path, error }
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


# ── Static ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/presets")
def presets():
    return jsonify(CHARSET_PRESETS)


# ── Conversion ────────────────────────────────────────────────────────────────

@app.route("/convert", methods=["POST"])
def convert():
    if "video" not in request.files:
        return jsonify({"error": "Aucun fichier vidéo reçu."}), 400

    video_file = request.files["video"]
    charset  = request.form.get("charset", " .:-=+*#@%")
    fg_color = request.form.get("fg_color", "#00ff41")
    bg_color = request.form.get("bg_color", "#000000")
    font_size = int(request.form.get("font_size", 10))
    colored   = request.form.get("colored", "false").lower() == "true"
    invert    = request.form.get("invert", "auto")
    invert_val = None if invert == "auto" else (invert == "true")

    job_id = str(uuid.uuid4())
    input_path  = os.path.join(UPLOAD_DIR, f"{job_id}_in.mp4")
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_out.mp4")

    video_file.save(input_path)

    with jobs_lock:
        jobs[job_id] = {"status": "processing", "progress": 0, "output_path": output_path}

    def run():
        try:
            conv = AsciiVideoConverter(
                charset=charset,
                fg_color=fg_color,
                bg_color=bg_color,
                font_size=font_size,
                colored=colored,
                invert=invert_val,
            )

            def on_progress(p):
                with jobs_lock:
                    jobs[job_id]["progress"] = p

            conv.convert_video(input_path, output_path, progress_callback=on_progress)

            with jobs_lock:
                jobs[job_id]["status"] = "done"

        except Exception as exc:
            with jobs_lock:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = str(exc)
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── Progress (SSE) ────────────────────────────────────────────────────────────

@app.route("/progress/<job_id>")
def progress(job_id: str):
    def stream():
        while True:
            with jobs_lock:
                job = jobs.get(job_id, {})
            payload = json.dumps({
                "status":   job.get("status", "not_found"),
                "progress": job.get("progress", 0),
                "error":    job.get("error", ""),
            })
            yield f"data: {payload}\n\n"
            if job.get("status") in ("done", "error", "not_found"):
                break
            time.sleep(0.4)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Download ──────────────────────────────────────────────────────────────────

@app.route("/download/<job_id>")
def download(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job introuvable."}), 404
    if job["status"] != "done":
        return jsonify({"error": "Conversion non terminée."}), 400

    path = job["output_path"]
    if not os.path.exists(path):
        return jsonify({"error": "Fichier de sortie introuvable."}), 404

    # Support Range requests so the HTML5 <video> player can seek
    as_attachment = request.args.get("dl") == "1"
    return send_file(
        path,
        mimetype="video/mp4",
        as_attachment=as_attachment,
        download_name="ascii_video.mp4",
        conditional=True,  # enables Range/ETag support
    )


@app.route("/cleanup/<job_id>", methods=["DELETE"])
def cleanup(job_id: str):
    with jobs_lock:
        job = jobs.pop(job_id, None)
    if job and os.path.exists(job.get("output_path", "")):
        os.remove(job["output_path"])
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("\n  ASCII Video Converter")
    print("  -> http://localhost:5000\n")
    app.run(debug=False, port=5000, threaded=True)
