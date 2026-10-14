from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
import base64
import json
import os
import webbrowser

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
TEXT_MODEL = "gemini-3.5-flash-lite"
IMAGE_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent"
SYSTEM = """You are Orbit, a careful social campaign content agent. Quickly understand the brief, plan the message, draft copy, then check factual claims and audience fit. Return ONLY a concise JSON object with these keys: strategy (string), caption (string), hashtags (array of strings), visual_prompt (string), audience_angles (array of objects with segment and angle strings), twin_suggestions (array of 2-3 short strings), claims_to_verify (array of strings), improvements (array of strings). Use the Digital Twin profile and interest scores when supplied to tailor twin_suggestions and audience_angles. The Digital Twin uses synthetic audience data: treat its scores as directional context, never a real forecast or proof of performance. Never invent ingredients, prices, discounts, awards, health claims, locations, or product features. Treat verified_details as the only confirmed product facts. If there are no verified details, write generic copy and add a useful question or reminder in claims_to_verify. Keep language natural, concise, and suitable for the chosen platform. Do not target or stereotype people based on sensitive traits. Image prompts must describe visual composition only and must not render text or logos."""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, maximum_size):
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > maximum_size:
            raise ValueError("size")
        return json.loads(self.rfile.read(size))

    def do_GET(self):
        if self.path == "/api/health":
            self._json(200, {
                "text_ready": bool(os.environ.get("GEMINI_API_KEY")),
                "image_ready": self.cloudflare_ready(),
                "text_model": TEXT_MODEL,
                "image_model": IMAGE_MODEL,
            })
            return
        if self.path == "/api/image-status":
            ready = self.cloudflare_ready()
            self._json(200, {
                "available": ready,
                "model": "Cloudflare Workers AI · FLUX.2 klein 4B" if ready else None,
                "message": (
                    "Ready · Cloudflare Workers AI · free daily allowance applies."
                    if ready else
                    "Add your Cloudflare account ID and Workers AI API token when starting Orbit."
                ),
            })
            return
        if self.path == "/":
            self.path = "/orbit-campaign-twin-prototype.html"
        super().do_GET()

    @staticmethod
    def cloudflare_ready():
        return bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))

    def do_POST(self):
        if self.path == "/api/image-generate":
            self.generate_cloudflare_image()
            return
        if self.path != "/api/content-agent":
            self._json(404, {"error": "Route not found."})
            return

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            self._json(503, {"error": "No Gemini API key is set. Close Orbit and restart it with Start-Agent.ps1."})
            return
        try:
            incoming = self._read_json(16000)
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "Request must contain valid JSON and stay under 16 KB."})
            return

        fields = {
            "brief": incoming.get("brief", ""),
            "product": incoming.get("product", ""),
            "verified_details": incoming.get("verified_details", ""),
            "audience": incoming.get("audience", ""),
            "channel": incoming.get("channel", "Instagram"),
            "brand_voice": incoming.get("brand_voice", "Warm and thoughtful"),
            "digital_twin": incoming.get("digital_twin", {}),
        }
        if not isinstance(fields["brief"], str) or not fields["brief"].strip():
            self._json(400, {"error": "Add a campaign brief first."})
            return

        prompt = "Create a campaign package from this brief. Consider the user's current brand voice.\n\n" + json.dumps(fields, ensure_ascii=False)
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.7,
                "maxOutputTokens": 1100,
                "thinkingConfig": {"thinkingLevel": "minimal"},
            },
        }
        request = Request(GEMINI_API_URL, data=json.dumps(payload).encode("utf-8"), headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Orbit-Campaign-Agent/1.0",
        }, method="POST")
        try:
            with urlopen(request, timeout=45) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            package = json.loads(content)
            for name, default in (("strategy", ""), ("caption", ""), ("visual_prompt", ""), ("hashtags", []), ("audience_angles", []), ("twin_suggestions", []), ("claims_to_verify", []), ("improvements", [])):
                if not isinstance(package.get(name, default), type(default)):
                    package[name] = default
            package["model"] = TEXT_MODEL
            self._json(200, package)
        except HTTPError as exc:
            detail = self._provider_error(exc)
            if exc.code == 429:
                self._json(429, {"error": "Gemini's free-tier limit was reached. Wait for the quota to reset; Orbit will not switch to a paid model."})
            elif exc.code in (400, 401, 403):
                self._json(502, {"error": "Google Gemini rejected the request. Check the API key, model access, and free-tier quota. " + detail})
            else:
                self._json(502, {"error": f"Gemini returned HTTP {exc.code}. " + detail})
        except (URLError, TimeoutError):
            self._json(502, {"error": "Could not reach Gemini in time. Check your connection and try again; no result was saved."})
        except (KeyError, IndexError, json.JSONDecodeError, TypeError):
            self._json(502, {"error": "Gemini returned an unreadable response. Try generating again."})

    @staticmethod
    def _provider_error(exc):
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = error.get("message", "") if isinstance(error, dict) else str(error)
            return (message[:350] + " ") if message else ""
        except Exception:
            return ""

    def generate_cloudflare_image(self):
        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        if not account or not token:
            self._json(503, {"error": "Cloudflare is not configured. Close Orbit and enter your account ID and Workers AI token in Start-Agent.ps1."})
            return
        try:
            incoming = self._read_json(8000)
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "Request must contain valid JSON and stay under 8 KB."})
            return
        prompt = incoming.get("prompt", "")
        if not isinstance(prompt, str) or not prompt.strip():
            self._json(400, {"error": "Enter a visual prompt first."})
            return

        boundary = "----OrbitWorkersAIFormBoundary"
        fields = {"prompt": prompt.strip()[:1800], "width": "1024", "height": "1024"}
        parts = []
        for name, value in fields.items():
            parts.extend([
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ])
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{IMAGE_MODEL}"
        request = Request(endpoint, data=body, headers={
            "Authorization": "Bearer " + token,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "Orbit-Campaign-Agent/1.0",
        }, method="POST")
        try:
            with urlopen(request, timeout=180) as response:
                result = response.read()
                content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                response_data = json.loads(result.decode("utf-8"))
                image_data = response_data.get("result", {}).get("image")
                if not image_data:
                    self._json(502, {"error": "Cloudflare completed the request but returned no image. Try a different prompt."})
                    return
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = result
            self._json(200, {
                "data_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
                "model": "Cloudflare Workers AI · FLUX.2 klein 4B",
                "free_tier": True,
            })
        except HTTPError as exc:
            detail = self._provider_error(exc)
            if exc.code == 429:
                self._json(429, {"error": "Cloudflare's free daily AI allowance may be exhausted or busy. Try again later; Orbit will not switch to a paid plan. " + detail})
            elif exc.code in (400, 401, 403):
                self._json(502, {"error": "Cloudflare rejected the request. Check the account ID, Workers AI token permissions, and free-plan access. " + detail})
            else:
                self._json(502, {"error": f"Cloudflare returned HTTP {exc.code}. " + detail})
        except (URLError, TimeoutError, OSError):
            self._json(502, {"error": "Could not reach Cloudflare Workers AI. Check your internet connection and try again."})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            self._json(502, {"error": "Could not read Cloudflare's image response. Try again with a simpler prompt."})


if __name__ == "__main__":
    print(f"Orbit campaign agent is running at http://{HOST}:{PORT}")
    print("Gemini handles campaign text; Cloudflare Workers AI handles images.")
    print("Keys are held only in this local process. Stop with Ctrl+C.")
    if os.environ.get("ORBIT_NO_BROWSER") != "1":
        webbrowser.open(f"http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
