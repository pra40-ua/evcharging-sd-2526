Certificado SSL generado para EV_Registry
==========================================
Fecha: 2025-12-04 20:57:13
Thumbprint: 6394BA1CCFFE63F2DFBC122FF1B78332F751D47C
VÃ¡lido hasta: 12/04/2026 20:57:13
Archivos:
  - Certificado: C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry_cert.pem
  - PFX (cert+key): C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry.pfx
  - Clave privada: C:\Users\panpatuhambre\Desktop\curso 25-26\SD\prac1ConRomero\evcharging-sd-2526\certificados\registry_key.pem (extraer con OpenSSL)

Para usar en EV_Registry:
  python ev_registry\EV_Registry.py --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem