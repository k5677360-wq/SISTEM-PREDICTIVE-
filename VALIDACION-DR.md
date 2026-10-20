# Prueba final de recuperación

Ejecutada desde cero con los scripts publicados y archivos descargados de GitHub.

- 23 servicios arrancados, con 22 imágenes recuperadas.
- 12 volúmenes reconstruidos y 9 redes internas de prueba.
- Sin puertos publicados ni salida de las redes de prueba a clientes.
- MariaDB y PostgreSQL restaurados; 8.205 registros de llamadas conservados.
- Marcador pausado y presencia de asesores reiniciada exclusivamente en la copia.
- HTTP 200 en API, interfaz y web nativa de VICIdial.
- HTTPS 200 a través de Nginx, con validación correcta del certificado.
- nginx -t correcto.
- Adaptación de IP internas, scripts desplegados, permisos y configuración de VICIdial.

La prueba NO valida llamadas reales, audio RTP ni autorización de Gino para una IP nueva.
Tampoco convierte la exportación online MyISAM en una instantánea transaccional.
El procedimiento y las dependencias externas están en RECUPERACION.md.
