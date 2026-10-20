# Recuperar el predictivo en otro servidor

Este paquete reconstruye el sistema predictivo y sus dependencias, no todo el
servidor ni las otras aplicaciones independientes que compartían la máquina.
Contiene 22 imágenes para 23 servicios, código desplegado, bases de datos,
configuración activa, certificados, identidad del puente, redes y volúmenes.
Las grabaciones y los logs históricos voluminosos están excluidos.

**El ZIP automático “Source code” de la release antigua NO es el respaldo.**
Descargar los adjuntos indicados debajo y las herramientas de recuperación.
La clave `RECOVERY.key` se conserva aparte; no está en GitHub.

## 1. Preparar el destino

- Servidor Linux x86_64 NUEVO, con recursos al menos equivalentes al original
  (4 vCPU, 16 GB RAM) y espacio suficiente para imágenes, extracción y crecimiento.
  Reservar al menos 40 GB libres para la recuperación sin grabaciones.
- Docker Engine y Docker Compose, Python 3.12+, GnuPG y GNU tar.
- Ejecutar la extracción/generación como root para conservar UID/GID originales,
  o con el mismo UID de despliegue original. Proteger el directorio con modo 700.
- No ejecutar el procedimiento sobre el servidor activo ni sobre volúmenes existentes.
- El inventario de sistema operativo, puertos, límites y servicios está cifrado en
  el complemento. `/etc/fstab` y las interfaces del servidor viejo son referencias:
  no copiarlos sobre los discos o interfaces del nuevo servidor.
- No se pudo leer el archivo root-only de reglas UFW. Reconstruir el firewall
  permitiendo únicamente SSH autorizado, los puertos publicados de `compose.json`
  y los puertos TURN que figuran en la configuración recuperada. No exponer las BD.

## 2. Descargar y verificar

Desde la release `backup-20261020`:

- `core.tar.gpg`
- Los 19 archivos `image-*.tar.gz.gpg`
- `dr-supplement-v2.tar.gpg` (complemento FINAL, contiene otras 3 imágenes)
- `recovery-tools.zip` y `DR-SHA256SUMS`

En el directorio de descarga:

```bash
sha256sum -c DR-SHA256SUMS
unzip recovery-tools.zip
```

No usar el complemento preliminar `dr-supplement.tar.gpg` si todavía aparece.
Los originales se conservan cifrados. Descifrar con la MISMA clave que el respaldo inicial:

```bash
gpg --batch --pinentry-mode loopback --passphrase-file /ruta/RECOVERY.key \
  --output core.tar --decrypt core.tar.gpg
gpg --batch --pinentry-mode loopback --passphrase-file /ruta/RECOVERY.key \
  --output dr-supplement-v2.tar --decrypt dr-supplement-v2.tar.gpg
tar -xpf core.tar
tar -xpf dr-supplement-v2.tar
cd private
sha256sum -c SHA256SUMS
cd ../supplement
sha256sum -c SHA256SUMS
cd ..
for f in image-*.tar.gz.gpg; do
  gpg --batch --pinentry-mode loopback --passphrase-file /ruta/RECOVERY.key \
    --output "${f%.gpg}" --decrypt "$f" || break
done
```

## 3. Cargar las imágenes

```bash
python3 RESTAURAR_IMAGENES.py "$PWD" "$PWD/private" "$PWD/supplement"
```

Produce `recovery-overrides/loaded-images.json`. No inicia contenedores.
Resuelve el cambio de identificadores entre almacenes Docker clásicos/containerd.
No necesita reconstruir imágenes ni descargar dependencias npm.

## 4. Ensayo aislado, recomendado primero

```bash
python3 GENERAR_RECUPERACION.py \
  --core "$PWD/private" --extra "$PWD/supplement" \
  --images "$PWD/recovery-overrides/loaded-images.json" \
  --dest /srv/predictivo-ensayo --project predictivo-ensayo
python3 RESTAURAR_DATOS.py /srv/predictivo-ensayo
docker compose -f /srv/predictivo-ensayo/compose.json --profile '*' up -d
python3 VALIDAR_RECUPERACION.py /srv/predictivo-ensayo
```

