from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, jsonify, after_this_request
import os
import uuid
import re
import requests
import threading
from data_extraction_script import process_excel_file

app = Flask(__name__)
app.secret_key = "your-secret-key"

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
LOGIN_API_URL = "https://api-platform.mastersindia.co/api/v2/token-auth/"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Global task tracker
task_status = {}

# ===================== Login =====================
@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("login"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            res = requests.post(LOGIN_API_URL, json={
                "username": username,
                "password": password
            })

            if res.status_code == 200 and "token" in res.json():
                new_token = res.json()["token"]
                if not new_token.startswith("JWT "):
                    new_token = "JWT " + new_token

                with open("data_extraction_script.py", "r", encoding="utf-8") as f:
                    content = f.read()
                content = re.sub(r'AUTH_TOKEN\s*=\s*".+?"', f'AUTH_TOKEN = "{new_token}"', content)
                with open("data_extraction_script.py", "w", encoding="utf-8") as f:
                    f.write(content)

                session["logged_in"] = True
                return redirect(url_for("index"))

            return render_template("login.html", error="Login failed: Invalid credentials or no token found.")

        except Exception as e:
            return render_template("login.html", error=f"Error: {str(e)}")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ===================== Form =====================
@app.route("/index", methods=["GET"])
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("index.html")

# ===================== Upload & Start Background Processing =====================
@app.route("/upload", methods=["POST"])
def upload():
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    file = request.files.get("file")
    selected_months = request.form.getlist("selected_months")

    if not file or not selected_months:
        return jsonify({"success": False, "error": "File and months required"}), 400

    filename = file.filename
    task_id = str(uuid.uuid4())
    uploaded_path = os.path.join(UPLOAD_FOLDER, filename)
    processed_path = os.path.join(PROCESSED_FOLDER, filename)
    file.save(uploaded_path)

    date_ranges = {
        month: {
            "from": request.form.get(f"{month}_from") or None,
            "to": request.form.get(f"{month}_to") or None
        } for month in selected_months
    }

    task_status[task_id] = {
        "status": "processing",
        "processed": processed_path,
        "uploaded": uploaded_path,
    }

    def background_process(task_id, uploaded_path, processed_path, month_map):
        try:
            process_excel_file(uploaded_path, month_map, output_path=processed_path)
            task_status[task_id]["status"] = "done"
        except Exception as e:
            task_status[task_id]["status"] = "error"
            task_status[task_id]["error"] = str(e)

    thread = threading.Thread(target=background_process, args=(task_id, uploaded_path, processed_path, date_ranges))
    thread.start()

    return jsonify({"success": True, "redirect": f"/processing?task_id={task_id}"})

# ===================== Polling Endpoint =====================
@app.route("/status", methods=["GET"])
def status():
    task_id = request.args.get("task_id")
    task = task_status.get(task_id)
    if not task:
        return jsonify({"status": "none"}), 404

    return jsonify({
        "status": task.get("status"),
        "download_url": f"/download/{os.path.basename(task['processed'])}" if task.get("status") == "done" else None,
        "error": task.get("error")
    })

# ===================== Processing Page =====================
@app.route("/processing")
def processing():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("processing.html")

# ===================== Download =====================


@app.route("/download/<filename>")
def download(filename):
    processed_path = os.path.join(PROCESSED_FOLDER, filename)
    uploaded_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(processed_path):
        return f"File not found: {filename}", 404

    @after_this_request
    def remove_files(response):
        try:
            if os.path.exists(processed_path):
                os.remove(processed_path)
            if os.path.exists(uploaded_path):
                os.remove(uploaded_path)
        except Exception as cleanup_err:
            print(f"Cleanup failed: {cleanup_err}")
        return response

    return send_from_directory(PROCESSED_FOLDER, filename, as_attachment=True)



# ===================== Run =====================
if __name__ == "__main__":
    print("\u2705 Flask app running at http://127.0.0.1:5000/")
    app.run(debug=True)