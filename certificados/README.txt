Certificado SSL generado para EV_Registry
==========================================
Fecha: 2025-12-01 21:24:40
Thumbprint: 6FCBC68C2BBE6A33CA839CD6148436AF176AEDD3
VÃ¡lido hasta: 12/01/2026 21:24:40
Archivos:
  - Certificado: C:\Users\luisi\Documents\sd\evcharging-sd-2526\certificados\registry_cert.pem
  - PFX (cert+key): C:\Users\luisi\Documents\sd\evcharging-sd-2526\certificados\registry.pfx
  - Clave privada: C:\Users\luisi\Documents\sd\evcharging-sd-2526\certificados\registry_key.pem (extraer con OpenSSL)

Para usar en EV_Registry:
  python ev_registry\EV_Registry.py --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem