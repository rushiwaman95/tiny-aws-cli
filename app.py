#!/usr/bin/env python3
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_PATH = os.environ.get("MODEL_PATH", "./supra-mini-aws-final")
PORT = int(os.environ.get("PORT", "8000"))

print(f"Loading model from {MODEL_PATH} ...", flush=True)

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForCausalLM.from_pretrained(MODEL_PATH)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

# Keep CPU usage sane inside a container
if device.type == "cpu":
    torch.set_num_threads(min(4, os.cpu_count() or 1))

print(f"Model ready on {device}", flush=True)


def generate_command(request: str, max_new_tokens: int = 60) -> str:
    prompt = f"User: {request}\nAssistant:"
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    text = tokenizer.decode(out[0], skip_special_tokens=True)

    if "Assistant:" in text:
        text = text.split("Assistant:", 1)[1]

    return text.strip().split("\n", 1)[0].strip()


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "device": str(device)})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/generate":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            request = data.get("request", "").strip()

            if not request:
                self._send_json(400, {"error": "missing 'request'"})
                return

            self._send_json(200, {
                "request": request,
                "command": generate_command(request),
            })
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        print("[api] " + fmt % args, flush=True)


def serve():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving on http://0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


def cli():
    print("Tiny AWS CLI assistant. Type 'exit' to quit.", flush=True)
    while True:
        try:
            req = input("Request: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not req:
            continue
        if req.lower() in ("exit", "quit"):
            break
        print(generate_command(req))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="Run HTTP API")
    parser.add_argument("--cli", action="store_true", help="Run interactive CLI")
    args = parser.parse_args()

    if args.cli:
        cli()
    else:
        serve()