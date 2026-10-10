import os
import uuid

import boto3
import pymysql
from botocore.config import Config
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    course = request.form.get("course", "").strip()
    photo = request.files.get("photo")

    if not all((name, email, course)) or not photo or not photo.filename:
        return "Complete all fields and choose a photo.", 400

    if len(name) > 100 or len(email) > 255 or len(course) > 100:
        return "One of the fields is too long.", 400

    filename = secure_filename(photo.filename)
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in {"jpg", "jpeg", "png"}:
        return "Choose a JPG or PNG photo.", 400

    connection = None
    try:
        bucket = os.environ["S3_BUCKET_NAME"]
        region = os.environ["AWS_REGION"]
        key = f"photos/{uuid.uuid4().hex}.{extension}"
        content_type = "image/png" if extension == "png" else "image/jpeg"

        s3 = boto3.client(
            "s3",
            region_name=region,
            config=Config(
                connect_timeout=5,
                read_timeout=10,
                retries={"max_attempts": 0},
            ),
        )
        s3.upload_fileobj(
            photo.stream,
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        photo_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

        connection = pymysql.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO students (name, email, course, photo_url) "
                "VALUES (%s, %s, %s, %s)",
                (name, email, course, photo_url),
            )
        connection.commit()
        return "Student Registered Successfully"

    except Exception:
        app.logger.exception("Registration failed")
        return "Registration failed. Check the service logs.", 500

    finally:
        if connection is not None:
            connection.close()
