// V Spotify Bridge (extensao Spicetify).
// ATENCAO: este arquivo instalado CONTEM o token do bridge em texto — e o unico
// jeito de a extensao autenticar, pois JS rodando no Spotify nao tem acesso ao
// DPAPI do Windows. O configurador restringe o arquivo ao seu usuario, e o V
// guarda a copia protegida em config/spotify_bridge_token.dat. Se este arquivo
// vazar, rode configurar_spotify_bridge.bat para ROTACIONAR o token.
(function vSpotifyBridge() {
  const TOKEN = "__TOKEN__";
  const BASE = "http://127.0.0.1:8766";
  const POLL_MS = 220;

  // Identidade por instancia (varias janelas do Spotify nao compartilham o
  // mesmo cliente) e header obrigatorio: o token NAO vai mais na query string.
  const CLIENT = (() => {
    try {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    } catch (_) {}
    return "v-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  })();
  const HEADERS = {
    'X-Bridge-Token': TOKEN,
    'X-Bridge-Client': CLIENT
  };

  if (!window.Spicetify || !Spicetify.Player || !Spicetify.Platform) {
    setTimeout(vSpotifyBridge, 250);
    return;
  }

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  function status() {
    // Cada campo e lido de forma defensiva: em algumas versoes do Spicetify um
    // getter ausente/inicializando lancava excecao aqui, o que derrubava o
    // heartbeat E o POST /result (o comando nunca "voltava" para o V).
    const safe = (fn, fallback = null) => {
      try {
        const v = fn();
        return v === undefined ? fallback : v;
      } catch (_) {
        return fallback;
      }
    };
    const d = safe(() => Spicetify.Player.data, null);
    const track = safe(() => (d && (d.item || d.track)) || (Spicetify.Queue && Spicetify.Queue.track), null);
    let title = null, artist = null, uri = null;
    if (track) {
      uri = safe(() => track.uri, null);
      const m = safe(() => track.metadata, {}) || {};
      title = safe(() => m.title || m.name, null);
      artist = safe(() => m.artist_name || m.artist, null);
    }
    return {
      playing: !!safe(() => Spicetify.Player.isPlaying(), false),
      volume: Number(safe(() => Spicetify.Player.getVolume(), 0)),
      uri, title, artist,
      context_uri: safe(() => (d && (d.context_uri || (d.context && d.context.uri))) || null, null),
      position_ms: Number(safe(() => Spicetify.Player.getProgress(), 0)),
      duration_ms: Number(safe(() => Spicetify.Player.getDuration(), 0)),
      shuffle: !!safe(() => Spicetify.Player.getShuffle(), false)
    };
  }

  // Nunca deixa uma falha de leitura de estado impedir o resultado do comando.
  function safeStatus() {
    try {
      return status();
    } catch (e) {
      const erro = String((e && e.message) || e);
      try { console.error('[V Spotify Bridge] status falhou:', erro); } catch (_) {}
      return {error: erro};
    }
  }

  async function send(path, body) {
    const r = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: Object.assign({'Content-Type':'application/json'}, HEADERS),
      body: JSON.stringify(body)
    });
    return r;
  }

  async function execute(cmd) {
    const a = cmd.action, x = cmd.args || {};
    if (a === 'status') return;
    if (a === 'play_uri') {
      if (!x.uri || !String(x.uri).startsWith('spotify:')) throw new Error('URI Spotify invalida');
      await Spicetify.Player.playUri(String(x.uri));
      await sleep(450);
    } else if (a === 'next') {
      Spicetify.Player.next(); await sleep(400);
    } else if (a === 'previous') {
      Spicetify.Player.back(); await sleep(400);
    } else if (a === 'pause') {
      Spicetify.Player.pause(); await sleep(200);
    } else if (a === 'play') {
      Spicetify.Player.play(); await sleep(200);
    } else if (a === 'toggle') {
      Spicetify.Player.togglePlay(); await sleep(200);
    } else if (a === 'volume') {
      Spicetify.Player.setVolume(Math.max(0, Math.min(1, Number(x.level)))); await sleep(120);
    } else if (a === 'shuffle') {
      Spicetify.Player.setShuffle(!!x.enabled); await sleep(150);
    } else {
      throw new Error(`acao desconhecida: ${a}`);
    }
  }

  async function poll() {
    try {
      const r = await fetch(`${BASE}/next`, {cache:'no-store', headers: HEADERS});
      if (r.status === 200) {
        const cmd = await r.json();
        let result;
        try {
          await execute(cmd);
          result = {id:cmd.id, ok:true, action:cmd.action, status:safeStatus()};
        } catch (e) {
          result = {id:cmd.id, ok:false, action:cmd.action, error:String(e?.message || e), status:safeStatus()};
        }
        await send('/result', result);
      }
    } catch (e) {
      // Bridge may not be running yet. Retry silently.
    } finally {
      setTimeout(poll, POLL_MS);
    }
  }

  setInterval(() => {
    send('/heartbeat', {status:safeStatus()}).catch(()=>{});
  }, 3000);

  console.log('[V Spotify Bridge] online');
  try { Spicetify.showNotification?.('V Spotify Bridge online'); } catch (_) {}
  poll();
})();
