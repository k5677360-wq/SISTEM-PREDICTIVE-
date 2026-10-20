"""Genera un despliegue completo; NO inicia servicios.
python3 GENERAR_RECUPERACION.py --core /ruta/private --extra /ruta/supplement \
  --images /ruta/local-images.json --dest /ruta/nueva --project recuperacion01
Por defecto: redes internas, sin puertos publicados, sin reinicio automatico.
--live conserva puertos/subredes originales: usar SOLO en servidor nuevo aislado.
"""
import argparse,pathlib,json,os,subprocess,hashlib,re,ipaddress,base64
a=argparse.ArgumentParser()
for k in ('core','extra','images','dest','project'): a.add_argument('--'+k,required=True)
a.add_argument('--live',action='store_true')
a.add_argument('--public-ip')
args=a.parse_args(); os.umask(0o077)
if args.live and not args.public_ip: raise SystemExit('--live requiere --public-ip del servidor NUEVO')
if args.public_ip: ipaddress.IPv4Address(args.public_ip)
core=pathlib.Path(args.core).resolve(); extra=pathlib.Path(args.extra).resolve()
dest=pathlib.Path(args.dest).resolve()
if dest.exists(): raise SystemExit('El destino debe ser nuevo y vacio')
if not re.fullmatch('[a-z][a-z0-9-]{3,30}',args.project): raise SystemExit('Nombre de proyecto invalido')
dest.mkdir(parents=True)
host=dest/'host'; (host/'home/deploy').mkdir(parents=True)
def unpack(archive,target):
    target.mkdir(parents=True,exist_ok=True)
    subprocess.run(['tar','-xzpf',str(archive),'--same-owner' if os.geteuid()==0 else '--no-same-owner','-C',str(target)],check=True)
unpack(core/'application-files.tar.gz',host/'home/deploy')
unpack(core/'tls.tar.gz',host)
unpack(core/'bridge-identity.tar.gz',host/'home/deploy')
unpack(extra/'monitoring-files.tar.gz',host/'home/deploy')
runtime=dest/'runtime'
unpack(extra/'nginx-runtime.tar.gz',runtime/'nginx')
unpack(extra/'native-web-runtime.tar.gz',runtime/'native')
unpack(core/'runtime-asterisk.tar.gz',runtime/'predictive')
unpack(core/'runtime-manual-asterisk.tar.gz',runtime/'manual')
code_roots={}
for name,archive in json.loads((extra/'runtime-code-index.json').read_text()).items():
    code_roots[name]=runtime/'code'/name
    unpack(extra/archive,code_roots[name])
containers=json.loads((core/'containers.json').read_text())+json.loads((extra/'monitoring-containers.json').read_text())
net_info={x['Name']:x for x in json.loads((extra/'network-inventory.json').read_text())}
images=json.loads(pathlib.Path(args.images).read_text())
compose={'name':args.project,'services':{},'networks':{},'volumes':{}}
volumes={}; seeds=[]; missing=[]
address_map={}
if args.public_ip: address_map['5.78.183.117']=args.public_ip
isolated_ranges={}
if not args.live:
    current=json.loads(subprocess.check_output(['docker','network','inspect']+subprocess.check_output(['docker','network','ls','-q'],text=True).split()))
    occupied=[ipaddress.ip_network(c['Subnet']) for n in current for c in (n.get('IPAM',{}).get('Config') or []) if c.get('Subnet') and ':' not in c['Subnet']]
    block=next((ipaddress.ip_network('10.'+str(i)+'.0.0/16') for i in range(233,255) if not any(ipaddress.ip_network('10.'+str(i)+'.0.0/16').overlaps(n) for n in occupied)),None)
    if block is None: raise SystemExit('No hay bloque de prueba libre')
    names=sorted({n for c in containers for n in c['NetworkSettings']['Networks']})
    for i,n in enumerate(names): isolated_ranges[n]=ipaddress.ip_network(str(block.network_address+i*256)+'/24')
    for c in containers:
        for n,settings in c['NetworkSettings']['Networks'].items():
            old=settings.get('IPAddress')
            if old: address_map[old]=str(isolated_ranges[n].network_address+int(old.split('.')[-1]))
