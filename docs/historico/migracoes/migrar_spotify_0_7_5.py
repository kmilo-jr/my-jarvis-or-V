from pathlib import Path
import shutil, json
here=Path(__file__).resolve().parent
old=here.parent/'V_PROTOTYPE_0_7_5_SPOTIFY_HTTP_FIX'
if old.exists():
    for rel in ['config/spotify_token.json','config/spotify_client.json']:
        src=old/rel; dst=here/rel
        if src.exists():
            dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); print('Copiado:',rel)
    od=old/'config/default.json'; nd=here/'config/default.json'
    if od.exists() and nd.exists():
        try:
            a=json.loads(od.read_text(encoding='utf-8')); b=json.loads(nd.read_text(encoding='utf-8'))
            cid=(a.get('spotify_api') or {}).get('client_id')
            if cid:
                b.setdefault('spotify_api',{})['client_id']=cid
                nd.write_text(json.dumps(b,ensure_ascii=False,indent=2),encoding='utf-8'); print('Client ID migrado.')
        except Exception as exc: print('Aviso:',exc)
    print('Migracao concluida.')
else:
    print('Pasta 0.7.5 nao encontrada ao lado desta pasta.')
input('ENTER para sair...')
