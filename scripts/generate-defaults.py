"""Translate reviewed constant defaults; reject any unrecognized expression."""
import json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
defs=json.loads((root/'default-schema.json').read_text())
layouts=json.loads((root/'layout-info.json').read_text())
def camel(s): return ''.join(p[:1].upper()+p[1:] for p in s.split('_') if p)
def typename(d): return camel(d['module'])+camel(d['type'])
def lower(s): return s[0].lower()+s[1:]
calls={(d['module'],d['name']):typename(d) for d in defs}
bytype={}
for d in defs: bytype.setdefault(typename(d),d)
done=set();active=set();out=['-- Generated from the pinned source constant defaults.']
def expression(body,t,mod):
    if body=='None':
        assert t.startswith('Option ('),t
        return 'none '+t[7:]
    if body=='Some false':return 'some Bool false'
    if body=='()':return 'ghost'
    if body=='[]':return lower(t)+'Nil'
    if body=='""':return 'b""'
    if body in ['0','Common.Uid.of_int 0']:return 'nonnegative 0'
    if body=='Common.Custom_resource ""':return 'commonKindCustomResource b""'
    m=re.fullmatch(r'(?:(\w+)\.)?(\w+) \(\)',body)
    if m:
        key=(m[1][0].lower()+m[1][1:] if m[1] else mod,m[2]);dep=calls[key];emit(dep);return 'default'+dep
    raise ValueError((body,t,mod))
def emit(t):
    if t in done:return
    assert t not in active,t
    active.add(t);d=bytype[t];body=d['body']
    if body.startswith('{'):
        fields=dict(x.strip().split(' = ',1) for x in body[1:-1].split(';') if x.strip())
        args=[expression(fields[n],ty,d['module']) for n,ty in layouts[t]['fields']]
        value=lower(t)+'Make '+' '.join('('+a+')' for a in args)
    else:value=expression(body,t,d['module'])
    out.append(f'def default{t} : {t} := {value}');active.remove(t);done.add(t)
for t in bytype:emit(t)
resources={'VDeploymentT','VStatefulSetT','VreplicaSetT','PersistentVolumeClaimT','PodT','StatefulSetT','ConfigMapT'}
arr='jsonObjectNil';ml=[]
for t,d in reversed(list(bytype.items())):
    enc=f'{lower(t)}Encode default{t}'
    if t in resources:enc=f'dynamicObjectTEncode ({lower(t)}Marshal default{t})'
    arr=f'jsonObjectCons b"{t}" ({enc}) ({arr})'
    mod=d['module'][0].upper()+d['module'][1:];fn=mod+'.'+d['name']+' ()'
    oe=f'{mod}.to_json ({fn})' if d['type']=='t' else f'{mod}.{d["type"]}_to_json ({fn})'
    if t in resources:oe=f'Dynamic_object.to_json ({mod}.marshal ({fn}))'
    if t in ['VDeploymentVdSpec','VreplicaSetVrsSpec']:oe=f'Value.json ({mod}.marshal_spec ({fn}))'
    if t=='VreplicaSetVrsStatus':oe=f'Value.json ({mod}.marshal_status (Some ({fn})))'
    if t=='ApiMethodPreconditions':oe=f'let p = {fn} in Json.obj_opt [("uid", Json.opt (fun x -> Json.int_ (Common.Uid.to_int x)) p.uid); ("resourceVersion", Json.opt (fun x -> Json.int_ (Common.Resource_version.to_int x)) p.resource_version)]'
    fields={'StatefulSetOrdinals':('ordinals','ordinals'),'StatefulSetUpdateStrategy':('update_strategy','updateStrategy'),'StatefulSetRetentionPolicy':('persistent_volume_claim_retention_policy','persistentVolumeClaimRetentionPolicy')}
    if t in fields:
        field,key=fields[t];oe=f'member "{key}" (Stateful_set.ss_spec_to_json {{ (Stateful_set.ss_spec_default ()) with {field} = Some ({fn}) }})'
    if t=='StatefulSetRollingUpdate':oe=f'member "rollingUpdate" (member "updateStrategy" (Stateful_set.ss_spec_to_json {{ (Stateful_set.ss_spec_default ()) with update_strategy = Some {{ (Stateful_set.update_strategy_default ()) with rolling_update = Some ({fn}) }} }}))'
    ml.append(f'  ("{t}", {oe});')
out.append('def defaultsRender : Nat -> Bytes := fun (ignored : Nat) => valueRender (jsonObject ('+arr+'))')
(root/'src/defaults.kan').write_text('\n'.join(out)+'\n')
(root/'oracle/defaults_oracle.ml').write_text('let member key j = Result.fold (Json.mem j key) ~ok:(fun x -> x) ~error:(fun e -> `String (Err.show e))\nlet invoke () = Json.obj [\n'+'\n'.join(reversed(ml))+'\n]\n')
