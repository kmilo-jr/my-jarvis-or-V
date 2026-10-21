import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import Mock

import requests

from brain.service import BrainService


class StreamLatencyTests(unittest.TestCase):
    def test_first_sentence_arrives_before_server_finishes(self):
        spoken = threading.Event()
        delivered_early = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                def send(text, finish=None):
                    candidate = {"content": {"parts": [{"text": text}]}}
                    if finish:
                        candidate["finishReason"] = finish
                    payload = json.dumps({"candidates": [candidate]}, ensure_ascii=False)
                    self.wfile.write(("data: " + payload + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                send("Olá, estou aqui. ")
                delivered_early.append(spoken.wait(2))
                send("Vamos começar!", "STOP")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        brain = BrainService.__new__(BrainService)
        brain.config = {}
        brain.gemini_chat_model = "test"
        brain.gemini_fallback_model = ""
        brain.gemini_base_url = "http://127.0.0.1:" + str(server.server_port)
        brain.gemini_key = "local-test"
        brain.gemini_chat_timeout = 4
        brain.should_use_live_search = lambda _: False
        brain._gemini_allowed = lambda: True
        brain._identity_prompt = lambda: ""
        brain._memory_prompt = lambda query='': ""
        brain._gemini_payload = lambda *args, **kwargs: {}
        brain.chat = Mock(return_value="fallback")
        brain._gemini_session = requests.Session()
        brain._gemini_session.trust_env = False
        chunks = []
        def receive(text):
            chunks.append(text)
            spoken.set()
        try:
            result = brain.chat_stream("Olá", [], chunk_callback=receive)
            self.assertEqual(delivered_early, [True])
            self.assertEqual(chunks, ["Olá, estou aqui.", "Vamos começar!"])
            self.assertEqual(result, "Olá, estou aqui. Vamos começar!")
            brain.chat.assert_not_called()
        finally:
            brain._gemini_session.close()
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == "__main__":
    unittest.main()