def key(s): return 'v'+hashlib.sha256(s.encode()).hexdigest()[:16]
def network(old):
    n='n'+hashlib.sha256(old.encode()).hexdigest()[:12]
    if n not in compose['networks']:
        spec={'internal':not args.live}
        info=net_info.get(old,{})
        if not args.live:
            spec['ipam']={'config':[{'subnet':str(isolated_ranges[old]),'gateway':str(isolated_ranges[old].network_address+1)}]}
        if args.live and old not in ('host','bridge'):
            cfg=info.get('IPAM',{}).get('Config')
            if cfg: spec['ipam']={'config':[{k.lower():v for k,v in x.items() if k in ('Subnet','Gateway')} for x in cfg]}
        compose['networks'][n]=spec
    return n
for c in containers:
    name=c['Name'].lstrip('/'); cfg=c['Config']; h=c['HostConfig']
    if c['Image'] not in images: raise SystemExit('Falta imagen cargada '+name)
    profile='apps'
    if name in ('asistencias-api-db-1','vicidial-predictivo-mariadb-1'): profile='data'
    elif name in ('grafana','prometheus','node-exporter'): profile='monitoring'
    elif 'asterisk' in name or 'turn' in name or name=='itelvox-relay-180': profile='voice'
    elif name in ('crm-nginx','vicidial-predictivo-admin-gateway-1'): profile='edge'
    s={'image':images[c['Image']],'pull_policy':'never','container_name':args.project+'-'+name,
       'profiles':[profile],'restart':'no','environment':dict(x.split('=',1) for x in cfg.get('Env',[]) if '=' in x),
       'logging':{'driver':'json-file','options':{'max-size':'5m','max-file':'2'}}}
    for old,new in [('Entrypoint','entrypoint'),('Cmd','command'),('User','user'),('WorkingDir','working_dir')]:
        if cfg.get(old): s[new]=cfg[old]
    for old,new in [('CapAdd','cap_add'),('CapDrop','cap_drop'),('SecurityOpt','security_opt'),('ExtraHosts','extra_hosts'),('Sysctls','sysctls'),('Tmpfs','tmpfs')]:
        if h.get(old): s[new]=h[old]
    if isinstance(s.get('tmpfs'),dict): s['tmpfs']=[k+(':'+v if v else '') for k,v in s['tmpfs'].items()]
    if name=='asistencias-api-db-1':
        s['environment']['POSTGRES_USER']='recovery_admin'
        s['environment']['POSTGRES_DB']='postgres'
    if h.get('ReadonlyRootfs'): s['read_only']=True
    if h.get('ShmSize'): s['shm_size']=h['ShmSize']
    if h.get('Ulimits'): s['ulimits']={x['Name']:{'soft':x['Soft'],'hard':x['Hard']} for x in h['Ulimits']}
    if h.get('Init'): s['init']=True
    if h.get('PidMode') and args.live: s['pid']=h['PidMode']
    if h.get('GroupAdd'): s['group_add']=h['GroupAdd']
    health=cfg.get('Healthcheck')
    if health and health.get('Test'):
        s['healthcheck']={'test':health['Test']}
        for k in ('Interval','Timeout','StartPeriod'):
            if health.get(k): s['healthcheck'][re.sub(r'(?<!^)(?=[A-Z])','_',k).lower()]=str(health[k])+'ns'
        if health.get('Retries'): s['healthcheck']['retries']=health['Retries']
    if not args.live:
        s['mem_limit']='512m' if name=='vicidial-predictivo-mariadb-1' else '256m' if name=='asistencias-api-db-1' else '192m'
        s['cpus']=0.5
    if args.live and h.get('NetworkMode')=='host':
        s['network_mode']='host'
    elif args.live and list(c['NetworkSettings']['Networks'])==['bridge']:
        s['network_mode']='bridge'
    else:
        s['networks']={}
        for old,n in c['NetworkSettings']['Networks'].items():
            if old=='bridge' and len(c['NetworkSettings']['Networks'])>1: continue
            aliases=[x for x in (n.get('Aliases') or []) if not re.fullmatch('[a-f0-9]{12,64}',x)]
            aliases=list(dict.fromkeys([name]+aliases))
            setting={'aliases':aliases}
            if not args.live and n.get('IPAddress'): setting['ipv4_address']=address_map[n['IPAddress']]
            if args.live and old not in ('bridge','host') and n.get('IPAddress'): setting['ipv4_address']=n['IPAddress']
            s['networks'][network(old)]=setting
    if args.live and s.get('network_mode')!='host':
        ports=[]
        for target,bindings in (h.get('PortBindings') or {}).items():
            for b in bindings or []:
                ports.append({'target':int(target.split('/')[0]),'published':b['HostPort'],'protocol':target.split('/')[1],'host_ip':b.get('HostIp') or '0.0.0.0'})
        if ports: s['ports']=ports
    mounts=[]
    for m in c.get('Mounts',[]):
        if m['Type']=='volume':
            old=m['Name']; v=key(old); volumes[old]=v
            compose['volumes'][v]={'name':args.project+'-'+v,'external':True}
            mounts.append({'type':'volume','source':v,'target':m['Destination'],'read_only':not m['RW']})
        elif m['Type']=='bind':
            source=host/m['Source'].lstrip('/')
            if name=='node-exporter' and m['Source'] in ('/','/proc','/sys'):
                source=pathlib.Path(m['Source'])
            if not source.exists():
                if name=='node-exporter' and m['Source'] in ('/','/proc','/sys'):
                    source=pathlib.Path(m['Source'])
                else: missing.append({'container':name,'source':m['Source']})
            mounts.append({'type':'bind','source':str(source),'target':m['Destination'],'read_only':not m['RW'],'bind':{'create_host_path':False}})
        else: raise SystemExit('Mount no soportado: '+m['Type'])
    # Conservar configuraciones activas que no estaban en un bind persistente.
    additions=[]
    if name=='crm-nginx': additions=[(runtime/'nginx/etc/nginx','/etc/nginx')]
    if name=='vicidial-predictivo-native-web-1':
        native=code_roots[name]
        additions=[(runtime/'native/etc/astguiclient.conf','/etc/astguiclient.conf'),(runtime/'native/etc/apache2','/etc/apache2'),
                   (native/'opt/native-start.php','/opt/native-start.php'),(native/'opt/vicidial/source/www/internal/join.php','/opt/vicidial/source/www/internal/join.php')]
    if name=='vicidial-predictivo-asterisk-1':
        additions=[(runtime/'predictive/var/lib/asterisk','/var/lib/asterisk')]
        for m in mounts:
            if m['target']=='/opt/vpd-asterisk-config':
                m['source']=str(runtime/'predictive/etc/asterisk')
    for src,target in additions:
        mounts.append({'type':'bind','source':str(src),'target':target,'read_only':name=='crm-nginx','bind':{'create_host_path':False}})
    if mounts: s['volumes']=mounts
    compose['services'][name]=s
