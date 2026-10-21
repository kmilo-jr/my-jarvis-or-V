(function vSpotifyBridge() {
  const TOKEN = "__TOKEN__";
  const BASE = "http://127.0.0.1:8766";
  const POLL_MS = 220;

  if (!window.Spicetify || !Spicetify.Player || !Spicetify.Platform) {
    setTimeout(vSpotifyBridge, 250);
    return;
  }

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  function status() {
    const d = Spicetify.Player.data;
    const track = (d && (d.item || d.track)) || (Spicetify.Queue && Spicetify.Queue.track) || null;
    let title = null, artist = null, uri = null;
    if (track) {
      uri = track.uri || null;
      const m = track.metadata || {};
      title = m.title || m.name || null;
      artist = m.artist_name || m.artist || null;
    }
    return {
      playing: !!Spicetify.Player.isPlaying(),
      volume: Number(Spicetify.Player.getVolume?.() ?? 0),
      uri, title, artist,
      context_uri: d?.context_uri || d?.context?.uri || null,
      position_ms: Number(Spicetify.Player.getProgress?.() ?? 0),
      duration_ms: Number(Spicetify.Player.getDuration?.() ?? 0),
      shuffle: !!Spicetify.Player.getShuffle?.()
    };
  }

  async function send(path, body) {
    const r = await fetch(`${BASE}${path}?token=${encodeURIComponent(TOKEN)}`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
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
      const r = await fetch(`${BASE}/next?token=${encodeURIComponent(TOKEN)}`, {cache:'no-store'});
      if (r.status === 200) {
        const cmd = await r.json();
        let result;
        try {
          await execute(cmd);
          result = {id:cmd.id, ok:true, action:cmd.action, status:status()};
        } catch (e) {
          result = {id:cmd.id, ok:false, action:cmd.action, error:String(e?.message || e), status:status()};
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
    send('/heartbeat', {status:status()}).catch(()=>{});
  }, 3000);

  console.log('[V Spotify Bridge] online');
  try { Spicetify.showNotification?.('V Spotify Bridge online'); } catch (_) {}
  poll();
})();
