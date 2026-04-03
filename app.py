from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "RehabSlash Backend Running ✅"

@app.route("/intake", methods=["POST"])
def intake():
    data = request.json
    print("Received intake:", data)
    return jsonify({"status": "success", "data": data})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})
