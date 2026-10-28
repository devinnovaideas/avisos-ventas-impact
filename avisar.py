#!/usr/bin/env python3
# Revisa las ventas nuevas en Impact y manda un aviso al iPhone (app ntfy).
# Corre en GitHub Actions cada 30 min. Datos privados en Secrets: IMPACT_SID, IMPACT_TOKEN, NTFY_TOPIC y TELEGRAM_TOKEN.
# Además de ntfy, manda cada aviso por Telegram (el bot de Laura), porque en su iPhone las notificaciones de ntfy dejaron de salir.
# El chat se descubre solo: el PRIMERO que le escriba /start al bot (Laura) queda guardado en chats.json; después ya no se agregan otros.
import base64, json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

SID, TOKEN, TOPIC = os.environ["IMPACT_SID"], os.environ["IMPACT_TOKEN"], os.environ["NTFY_TOPIC"]
TG = os.environ.get("TELEGRAM_TOKEN", "")
CHATS = "chats.json"
VISTOS = "vistos.json"

def avisar(titulo, texto, tags="moneybag", prioridad="urgent"):
    p = {"title": titulo, "tags": tags, "priority": prioridad,
         "click": "https://app.impact.com/secure/mediapartner/report/viewReport.report?handle=partner_performance_by_program"}
    q = urllib.parse.urlencode(p)
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}", data=texto.encode(), method="POST"), timeout=30).read()
    for chat in chats_telegram():
        datos = urllib.parse.urlencode({"chat_id": chat, "text": f"💰 {titulo}\n{texto}"}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG}/sendMessage", data=datos, timeout=30).read()

def chats_telegram():
    if not TG:
        return []
    if os.path.exists(CHATS):
        return json.load(open(CHATS))
    nuevos = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{TG}/getUpdates", timeout=30)).get("result", [])
    privados = [str(u["message"]["chat"]["id"]) for u in nuevos if u.get("message", {}).get("chat", {}).get("type") == "private"]
    if not privados:
        return []
    json.dump(privados[:1], open(CHATS, "w"))
    return privados[:1]

if "--prueba" in sys.argv:
    avisar("Prueba desde la nube", "Tu revisor de ventas ya funciona las 24 horas ☁️💰", "tada")
    sys.exit()

ahora = datetime.now(timezone.utc)
q = urllib.parse.urlencode({"ActionDateStart": (ahora - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "ActionDateEnd": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "PageSize": 200})
auth = base64.b64encode(f"{SID}:{TOKEN}".encode()).decode()
req = urllib.request.Request(f"https://api.impact.com/Mediapartners/{SID}/Actions?{q}",
                             headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
acciones = json.load(urllib.request.urlopen(req, timeout=60)).get("Actions", [])

datos = json.load(open(VISTOS)) if os.path.exists(VISTOS) else {"ids": [], "revisado": ""}
vistos = set(datos["ids"])
for a in acciones:
    if a["Id"] in vistos:
        continue
    comision = float(a.get("Payout") or 0)
    marca = a.get("CampaignName", "Impact")
    avisar(f"Nueva venta: {marca}" if comision else f"Nuevo registro: {marca}",
           f"Ganaste {comision:.2f} {a.get('Currency', 'USD')} (venta de {float(a.get('Amount') or 0):.2f}). ¡Felicidades! 🎉")
# Se guarda la fecha del día para que GitHub vea actividad y no apague el revisor
json.dump({"ids": sorted(vistos | {a["Id"] for a in acciones}), "revisado": f"{ahora:%Y-%m-%d}"}, open(VISTOS, "w"), indent=1)
print(f"{ahora:%Y-%m-%d %H:%M} · {len(acciones)} acciones en 3 días")
