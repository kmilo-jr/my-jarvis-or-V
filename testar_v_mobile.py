from __future__ import annotations
from core.tool_router import ToolRouter
import mobile_bridge
from windows_notification_reader import WindowsPhoneNotificationReader

print('=== V MOBILE DIAGNOSTICO ===')
r = ToolRouter()
for text in (
    'V, coloque um alarme para 06:30',
    'V, me lembre amanhã às 14h de estudar',
):
    d = r.route(text, [])
    print(text)
    print(' ->', d.mode, [x.name for x in d.calls], d.reason)
reader = WindowsPhoneNotificationReader(['whatsapp', 'instagram'])
print('Banco de notificacoes Windows:', 'OK' if reader.available else 'NAO ENCONTRADO')
print('Status mobile:', mobile_bridge.notification_backend_status())
print('Acoes pendentes:', len(mobile_bridge.pending_actions()))
print('============================')
