-- 📌 Qué hay ahora --

✅ EV_Central (~95%)
	- Servidor TCP estable que recibe conexiones de monitores.
	- Soporta registro/autenticación de CPs.
	- Recibe notificaciones de avería (AVR).
	- Falta: integrar Kafka y MySQL, y añadir la lógica de negocio de sesiones (START/STOP, tickets, etc.).

✅ EV_CP_E (Engine) (~90%)

	- Servidor TCP que escucha al Monitor.
	- Responde a health checks (HCK → HCK_RESP OK/KO).
	- Simula estados del motor (OK/KO).
	- Acepta solo una conexión (el Monitor).
	- Bien alineado con la práctica V2: ya no se conecta a Central, solo al Monitor.

✅ EV_CP_M (Monitor) (~95%)
	- Cliente que conecta tanto a Central como a Engine.
	- Envia health checks cada 1s.
	- Detecta fallos (KO, timeout, desconexión).
	- Notifica a Central con AVR#CPID#motivo.
	- Tiene reconexión automática con el Engine.
	- Es el responsable de autenticar y reportar al Central, justo como decía la V2.

🔄 EV_Driver (~5%)
	- Sigue siendo un placeholder (estructura básica).
	- Aún no puede pedir recargas ni recibir tickets.

🔄 ev_common (~10%)
	- Solo con utilidades mínimas (build_message).
	- Falta mover aquí toda la lógica de framing/protocolo común para que no esté duplicada.
	

-- 🚀 Próximos pasos --
	
🔹 Paso 1 — Consolidar ev_common/
	- Extraer:
		framing/parsing (STX, ETX, LRC).
		códigos de mensajes (REG, AUTH, HCK, HCK_RESP, AVR, START, STOP, STATUS, TELEM, TICKET).
		utilidades de red (send_frame, recv_frame, timeouts).
	- Objetivo: Central, Monitor y Engine usen el mismo código base.

🔹 Paso 2 — EV_Driver (cliente/conductor)
	- Implementar CLI con --driver-id y --requests-file.
	- Funcionalidades mínimas:
		1. Enviar REQ#driverId#cpId a Central.
		2. Recibir respuesta: AUTHORIZED o DENIED.
		3. Mostrar estados paso a paso en consola.
		4. Esperar ticket final: TICKET#sessionId#kwh#euros#dur.
	- Objetivo: que un usuario pueda pedir recarga y ver todo el flujo.

🔹 Paso 3 — Lógica de negocio en Central
	- Validar disponibilidad del CP antes de autorizar.
	- Enviar orden START al Monitor → Engine.
	- Recibir STOP y generar TICKET para el Driver.
	- Rechazar peticiones si CP está ocupado o averiado.
	- Objetivo: cerrar el ciclo completo de recarga.

🔹 Paso 4 — Telemetría
	- Engine genera datos de consumo cada 1s durante una sesión.
	- Enviarlos:
		Opción rápida: sockets → Central.
		Opción final: vía Kafka (cp.telemetry).
	- Objetivo: que Central y Driver puedan ver el consumo en tiempo real.

🔹 Paso 5 — Kafka
	- Integrar productores/consumidores:
		Engine → Kafka → Central (cp.telemetry).
		Monitor/Engine → Kafka → Central (cp.events).
	- Opcional: Central → Kafka → CP (central.commands).
	- Objetivo: separar control síncrono (sockets) de datos asíncronos (Kafka).

🔹 Paso 6 — Persistencia (MySQL)
	- Tablas mínimas:
		cps (estado, ubicación, precio).
		drivers.
		sessions (histórico de recargas).
		events (averías, recuperaciones, etc.).
	- Objetivo: guardar auditoría y que Central pueda reconstruir estado al reiniciar.
