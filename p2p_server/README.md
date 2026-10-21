# V P2P Signaling + Relay

Servidor mínimo do V Remote P2P. Ele faz somente:
- sinalização WebRTC (oferta/resposta);
- entrega da interface web do iPhone;
- relay de JSON quando o P2P direto falha.

O PC cria uma conexão **de saída** para este servidor, portanto não é necessário abrir porta no roteador de casa.

## Teste local

```bat
python -m pip install -r requirements.txt
python server.py
```

Abra `http://127.0.0.1:8890/health`.

## Publicação

Pode ser publicado como um Web Service Python em Render, Railway, Fly.io ou VPS. O processo precisa aceitar WebSocket.
Depois use a URL WebSocket em `config/default.json`, por exemplo:

`wss://SEU-SERVIDOR.onrender.com/ws`
