import json
import os
import threading
import time
from datetime import datetime, timezone

import boto3
import requests
from botocore.exceptions import ClientError
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

app = Flask(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EVENTS_BUCKET = os.getenv("EVENTS_BUCKET", "")
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "")
TICKETMASTER_SIZE = int(os.getenv("TICKETMASTER_SIZE", "20"))
TICKETMASTER_COUNTRY = os.getenv("TICKETMASTER_COUNTRY", "US")
FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", "900"))
EVENTS_S3_KEY = "events/latest.json"

s3_client = boto3.client("s3", region_name=AWS_REGION)
cache_lock = threading.Lock()
events_cache = {
    "last_updated": None,
    "events": [],
    "source": "startup",
}

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def fetch_ticketmaster_events() -> list:
    if not TICKETMASTER_API_KEY:
        raise RuntimeError("TICKETMASTER_API_KEY is not configured")

    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": TICKETMASTER_API_KEY,
        "size": TICKETMASTER_SIZE,
        "countryCode": TICKETMASTER_COUNTRY,
        "sort": "date,asc",
        "keyword": "university",
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()
    raw_events = payload.get("_embedded", {}).get("events", [])

    normalized_events = []
    for event in raw_events:
        dates = event.get("dates", {}).get("start", {})
        venue_data = event.get("_embedded", {}).get("venues", [{}])[0]
        images = event.get("images", [])

        normalized_events.append(
            {
                "id": event.get("id"),
                "title": event.get("name", "Untitled Event"),
                "date": dates.get("localDate") or dates.get("dateTime"),
                "time": dates.get("localTime"),
                "venue": venue_data.get("name", "TBA"),
                "city": venue_data.get("city", {}).get("name", ""),
                "country": venue_data.get("country", {}).get("name", ""),
                "description": event.get("info") or event.get("pleaseNote") or "No description provided",
                "image_url": images[0].get("url") if images else None,
                "external_url": event.get("url"),
            }
        )

    return normalized_events


def save_events_to_s3(events: list) -> None:
    if not EVENTS_BUCKET:
        return

    body = json.dumps(
        {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "events": events,
            "source": "ticketmaster",
        },
        indent=2,
    ).encode("utf-8")

    s3_client.put_object(
        Bucket=EVENTS_BUCKET,
        Key=EVENTS_S3_KEY,
        Body=body,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )


def load_events_from_s3() -> dict:
    if not EVENTS_BUCKET:
        return {"last_updated": None, "events": [], "source": "no-bucket"}

    try:
        obj = s3_client.get_object(Bucket=EVENTS_BUCKET, Key=EVENTS_S3_KEY)
        data = json.loads(obj["Body"].read().decode("utf-8"))
        return data
    except ClientError:
        return {"last_updated": None, "events": [], "source": "s3-empty"}


def refresh_events() -> None:
    global events_cache

    try:
        fresh_events = fetch_ticketmaster_events()
        save_events_to_s3(fresh_events)
        with cache_lock:
            events_cache = {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "events": fresh_events,
                "source": "ticketmaster-live",
            }
    except Exception:
        fallback = load_events_from_s3()
        with cache_lock:
            events_cache = fallback


def scheduler_loop() -> None:
    while True:
        refresh_events()
        time.sleep(FETCH_INTERVAL_SECONDS)


def start_scheduler() -> None:
    refresh_events()
    worker = threading.Thread(target=scheduler_loop, daemon=True)
    worker.start()


@app.route("/")
def index():
    with cache_lock:
        data = dict(events_cache)

    if not data.get("events"):
        data = load_events_from_s3()

    return render_template("index.html", data=data)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


@app.route("/api/events")
def api_events():
    with cache_lock:
        return jsonify(events_cache)


@app.route("/upload", methods=["POST"])
def upload_poster():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    if not EVENTS_BUCKET:
        return jsonify({"error": "S3 bucket is not configured"}), 500

    safe_name = secure_filename(file.filename)
    key = f"posters/{int(time.time())}_{safe_name}"

    s3_client.upload_fileobj(
        file,
        EVENTS_BUCKET,
        key,
        ExtraArgs={
            "ContentType": file.content_type,
            "ServerSideEncryption": "AES256",
        },
    )

    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": EVENTS_BUCKET, "Key": key},
        ExpiresIn=3600,
    )

    return jsonify({"message": "Upload successful", "s3_key": key, "preview_url": presigned_url})


start_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
