Certificado SSL generado para EV_Registry
==========================================
Fecha: 2025-12-09 19:28:28
Thumbprint: 2751569EDF6776689AD56D90B246052D34D31E4F
VÃ¡lido hasta: 12/09/2026 19:28:28
Archivos:
  - Certificado: C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry_cert.pem
  - PFX (cert+key): C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry.pfx
  - Clave privada: C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry_key.pem (extraer con OpenSSL)

Para usar en EV_Registry:
  python ev_registry\EV_Registry.py --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem