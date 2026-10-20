"""Comprueba el ensayo aislado: python3 VALIDAR_RECUPERACION.py /ruta/destino"""
import pathlib,json,subprocess,os,datetime,sys
d=pathlib.Path(sys.argv[1]).resolve()
project=json.loads((d/'restore-inputs.json').read_text())['project']
ids=subprocess.check_output(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project],text=True).split()
cs=json.loads(subprocess.check_output(['docker','inspect']+ids))
assert len(cs)==23
assert all(c['State']['Running'] and not c['State']['OOMKilled'] for c in cs),[(c['Name'],c['State']['Status']) for c in cs if not c['State']['Running']]
assert all(not c['HostConfig'].get('PortBindings') for c in cs),'Solo para ensayo sin puertos publicados'
netids=set(n['NetworkID'] for c in cs for n in c['NetworkSettings']['Networks'].values())
nets=json.loads(subprocess.check_output(['docker','network','inspect']+list(netids)))
assert all(n['Internal'] for n in nets),'Solo para ensayo aislado'
original=json.loads((d/'original-containers.json').read_text())
env0=dict(x.split('=',1) for x in next(x for x in original if 'mariadb' in x['Name'])['Config']['Env'] if '=' in x)
q="SELECT v FROM predictive_session.predictive_control WHERE k='motor_paused'; SELECT COUNT(*) FROM predictive_session.predictive_advisor_slots WHERE current_state<>'disconnected'; SELECT COUNT(*) FROM predictive_session.predictive_calls;"
counts=subprocess.check_output(['docker','exec','-e','MYSQL_PWD',project+'-vicidial-predictivo-mariadb-1','mariadb','-uroot','-N','-e',q],env={**os.environ,'MYSQL_PWD':env0['MARIADB_ROOT_PASSWORD']},text=True).split()
assert counts[:2]==['1','0']
js="""(async()=>{
const results=[];
for(const u of ['http://127.0.0.1:4315/healthz','http://crm-campana-maqueta/gemini/',process.env.NATIVE_BASE_URL+'/agc/vicidial.php']){
 const r=await fetch(u,{signal:AbortSignal.timeout(5000)});results.push(r.status);if(r.status!==200)throw Error('HTTP '+r.status);
}
const https=require('node:https');
await new Promise((ok,bad)=>{
 https.get({hostname:'crm-nginx',servername:'crm.mercedtelco.com',path:'/gemini/',headers:{Host:'crm.mercedtelco.com'},rejectUnauthorized:true},r=>{
  results.push(r.statusCode);r.resume();r.statusCode===200?ok():bad(Error('HTTPS '+r.statusCode));
 }).on('error',bad);
});
console.log(JSON.stringify(results));
})().catch(e=>{console.error(e.message);process.exit(1)})"""
http=json.loads(subprocess.check_output(['docker','exec',project+'-vicidial-predictivo-predictive-session-api-1','node','-e',js],text=True))
subprocess.run(['docker','exec',project+'-crm-nginx','nginx','-t'],check=True,stdout=subprocess.DEVNULL)
report={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'running_services':len(cs),'internal_networks':len(nets),
        'published_ports':0,'motor_paused':True,'connected_advisors':0,'calls_preserved':int(counts[2]),
        'http_statuses':http,'https_certificate_verified':True,'nginx_config':'passed',
        'limits':'No valida llamadas reales, audio RTP ni autorizacion del proveedor para una IP nueva'}
(d/'DR-VALIDATION.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
