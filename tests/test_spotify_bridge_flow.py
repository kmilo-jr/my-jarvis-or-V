"""Regressao do Spotify Bridge: protocolo por header, lease e ciclo do comando.

Nao precisa de Spotify aberto: o teste faz o papel da extensao (poll + result).
Skip quando a porta do bridge ja esta em uso (V rodando) para nao brigar com ele.
"""
import json
import os
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import spotify_bridge as bridge

PORTA = 8766
BASE = f"http://127.0.0.1:{PORTA}"


def _porta_livre(porta: int = PORTA) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", porta)) != 0


@unittest.skipUnless(_porta_livre(), "porta 8766 em uso (V/bridge ja rodando)")
class SpotifyBridgeFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token = bridge.ensure_token()
        if not bridge.start_bridge_background():
            raise unittest.SkipTest("bridge nao iniciou")

    def _http(self, path, method="GET", body=None, token=True):
        dados = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(BASE + path, data=dados, method=method)
        if dados is not None:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("X-Bridge-Token", self.token)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_health_e_publico_e_usa_dpapi(self):
        status, corpo = self._http("/health", token=False)
        self.assertEqual(status, 200)
        dados = json.loads(corpo)
        self.assertTrue(dados["ok"])
        self.assertEqual(dados["token_storage"], "dpapi")

    def test_next_sem_token_e_bloqueado(self):
        self.assertEqual(self._http("/next", token=False)[0], 403)

    def test_token_na_query_nao_vale_para_comando(self):
        # Protocolo antigo: a extensao mandava o token na query. Agora so o
        # handshake aceita isso; /next precisa recusar.
        status, _ = self._http(f"/next?token={self.token}", token=False)
        self.assertEqual(status, 403)

    def test_ciclo_completo_com_lease(self):
        pedido = {}

        def cliente():
            pedido["resposta"] = self._http(
                "/command", "POST", {"action": "status", "timeout": 5}, token=True
            )

        thread = threading.Thread(target=cliente)
        thread.start()

        cmd = None
        limite = time.time() + 4.0
        while time.time() < limite:
            status, corpo = self._http("/next")
            if status == 200:
                cmd = json.loads(corpo)
                break
            self.assertIn(status, (204, 409), "poll inesperado do bridge")
            time.sleep(0.05)
        self.assertIsNotNone(cmd, "o bridge nao entregou o comando")
        self.assertEqual(cmd["action"], "status")

        # Enquanto o comando esta em andamento, outro poll leva 409 (nao rouba).
        self.assertEqual(self._http("/next")[0], 409)

        status, corpo = self._http("/result", "POST", {
            "id": cmd["id"], "ok": True, "action": "status",
            "status": {"playing": False, "title": "teste"},
        })
        self.assertEqual(status, 200)
        thread.join(timeout=6)
        self.assertFalse(thread.is_alive(), "o /command nao respondeu apos o /result")
        status, corpo = pedido["resposta"]
        self.assertEqual(status, 200, corpo)
        self.assertTrue(json.loads(corpo)["ok"])

        # Depois do resultado a fila fica vazia (204), sem comando fantasma.
        self.assertEqual(self._http("/next")[0], 204)


if __name__ == "__main__":
    unittest.main()
