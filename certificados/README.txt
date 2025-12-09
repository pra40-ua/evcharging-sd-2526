Certificado SSL generado para EV_Registry
==========================================
Fecha: 2025-12-09 18:44:40
Thumbprint: BD4668F7676DF00C754F3C5991E65823959D3C8B
VÃ¡lido hasta: 12/09/2026 18:44:40
Archivos:
  - Certificado: C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry_cert.pem
  - PFX (cert+key): C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry.pfx
  - Clave privada: C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry_key.pem (extraer con OpenSSL)

Para usar en EV_Registry:
  python ev_registry\EV_Registry.py --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem