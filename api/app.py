from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import joblib
from urllib.parse import urlparse, parse_qs
import socket
import ssl
import time as time_module
import os
import csv
from datetime import datetime

import requests
import dns.resolver
import whois
from ipwhois import IPWhois
print("=== Flask app started running ===")

app = Flask(__name__)
CORS(app)

# ================================
# LOAD YOUR REAL MODEL
# ================================
MODEL_PATH = "best_model.pkl"
model = joblib.load(MODEL_PATH)
print("Model loaded successfully:", MODEL_PATH)

# ================================
# LOGGING SETUP
# ================================
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "api_log.csv")

# Create folder if missing
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Create CSV file with header if missing
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "url", "probability", "label", "client_ip"])

def log_request(url, probability, label, ip):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            url,
            probability,
            label,
            ip,
        ])

# ================================
# Helper functions
# ================================
def get_hostname(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


def get_domain(host: str) -> str:
    # For simplicity, treat host as domain.
    # If you used tldextract in training, you can switch to that later.
    return host.lower()


def resolve_ips(host: str):
    ips = []
    try:
        answers = dns.resolver.resolve(host, "A")
        ips = [rdata.address for rdata in answers]
    except Exception:
        pass
    return ips


def get_ttl_hostname(host: str) -> int:
    try:
        answers = dns.resolver.resolve(host, "A")
        return answers.rrset.ttl
    except Exception:
        return 0


def get_mx_count(domain: str) -> int:
    try:
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers)
    except Exception:
        return 0


def get_ns_count(domain: str) -> int:
    try:
        answers = dns.resolver.resolve(domain, "NS")
        return len(answers)
    except Exception:
        return 0


def get_spf_flag(domain: str) -> int:
    """1 if SPF record (v=spf1) exists, else 0"""
    try:
        answers = dns.resolver.resolve(domain, "TXT")
        for rdata in answers:
            txt = b"".join(rdata.strings).decode("utf-8", errors="ignore").lower()
            if "v=spf1" in txt:
                return 1
    except Exception:
        pass
    return 0


def get_whois_dates(domain: str):
    """
    Return (activation_days, expiration_days)
    activation_days: how many days since domain creation (age)
    expiration_days: how many days until expiration (remaining life)
    If cannot fetch = (0, 0)
    """
    try:
        w = whois.whois(domain)
        now = time_module.time()

        # creation_date and expiration_date can be list or single
        creation = w.creation_date
        expiration = w.expiration_date

        # Normalize possible list
        if isinstance(creation, list):
            creation = creation[0]
        if isinstance(expiration, list):
            expiration = expiration[0]

        activation_days = 0
        expiration_days = 0

        if creation is not None:
            activation_days = int((now - creation.timestamp()) / 86400)  # seconds -> days
        if expiration is not None:
            expiration_days = int((expiration.timestamp() - now) / 86400)

        return activation_days, expiration_days
    except Exception:
        return 0, 0


def get_asn_ip(ips):
    """
    Very rough ASN lookup using first IP.
    If fail, return 0.
    """
    if not ips:
        return 0
    ip = ips[0]
    try:
        obj = IPWhois(ip)
        res = obj.lookup_rdap()
        asn = res.get("asn", "")
        return int(asn) if asn.isdigit() else 0
    except Exception:
        return 0


def get_time_response_and_redirects(url: str):
    """
    Returns (time_response, qty_redirects)
    time_response in milliseconds
    qty_redirects from response.history
    """
    try:
        start = time_module.time()
        resp = requests.get(url, timeout=5, allow_redirects=True, verify=True)
        end = time_module.time()
        t_resp_ms = int((end - start) * 1000)
        redirects = len(resp.history)
        return t_resp_ms, redirects
    except Exception:
        return 0, 0