def replace_addresses(s):
    return re.sub(r'(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])',lambda m:address_map.get(m.group(),m.group()),s)
for service in compose['services'].values():
    for k,v in service.get('environment',{}).items():
        if 'B64' in k or 'BASE64' in k:
            try: v=base64.b64encode(replace_addresses(base64.b64decode(v).decode()).encode()).decode()
            except (ValueError,UnicodeDecodeError): pass
        service['environment'][k]=replace_addresses(v)
    # Only public listen addresses need changes here; isolated IPAM assignments are already adapted.
    for port in service.get('ports',[]): port['host_ip']=replace_addresses(port['host_ip'])
changed=[]
for base in (host,runtime):
    for file in base.rglob('*'):
        if not file.is_file() or file.is_symlink() or file.stat().st_size>8*1024**2: continue
        if any(part in ('backups','node_modules','.git') for part in file.parts): continue
        if file.suffix not in ('.conf','.env','.json','.yml','.yaml','.js','.html','.ini','.sh','.service','.php') and not file.name.endswith('.env'): continue
        try: text=file.read_text()
        except UnicodeDecodeError: continue
        altered=replace_addresses(text)
        if not args.live and file==host/'home/deploy/gemini-turn/turnserver.conf':
            altered=re.sub(r'^listening-ip=.*$', 'listening-ip=0.0.0.0',altered,flags=re.M)
            altered=re.sub(r'^relay-ip=.*$', '# relay-ip autodetectado solo para prueba aislada',altered,flags=re.M)
        if altered!=text: file.write_text(altered); changed.append(str(file.relative_to(dest)))
for name,base in code_roots.items():
    service=compose['services'][name]
    mounts=service.setdefault('volumes',[])
    targets={m['target'] for m in mounts}
    for relative in changed:
        file=dest/relative
        if not file.is_relative_to(base): continue
        target='/'+str(file.relative_to(base))
        if target in targets: continue
        mounts.append({'type':'bind','source':str(file),'target':target,'read_only':True,'bind':{'create_host_path':False}})
services=compose['services']
services['asistencias-api-db-1']['healthcheck']={'test':['CMD','pg_isready','-h127.0.0.1','-U','recovery_admin','-d','postgres'],'interval':'5s','timeout':'3s','retries':20}
for name in ('vicidial-predictivo-native-web-1','vicidial-predictivo-predictive-session-api-1','vicidial-predictivo-control-api-1','merced-mascotas-posibles-source-1','predictivo-tecnico-app-1'):
    services[name].setdefault('depends_on',{})['vicidial-predictivo-mariadb-1']={'condition':'service_healthy'}
for name in ('asistencias-api-api-1','merced-mascotas'):
    services[name].setdefault('depends_on',{})['asistencias-api-db-1']={'condition':'service_healthy'}
for name in ('vicidial-predictivo-asterisk-1','vicidial-predictivo-native-web-1'):
    services['vicidial-predictivo-predictive-session-api-1'].setdefault('depends_on',{})[name]={'condition':'service_started'}
for name in ('asistencias-api-api-1','merced-mascotas','merced-call-bridge','vicidial-predictivo-predictive-session-api-1','gemini-webphone-asterisk','crm-campana-maqueta','grafana'):
    services['crm-nginx'].setdefault('depends_on',{})[name]={'condition':'service_started'}
(dest/'address-map.json').write_text(json.dumps(address_map,indent=2))
(dest/'adapted-files.json').write_text(json.dumps(changed,indent=2))
def esc(x):
    if isinstance(x,str): return x.replace('$','$$')
    if isinstance(x,list): return [esc(v) for v in x]
    if isinstance(x,dict): return {k:esc(v) for k,v in x.items()}
    return x
(dest/'compose.json').write_text(json.dumps(esc(compose),indent=2))
(dest/'volume-map.json').write_text(json.dumps({old:args.project+'-'+v for old,v in volumes.items()},indent=2))
(dest/'missing-binds.json').write_text(json.dumps(missing,indent=2))
(dest/'original-containers.json').write_text(json.dumps(containers,indent=2))
(dest/'restore-inputs.json').write_text(json.dumps({'core':str(core),'extra':str(extra),'project':args.project},indent=2))
if missing: raise SystemExit('Faltan binds; revisar missing-binds.json. No iniciar.')
print('Despliegue generado:',len(compose['services']),'servicios;',len(compose['volumes']),'volumenes;',len(compose['networks']),'redes. Ningun servicio iniciado.')