Genera redes internas nuevas y adapta IP internas, permisos de MySQL, configuración
de VICIdial y referencias IP del código realmente desplegado. No publica puertos
ni permite llamar a clientes. En este modo, TURN escucha en su interfaz aislada,
no en la IP pública antigua.

La restauración:

- Importa MariaDB y PostgreSQL y conserva campañas, bases, ventas e historial.
- Restaura volúmenes funcionales y crea vacíos los de grabaciones excluidas.
- Deja `motor_paused=1`.
- Invalida presencia/sesiones y colas transitorias del servidor caído. Los asesores
  deben volver a iniciar sesión. No se borran ventas, contactos ni historial.
- No modifica los dumps originales: los estados previos siguen disponibles allí.

Los servicios externos —proveedor telefónico, puente remoto y almacenamiento—
no estarán disponibles en este ensayo sin salida a internet. No confundir esta
restricción deliberada con una validación de llamadas reales.

## 5. Preparar el despliegue real en el servidor NUEVO

Usar otro destino y proyecto, nunca reutilizar los volúmenes del ensayo.
Sustituir `IP_NUEVA` por la IPv4 pública realmente asignada al servidor:

```bash
python3 GENERAR_RECUPERACION.py \
  --core "$PWD/private" --extra "$PWD/supplement" \
  --images "$PWD/recovery-overrides/loaded-images.json" \
  --dest /srv/predictivo-recuperado --project predictivo-recuperado \
  --live --public-ip IP_NUEVA
docker compose -f /srv/predictivo-recuperado/compose.json --profile '*' config --quiet
python3 RESTAURAR_DATOS.py /srv/predictivo-recuperado
```

Este modo conserva los puertos, subredes y direcciones internas originales;
adapta la IP pública en archivos y variables. Si hay redes existentes que se
solapan, usar un servidor limpio o planificar el cambio antes de iniciar.
Si la IP pública está detrás de NAT y no existe en una interfaz local, ajustar
los listeners TURN a la IP local; mantener la pública como dirección anunciada.

Antes de levantar aplicaciones:

1. Asegurar que el servidor anterior no siga marcando. Evitar dos motores activos.
2. Actualizar DNS del CRM y comprobar TLS. Los certificados y renovación están
   respaldados; instalar/configurar el mecanismo de renovación en el host nuevo.
3. Pedir a Gino autorización de la IP nueva; conservar ruta/prefijo/DID del respaldo.
4. Verificar conectividad y permisos del puente remoto y almacenamiento externo.
   Esas cuentas y autorizaciones externas no pueden restaurarse desde Docker.
5. Configurar firewall y revisar todos los listeners/puertos publicados.

Después:

```bash
docker compose -f /srv/predictivo-recuperado/compose.json --profile '*' up -d
```

El marcador permanece pausado. Validar login y salas independientes, teléfono
manual y predictivo, audio bidireccional, AMD, derivación, tipificación, avisos y
grabación nueva con números de prueba autorizados. Solo entonces reanudar desde
la interfaz técnica con un asesor disponible.

## Límites y continuidad

- La copia de bases es del 20/10/2026; no incluye cambios posteriores.
- La exportación online de MyISAM/MEMORY no garantiza una instantánea transaccional
  común entre todas las tablas ni entre PostgreSQL y MariaDB.
- No es una imagen completa del sistema operativo ni de aplicaciones ajenas al predictivo.
- Las grabaciones anteriores no pueden recuperarse desde este paquete.
- Una prueba aislada de arranque no demuestra audio real con el proveedor desde
  una IP nueva. Esa comprobación se realiza después de la autorización de red.
- Conservar la clave fuera del servidor y renovar el respaldo cuando cambien datos
  o versiones. No eliminar producción basándose solo en que existe esta release.