def get_tls_ssl_certificate_flag(url: str) -> int:
    """
    1 if HTTPS and TLS handshake works, else 0.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if parsed.scheme != "https" or not host:
            return 0

        port = parsed.port or 443
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                if cert:
                    return 1
    except Exception:
        pass
    return 0


# ================================
# MAIN FEATURE EXTRACTOR (30 features)
# ================================
def extract_features_from_url(url: str) -> np.ndarray:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    domain = get_domain(host)
    path = parsed.path or ""
    query = parsed.query or ""

    # --- directory and file from path ---
    # e.g. "/dir1/dir2/file.php"
    # directory: "/dir1/dir2/"
    # file: "file.php"
    directory = ""
    file_name = ""

    if path:
        if "/" in path:
            parts = path.rsplit("/", 1)
            directory = parts[0] + "/" if parts[0] else "/"
            file_name = parts[1]
        else:
            directory = "/"
            file_name = path

    # ----------------------
    # Lexical-style features
    # ----------------------
    length_url = len(url)

    directory_length = len(directory)
    file_length = len(file_name)

    qty_slash_url = url.count("/")
    qty_dot_url = url.count(".")
    qty_hyphen_url = url.count("-")
    qty_equal_url = url.count("=")
    qty_questionmark_params = query.count("?")  # query rarely has "?", but keep

    qty_dot_directory = directory.count(".")
    qty_hyphen_directory = directory.count("-")
    qty_underline_directory = directory.count("_")
    qty_equal_directory = directory.count("=")

    qty_hyphen_file = file_name.count("-")

    qty_vowels_domain = sum(ch in "aeiouAEIOU" for ch in domain)
    qty_dot_domain = domain.count(".")

    params_length = len(query)
    qty_hyphen_params = query.count("-")
    qty_slash_params = query.count("/")
    qty_percent_params = query.count("%")

    # ----------------------
    # Network / DNS / WHOIS
    # ----------------------
    ips = resolve_ips(host)
    qty_ip_resolved = len(ips)

    ttl_hostname = get_ttl_hostname(host)
    asn_ip = get_asn_ip(ips)

    qty_mx_servers = get_mx_count(domain)
    qty_nameservers = get_ns_count(domain)

    domain_spf = get_spf_flag(domain)

    time_domain_activation, time_domain_expiration = get_whois_dates(domain)

    time_response, qty_redirects = get_time_response_and_redirects(url)

    tls_ssl_certificate = get_tls_ssl_certificate_flag(url)

    # ----------------------
    # ORDER MUST MATCH YOUR FEATURE LIST
    # ----------------------
    features = [
        # 1. directory_length
        directory_length,
        # 2. length_url
        length_url,
        # 3. time_domain_activation
        time_domain_activation,
        # 4. qty_slash_url
        qty_slash_url,
        # 5. file_length
        file_length,
        # 6. ttl_hostname
        ttl_hostname,
        # 7. asn_ip
        asn_ip,
        # 8. qty_dot_directory
        qty_dot_directory,
        # 9. qty_dot_domain
        qty_dot_domain,
        # 10. time_domain_expiration
        time_domain_expiration,
        # 11. qty_hyphen_file
        qty_hyphen_file,
        # 12. qty_hyphen_directory
        qty_hyphen_directory,
        # 13. qty_underline_directory
        qty_underline_directory,
        # 14. qty_equal_directory
        qty_equal_directory,
        # 15. time_response
        time_response,
        # 16. qty_vowels_domain
        qty_vowels_domain,
        # 17. qty_dot_url
        qty_dot_url,
        # 18. qty_mx_servers
        qty_mx_servers,
        # 19. params_length
        params_length,
        # 20. qty_ip_resolved
        qty_ip_resolved,
        # 21. qty_nameservers
        qty_nameservers,
        # 22. qty_hyphen_url
        qty_hyphen_url,
        # 23. qty_redirects
        qty_redirects,
        # 24. qty_hyphen_params
        qty_hyphen_params,
        # 25. tls_ssl_certificate
        tls_ssl_certificate,
        # 26. domain_spf
        domain_spf,
        # 27. qty_equal_url
        qty_equal_url,
        # 28. qty_slash_params
        qty_slash_params,
        # 29. qty_percent_params
        qty_percent_params,
        # 30. qty_questionmark_params
        qty_questionmark_params,
    ]

    return np.array(features, dtype=np.float32).reshape(1, -1)


# ================================
# FLASK ROUTES
# ================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "PhishGuard API running"}), 200



@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    url = data.get("url", "")

    if not url:
        return jsonify({"error": "Missing 'url'"}), 400

    # Extract features
    X = extract_features_from_url(url)

    # Predict
    proba = model.predict_proba(X)[0][1]
    label = "phishing" if proba >= 0.5 else "legitimate"

    # ================================
    # LOG HERE (only new lines)
    # ================================
    client_ip = request.remote_addr
    log_request(url, float(proba), label, client_ip)
    # ================================

    return jsonify({
        "url": url,
        "label": label,
        "probability": float(proba)
    }), 200



if __name__ == "__main__":
    # Run on http://127.0.0.1:5000/
    app.run(host="0.0.0.0", port=5000, debug=True)
