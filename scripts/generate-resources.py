"""Resource-view marshal contracts from the source's RESOURCE_VIEW instances."""
from pathlib import Path
root = Path(__file__).resolve().parent.parent
out = ['-- Resource marshal/unmarshal contracts, including kind and null checks.',
'''def decodeResourceObject : (0 A : Type 0) -> Bytes -> Bytes -> (Value -> Result A) -> Value -> Result A :=
  fun (0 A : Type 0) (label : Bytes) (detail : Bytes) (decode : Value -> Result A) (v : Value) =>
  case (jsonGetObject v) with | 0 (e : Error) => err A (decodeError label detail) | 1 (m : Members) => decode v
def decodeResourceOptional : (0 A : Type 0) -> Bytes -> (Value -> Result A) -> Value -> Result (Option A) :=
  fun (0 A : Type 0) (label : Bytes) (decode : Value -> Result A) (v : Value) =>
  case (jsonIsNull v) with | 1 (u : Unit) => ok (Option A) (none A)
  | 0 (u : Unit) => resultMap A (Option A) (fun (x : A) => some A x) (decodeResourceObject A label b"expected object or null" decode v)
def decodeResourceNull : Bytes -> Value -> Result Ghost := fun (label : Bytes) (v : Value) =>
  case (jsonIsNull v) with | 1 (u : Unit) => ok Ghost ghost | 0 (u : Unit) => err Ghost (decodeError label b"expected null")
def encodeResourceNull : Ghost -> Value := fun (x : Ghost) => jsonNull
''']
specs = [
    ('PodT', 'commonKindPod', 'pod', ('Option PodSpecT','podSpecT',True), ('Option Ghost','jsonGhost',True)),
    ('StatefulSetT', 'commonKindStatefulSet', 'stateful_set', ('Option StatefulSetSsSpec','statefulSetSsSpec',True), ('Option StatefulSetSsStatus','statefulSetSsStatus',True)),
    ('VreplicaSetT', '(commonKindCustomResource b"vreplicaset")', 'vreplica_set', ('VreplicaSetVrsSpec','vreplicaSetVrsSpec',False), ('Option VreplicaSetVrsStatus','vreplicaSetVrsStatus',True)),
    ('VDeploymentT', '(commonKindCustomResource b"vdeployment")', 'v_deployment', ('VDeploymentVdSpec','vDeploymentVdSpec',False), ('Ghost','null',False)),
    ('VStatefulSetT', '(commonKindCustomResource b"vstatefulset")', 'v_stateful_set', ('StatefulSetSsSpec','statefulSetSsSpec',False), ('Option StatefulSetSsStatus','statefulSetSsStatus',True)),
    ('ConfigMapT', 'commonKindConfigMap', 'config_map', ('Option StringMap','jsonMap',True), ('Ghost','null',False)),
    ('PersistentVolumeClaimT', 'commonKindPersistentVolumeClaim', 'PersistentVolumeClaim', ('Option PersistentVolumeClaimSpec','persistentVolumeClaimSpec',True), ('Option PersistentVolumeClaimStatus','persistentVolumeClaimStatus',True)),
]
for typ, kind, label, spec, status in specs:
    f=typ[:1].lower()+typ[1:]
    out.append(f'def {f}Kind : CommonKind := {kind}')
    for part,(t,codec,optional) in [('Spec',spec),('Status',status)]:
        fieldlabel = 'data' if typ=='ConfigMapT' and part=='Spec' else part.lower()
        if typ=='PersistentVolumeClaimT': fieldlabel=part
        labeltext = label+('.'+fieldlabel if typ!='PersistentVolumeClaimT' else fieldlabel)
        if codec=='null':
            enc='encodeResourceNull'
            dec=f'decodeResourceNull b"{labeltext}"'
        else:
            enc,dec={'jsonGhost':('jsonEncodeGhost','jsonDecodeGhost'), 'jsonMap':('jsonEncodeMap','jsonDecodeMap')}.get(codec,(codec+'Encode',codec+'Decode'))
            if optional:
                inner=t[7:]
                enc=f'jsonEncodeOption {inner} ({enc})'
                dec=f'decodeResourceOptional {inner} b"{labeltext}" ({dec})'
            else:
                dec=f'decodeResourceObject {t} b"{labeltext}" b"expected object" ({dec})'
        out.append(f'def {f}Marshal{part} : {t} -> Value := fun (x : {t}) => {enc} x')
        out.append(f'def {f}Unmarshal{part} : Value -> Result ({t}) := fun (x : Value) => {dec} x')
    getsp=f+'Data' if typ=='ConfigMapT' else f+'Spec'
    gets='ghost' if typ=='ConfigMapT' else f'({f}Status x)'
    out.append(f'def {f}Marshal : {typ} -> DynamicObjectT := fun (x : {typ}) =>\n'
               f'  dynamicObjectTMake {f}Kind ({f}Metadata x) ({f}MarshalSpec ({getsp} x)) ({f}MarshalStatus {gets})')
    tail='' if typ=='ConfigMapT' else ' status'
    out.append(f'''def {f}Unmarshal : DynamicObjectT -> Result {typ} := fun (x : DynamicObjectT) =>
  case (commonKindEqual (dynamicObjectTKind x) {f}Kind) with
  | 0 (u : Unit) => err {typ} (kindMismatch (kindShow {f}Kind) (kindShow (dynamicObjectTKind x)))
  | 1 (u : Unit) => resultBind ({spec[0]}) {typ} ({f}UnmarshalSpec (dynamicObjectTSpec x)) (fun (spec : {spec[0]}) =>
    resultMap ({status[0]}) {typ} (fun (status : {status[0]}) => {f}Make (dynamicObjectTMetadata x) spec{tail}) ({f}UnmarshalStatus (dynamicObjectTStatus x)))''')
    if typ.startswith('V'):
        out.append(f'''def {f}ControllerOwner : {typ} -> Option OwnerReferenceT := fun (x : {typ}) =>
  let m : ObjectMetaT := {f}Metadata x in
  optionBind Bytes OwnerReferenceT (objectMetaTName m) (fun (name : Bytes) =>
    optionMap Int OwnerReferenceT (fun (uid : Int) => ownerReferenceTMake (some Bool true) (some Bool true) {f}Kind name uid) (objectMetaTUid m))''')
(root / 'src/resources.kan').write_text('\n\n'.join(out)+'\n')
