"""En servidor nuevo: python3 RESTAURAR_IMAGENES.py /ruta/imagenes-descifradas /ruta/private /ruta/supplement"""
import sys,pathlib,json,subprocess,re
images=pathlib.Path(sys.argv[1])
private=pathlib.Path(sys.argv[2])
mapping=json.loads((private/'image-map.json').read_text())
inventory=json.loads((private/'containers.json').read_text())
extra=pathlib.Path(sys.argv[3]) if len(sys.argv)>3 else None
if extra:
    additional=json.loads((extra/'monitoring-containers.json').read_text())
    inventory+=additional
    mapping += [{'id':c['Image']} for c in additional]
loaded={}
for original in sorted({x['id'] for x in mapping}):
    suffix=original.split(':')[1]+'.tar.gz'
    candidates=[images/suffix,images/('image-'+suffix)]
    if extra: candidates.append(extra/'images'/suffix)
    archive=next((p for p in candidates if p.exists()),None)
    if archive is None: raise SystemExit('Falta imagen '+suffix)
    result=subprocess.check_output(['docker','load','-i',str(archive)],text=True)
    hit=re.search(r'Loaded image ID: (sha256:[0-9a-f]+)',result)
    if not hit: raise SystemExit('Revise manualmente salida docker load: '+result)
    local=hit.group(1)
    # Docker con image store containerd puede asignar un ID distinto al de origen.
    tag='predictive-recovery/'+original.split(':')[1][:16]+':20261020'
    subprocess.run(['docker','tag',local,tag],check=True)
    loaded[original]=tag
overrides={}
for c in inventory:
    labels=c['Config'].get('Labels') or {}
    project=labels.get('com.docker.compose.project')
    service=labels.get('com.docker.compose.service')
    if project and service:
        overrides.setdefault(project,{'services':{}})['services'][service]={'image':loaded[c['Image']],'pull_policy':'never'}
dest=pathlib.Path('recovery-overrides')
dest.mkdir(exist_ok=True)
for project,override in overrides.items():
    (dest/(project+'.json')).write_text(json.dumps(override,indent=2)+'\n')
(dest/'loaded-images.json').write_text(json.dumps(loaded,indent=2)+'\n')
print('Imagenes cargadas. Overrides generados. NO se ha iniciado ningun servicio.')
print('Revisar compose original y usar -f original.yml -f recovery-overrides/PROYECTO.json')
print('No usar --build ni habilitar marcacion durante la recuperacion.')
