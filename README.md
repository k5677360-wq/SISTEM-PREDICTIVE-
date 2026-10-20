# Respaldo recuperable del predictivo

Respaldo del 20 de octubre de 2026. Los archivos están **cifrados** en Releases.
Las credenciales, bases de datos y código privado no se publican en texto plano.
La clave RECOVERY.key se entrega aparte y NO está en GitHub. Consérvela fuera del servidor.

Incluye código, configuraciones, interfaz CRM, telefonía manual, TURN, autenticación,
predictivo técnico, exportaciones MariaDB/PostgreSQL, configuraciones Asterisk activas,
certificados TLS, identidad del puente y las imágenes Docker indicadas en el manifiesto.
Los archivos application-files incluyen fuentes, Dockerfiles y archivos de despliegue.

Excluye grabaciones de llamadas, volúmenes de audio grabado, registros históricos
de Asterisk, cachés, node_modules y metadatos .git. Los sonidos de sistema se conservan.
Los metadatos de grabaciones en las bases de datos se conservan; sus audios no.

## Recuperación

1. Descargar TODOS los adjuntos de la release y SHA256SUMS. Ejecutar `sha256sum -c SHA256SUMS`.
2. En un servidor AISLADO, descifrar cada archivo:
   `gpg --batch --pinentry-mode loopback --passphrase-file /ruta/RECOVERY.key --output core.tar --decrypt core.tar.gpg`
   Repetir para cada imagen, utilizando como salida su nombre sin `.gpg`.
3. Extraer core.tar en un directorio privado vacío. Verificar `private/SHA256SUMS`
   desde el directorio private. Consultar containers.json, image-map.json y networks.json.
4. Cargar las imágenes con `docker load -i imagen.tar.gz`. Restituir sus etiquetas
   originales usando image-map.json (`docker tag sha256:ID etiqueta`).
5. Extraer application-files.tar.gz bajo /home/deploy del servidor de recuperación.
   Restituir TLS y la identidad del puente con permisos privados, según el inventario.
   Restaurar los directorios Asterisk activos en sus destinos documentados.
6. Crear redes y volúmenes indicados en el inventario y usar los compose incluidos.
   Iniciar SOLO MariaDB y PostgreSQL, sin puertos públicos y sin servicios de marcación.
   Importar mariadb.sql con el cliente MariaDB y postgres.sql con psql como administrador.
   Usar las mismas versiones de imágenes, revisar roles existentes y errores de importación.
7. Antes de iniciar APIs/motor, establecer motor_paused=1 en la tabla de configuración
   que usa motor.js. Confirmar la tabla/columnas en el código restaurado.
   NO iniciar campañas automáticamente.
8. Revisar IP pública, DNS, TLS, firewall, redes, credenciales y autorización del proveedor
   Gino para la IP de recuperación. Las autorizaciones externas no se restauran desde Git.
9. Validar login, salas independientes, llamadas manuales, audio bidireccional,
   AMD, derivación, tipificación y grabaciones nuevas con números de prueba autorizados.
   Solo entonces habilitar tráfico con autorización del responsable.

## Límites de la copia

Exportación online sin bloquear tablas ni detener servicios. InnoDB usa snapshot;
VICIdial contiene MyISAM/MEMORY, por lo que no se garantiza una instantánea transaccional
común entre todas las tablas ni entre MariaDB y PostgreSQL. Había cero llamadas en la
comprobación inicial. No es una imagen completa del sistema operativo.
La integridad criptográfica/descifrado no equivale a una prueba operativa integral.
Consultar VALIDACION.md para las comprobaciones efectivamente realizadas.
