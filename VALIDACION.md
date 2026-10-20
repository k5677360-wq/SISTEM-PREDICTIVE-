# Validación del respaldo — 20 de octubre de 2026

- 21 adjuntos en GitHub: núcleo cifrado, 19 imágenes Docker cifradas y SHA256SUMS.
- Se comparó SHA-256 y tamaño de TODOS los adjuntos con GitHub.
- Se descifraron localmente los 20 archivos cifrados y coincidieron con los originales.
- Se verificaron los 11 archivos del manifiesto interno del núcleo.
- PostgreSQL restaurado en contenedor local temporal SIN RED: 50 tablas públicas, cero errores de importación.
- MariaDB restaurado desde la imagen respaldada en contenedor local temporal SIN RED:
  14 tablas predictive_session, 349 tablas/vistas vicidial y 8.205 registros predictive_calls.
  Se verificó acceso con las credenciales originales tras FLUSH PRIVILEGES.
- Los contenedores temporales de prueba fueron retirados.
- No se reinició ningún servicio de producción ni se borraron datos de producción.
- La exportación inicial conjunta de imágenes agotó temporalmente el espacio; se canceló,
  Docker liberó sus temporales y se completó mediante exportaciones individuales con margen previo.
  Comprobación final: 3,2 GB disponibles; MariaDB healthy; servicios sin reinicios.
- No se dejó un archivo de respaldo en el servidor de producción. GitHub es el destino definitivo.

## Límites

No se probó una recuperación integral de telefonía con tráfico real. Las IP/DNS,
permisos del proveedor, firewall y operación de campañas deben validarse antes de habilitar tráfico.
Las tablas MyISAM/MEMORY no tienen snapshot transaccional común; se exportaron online sin bloqueo.
Las grabaciones de clientes y los logs históricos voluminosos no forman parte del respaldo.
Los archivos funcionales, sonidos de sistema, datos y configuración están cifrados.
