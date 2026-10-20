# SISTEM PREDICTIVE — Recuperación en otro servidor

Paquete cifrado del 20/10/2026: código, bases, configuración activa, certificados,
22 imágenes Docker para 23 servicios y herramientas para reconstruir redes y volúmenes.
**Sin grabaciones de llamadas.**

## Descarga y procedimiento

[Descargar los archivos de la release](../../releases/tag/backup-20261020).
El respaldo está en los adjuntos de Releases, no en el ZIP automático Source code.
Usar core.tar.gpg, los 19 image-*.gpg, dr-supplement-v2.tar.gpg,
recovery-tools.zip y DR-SHA256SUMS. La clave RECOVERY.key se guarda aparte.

**[Instrucciones completas para otro servidor](RECUPERACION.md)**

**[Pruebas de recuperación realizadas](VALIDACION-DR.md)**

Se ejecutó una reconstrucción desde cero en redes aisladas: 23 servicios arrancados,
bases restauradas, HTTP/HTTPS correctos y certificado validado. El motor quedó pausado.
Al migrar deben actualizarse IP/DNS, firewall y autorización del proveedor.
Las llamadas reales/audio desde una IP nueva requieren una prueba posterior.
No es una imagen del sistema operativo ni incluye aplicaciones independientes ajenas al predictivo.
