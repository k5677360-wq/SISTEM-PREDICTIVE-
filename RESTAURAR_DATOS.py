"""Usar SOLO con el destino NUEVO creado por GENERAR_RECUPERACION.py.
python3 RESTAURAR_DATOS.py /ruta/destino
Inicia solo las dos bases; importa datos y deja motor_paused=1.
"""
import pathlib,json,subprocess,sys,os,time,tarfile
dest=pathlib.Path(sys.argv[1]).resolve()
info=json.loads((dest/'restore-inputs.json').read_text()); project=info['project']
core=pathlib.Path(info['core']); extra=pathlib.Path(info['extra'])
containers=json.loads((dest/'original-containers.json').read_text())
volumes=json.loads((dest/'volume-map.json').read_text())
compose=json.loads((dest/'compose.json').read_text())
if (dest/'DATOS_RESTAURADOS').exists(): raise SystemExit('Datos ya restaurados; no se sobreescriben')
names={c['Name'].lstrip('/'):c for c in containers}
helper=compose['services']['crm-campana-maqueta']['image']
seeds={
 ('gemini-webphone-asterisk','/var/lib/asterisk'):(core/'runtime-manual-asterisk.tar.gz','var/lib/asterisk'),
 ('gemini-webphone-asterisk','/var/spool/asterisk'):(extra/'manual-spool.tar.gz','var/spool/asterisk'),
 ('grafana','/var/lib/grafana'):(extra/'grafana-data.tar.gz','var/lib/grafana'),
 ('gemini-turn','/var/lib/coturn'):(extra/'manual-turn-data.tar.gz','var/lib/coturn'),
 ('vicidial-predictivo-turn-1','/var/lib/coturn'):(extra/'predictive-turn-data.tar.gz','var/lib/coturn')}
for c in containers:
    for m in c.get('Mounts',[]):
        if m['Type']!='volume': continue
        name=volumes[m['Name']]
        assert name.startswith(project+'-v')
        # Refuse existing volumes on the first pass to prevent overwriting unrelated data.
        old=subprocess.run(['docker','volume','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        marker=dest/('created-'+name)
        if old.returncode==0 and not marker.exists(): raise SystemExit('Volumen preexistente: '+name)
        if not marker.exists():
            subprocess.run(['docker','volume','create',name],check=True,stdout=subprocess.DEVNULL)
            marker.touch()
        pair=(c['Name'].lstrip('/'),m['Destination'])
        if pair not in seeds: continue
        archive,path=seeds[pair]
        with tarfile.open(archive) as t:
            member=t.getmember(path); uid,gid=member.uid,member.gid
        subprocess.run(['docker','run','--rm','--network','none','--user','0',
          '--mount','type=volume,src='+name+',dst=/restore',
          '--mount','type=bind,src='+str(archive)+',dst=/archive,readonly',
          '--entrypoint','/bin/sh',helper,'-c',
          'tar -xzpf /archive -C /restore --strip-components='+str(len(path.split('/')))+' '+path+' && chown '+str(uid)+':'+str(gid)+' /restore'],check=True)
cmd=['docker','compose','-f',str(dest/'compose.json')]
subprocess.run(cmd+['--profile','data','up','-d'],check=True,stdout=subprocess.DEVNULL)
mysql=project+'-vicidial-predictivo-mariadb-1'; pg=project+'-asistencias-api-db-1'
source_env=dict(x.split('=',1) for x in names['vicidial-predictivo-mariadb-1']['Config']['Env'] if '=' in x)
env={**os.environ,'MYSQL_PWD':source_env['MARIADB_ROOT_PASSWORD']}
for _ in range(90):
    r=subprocess.run(['docker','exec','-e','MYSQL_PWD',mysql,'mariadb','--protocol=tcp','-h127.0.0.1','-uroot','-N','-e','SELECT 1'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if r.returncode==0: break
    time.sleep(1)
else: raise SystemExit('MariaDB no disponible')
with open(core/'mariadb.sql','rb') as src,open(dest/'mysql-restore.log','wb') as log:
    subprocess.run(['docker','exec','-i','-e','MYSQL_PWD',mysql,'mariadb','-uroot','--binary-mode=1'],stdin=src,stdout=log,stderr=log,env=env,check=True)
mapping=json.loads((dest/'address-map.json').read_text())
sql=''
for old,new in mapping.items():
    import ipaddress
    ipaddress.IPv4Address(old); ipaddress.IPv4Address(new)
    for table in ('global_priv','db','tables_priv','columns_priv','procs_priv','proxies_priv'):
        sql+="UPDATE mysql."+table+" SET Host='"+new+"' WHERE Host='"+old+"';"
    for table in ('servers','phones','conferences','vicidial_conferences','vicidial_confbridges',
                  'vicidial_server_carriers','vicidial_server_trunks','vicidial_stations',
                  'vicidial_inbound_dids','inbound_numbers','vicidial_remote_agents',
                  'vicidial_process_triggers','server_updater'):
        sql+="UPDATE vicidial."+table+" SET server_ip='"+new+"' WHERE server_ip='"+old+"';"
sql+="FLUSH PRIVILEGES; INSERT INTO predictive_session.predictive_control(k,v,updated_by) VALUES('motor_paused','1','disaster-recovery') ON DUPLICATE KEY UPDATE v='1',updated_by='disaster-recovery';"
sql+="UPDATE predictive_session.predictive_advisor_slots SET current_state='disconnected';"
for table in ('vicidial_live_agents','vicidial_session_data','web_client_sessions','live_channels',
              'live_sip_channels','vicidial_auto_calls','parked_channels','recording_live','live_inbound','vicidial_manager'):
    sql+="DELETE FROM vicidial."+table+";"
subprocess.run(['docker','exec','-e','MYSQL_PWD',mysql,'mariadb','-uroot','-e',sql],env=env,check=True)
for _ in range(90):
    r=subprocess.run(['docker','exec',pg,'pg_isready','-h127.0.0.1','-U','recovery_admin'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if r.returncode==0: break
    time.sleep(1)
else: raise SystemExit('PostgreSQL no disponible')
with open(core/'postgres.sql','rb') as src,open(dest/'pg-restore.log','wb') as log:
    subprocess.run(['docker','exec','-i',pg,'psql','-U','recovery_admin','-d','postgres','-v','ON_ERROR_STOP=1'],stdin=src,stdout=log,stderr=log,check=True)
(dest/'DATOS_RESTAURADOS').write_text('Bases restauradas. motor_paused=1. No se han iniciado aplicaciones ni telefonia.\n')
print('DATOS RESTAURADOS. Marcador pausado en la copia.')
