"""Generate named predicate records; executable predicates live in Kanon."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = ['-- Generated named families. Keep ordering and non-vacuity independent.']

def family(symbol, args, entries):
    sig = ' -> '.join(['(' + t + ')' if '->' in t else t for _, t in args] + ['Invariants'])
    lam = ' '.join(f'({n} : {t})' for n, t in args)
    out.append(f'def {symbol} : {sig} := ' + (f'fun {lam} =>' if args else ''))
    out.append('  let empty : Invariants := sequenceEmpty Invariant in')
    prev = 'empty'
    for i, (name, source, holds, witness) in enumerate(entries):
        curr = f'family{i}'
        out.append(f'  let {curr} : Invariants := sequencePush Invariant {prev} (tuple (b"{name}", b"{source}", (fun (s : ClusterState) => {holds}), (fun (s : ClusterState) => {witness}))) in')
        prev = curr
    out.append('  ' + prev)

structural = [
 ('etcd_objects_have_unique_uids', 'objects_in_store.rs:23', 'assuranceUniqueUids s', 'natLt 1 (resourceStoreSize s.0.0)'),
 ('each_object_in_etcd_is_weakly_well_formed', 'objects_in_store.rs:33', 'assuranceStoreWellFormed s', 'natLt 0 (resourceStoreSize s.0.0)'),
 ('each_object_in_etcd_has_at_most_one_controller_owner', 'objects_in_store.rs:299', 'storeEvery s.0.0 (fun (k : CommonObjectRef) (o : DynamicObjectT) => assuranceOneOwner (dynamicObjectTMetadata o))', 'storeAny s.0.0 (fun (k : CommonObjectRef) (o : DynamicObjectT) => assuranceAnyOwner (dynamicObjectTMetadata o))'),
 ('scheduled_cr_has_lower_uid_than_uid_counter', 'controller_runtime_safety.rs:15', 'storeEvery (assuranceScheduled id s) (fun (k : CommonObjectRef) (o : DynamicObjectT) => assuranceUidBelow s.0.1 o)', 'natLt 0 (resourceStoreSize (assuranceScheduled id s))'),
 ('triggering_cr_has_lower_uid_than_uid_counter', 'controller_runtime_safety.rs:47', 'ongoingEvery (assuranceOngoing id s) (fun (k : CommonObjectRef) (o : Ongoing) => assuranceUidBelow s.0.1 o.0)', 'natLt 0 (ongoingMapSize (assuranceOngoing id s))'),
 ('every_ongoing_reconcile_has_unique_id', 'controller_runtime_safety.rs:874', 'assuranceUniqueReconcile id s', 'natLt 1 (ongoingMapSize (assuranceOngoing id s))'),
]
structural = [(n, 'kubernetes_cluster/proof/' + p, h, w) for n, p, h, w in structural]
family('clusterStructural', [('id', 'Int')], structural)
out.append('def storeFamily : Int -> Invariants := fun (id : Int) => sequenceSlice Invariant (clusterStructural id) 0 3')

network = [
 ('every_in_flight_msg_has_lower_id_than_allocator', 35, 'messagePoolEvery s.2 (fun (m : Message) => intLess m.2 s.3)', 'natLt 0 (messagePoolSize s.2)'),
 ('every_pending_req_msg_has_lower_id_than_allocator', 76, 'assurancePendingLower id s', 'assuranceSomePending id s'),
 ('every_in_flight_req_msg_has_different_id_from_pending_req_msg_of_every_ongoing_reconcile', 254, 'assuranceFlightPendingDistinct id s', 'boolAnd (assuranceSomePending id s) (messagePoolAny s.2 assuranceApiRequest)'),
 ('every_in_flight_req_msg_from_controller_has_valid_controller_id', 312, 'assuranceValidControllerIds c s', 'messagePoolAny s.2 (fun (m : Message) => boolAnd (assuranceApiRequest m) (optionIsSome (prod (Int, CommonObjectRef)) (hostControllerData m.0)))'),
 ('every_in_flight_msg_has_no_replicas_and_has_unique_id', 382, 'assuranceUniqueFlight s', 'natLt 1 (messagePoolSize s.2)'),
]
family('correspondenceFamily', [('c', 'ClusterConfig'), ('id', 'Int')], [(n, f'kubernetes_cluster/proof/network.rs:{l}', h, w) for n, l, h, w in network])

family('reconcileCorrespondenceFamily', [('id', 'Int'), ('pending', 'Value -> Bool'), ('quiet', 'Value -> Bool')], [
 ('pending_req_of_key_is_unique_with_unique_id', 'kubernetes_cluster/proof/network.rs:104', 'assuranceUniquePending id s', 'natLt 1 (assurancePendingCount id s)'),
 ('pending_req_in_flight_or_resp_in_flight_at_reconcile_state', 'kubernetes_cluster/proof/controller_runtime_liveness.rs:131', 'assurancePendingExpected id pending s', 'assuranceExpectedWitness id pending s'),
 ('pending_req_in_flight_xor_resp_in_flight_if_has_pending_req_msg', 'kubernetes_cluster/proof/controller_runtime_liveness.rs:147', 'assurancePendingXor id s', 'ongoingAny (assuranceOngoing id s) (fun (k : CommonObjectRef) (o : Ongoing) => assuranceHasPendingRequest o)'),
 ('no_pending_req_msg_at_reconcile_state', 'kubernetes_cluster/proof/controller_runtime_liveness.rs:105', 'assuranceNoPendingExpected id quiet s', 'assuranceExpectedWitness id quiet s'),
])

provenance = [('every_msg_from_vsts_controller_carries_vsts_key', 'vstatefulset_controller/proof/helper_invariants.rs:1213',
 'messagePoolEvery s.2 (fun (m : Message) => optionFold (prod (Int, CommonObjectRef)) Bool true (fun (x : prod (Int, CommonObjectRef)) => implies (intEqual x.0 id) (commonKindEqual (commonObjectRefKind x.1) vStatefulSetTKind)) (hostControllerData m.0))',
 'messagePoolAny s.2 (fun (m : Message) => hostIsController m.0 id)')]
for name, line, host, check in [('all_requests_from_pod_monkey_are_api_pod_requests', 570, 'hostMonkey', 'assuranceMonkeyRequest'), ('all_requests_from_builtin_controllers_are_api_delete_requests', 618, 'hostBuiltin', 'assuranceBuiltinRequest')]:
 provenance.append((name, f'kubernetes_cluster/proof/network.rs:{line}', f'messagePoolEvery s.2 (fun (m : Message) => implies (hostEqual m.0 {host}) (boolAnd (hostEqual m.1 hostApi) (optionFold Request Bool false {check} (contentGetRequest m.3))))', f'messagePoolAny s.2 (fun (m : Message) => hostEqual m.0 {host})'))
provenance.append(('no_pending_request_to_api_server_from_api_server_or_external', 'kubernetes_cluster/proof/network.rs:540', 'messagePoolEvery s.2 (fun (m : Message) => boolNot (boolAnd (assuranceForbiddenSource m.0) (boolAnd (hostEqual m.1 hostApi) (assuranceApiRequest m))))', 'messagePoolAny s.2 (fun (m : Message) => assuranceForbiddenSource m.0)'))
family('provenanceFamily', [('id', 'Int')], provenance)

family('responseRvFamily', [('b', 'Bound')], [
 ('object_in_ok_get_response_has_smaller_rv_than_etcd', 'kubernetes_cluster/proof/req_resp.rs:14', 'assuranceGetRvLower s', 'messagePoolAny s.2 (fun (m : Message) => optionIsSome DynamicObjectT (assuranceOkGet m))'),
 ('object_in_ok_get_resp_is_same_as_etcd_with_same_rv', 'kubernetes_cluster/proof/req_resp.rs:69', 'assuranceGetSameRv b s', 'assuranceGetSameRvWitness b s'),
])
family('responseMatchedFamily', [('id', 'Int')], [
 ('key_of_object_in_matched_ok_get_resp_message_is_same_as_key_of_pending_req', 'kubernetes_cluster/proof/req_resp.rs:136', 'assuranceMatchedGet id s', 'assuranceMatchedGetWitness id s'),
 ('key_of_object_in_matched_ok_create_resp_message_is_same_as_key_of_pending_req', 'kubernetes_cluster/proof/req_resp.rs:345', 'assuranceMatchedCreate id s', 'assuranceMatchedCreateWitness id s'),
])
family('vstsInvariants', [('cr', 'Stateful'), ('id', 'Int')], [
 ('vsts_reconcile_request_only_interferes_with_itself', 'vreplicaset_controller/proof/helper_invariants/predicate.rs:237 (widened inv9; vstatefulset has no upstream analogue)', 'vstsRequestsHold cr id (fun (r : Request) => true) (vstsSelfRequest cr) s', 'vstsRequestsWitness cr id (fun (r : Request) => true) s'),
 ('owned_pods_have_wellformed_ordinal_identity', 'vstatefulset_controller/proof/predicate.rs (ordinal identity)', 'vstsOrdinalIdentity cr s', 'natLt 0 (listDynamicObjectTLength (vstsOwned commonKindPod cr s))'),
 ('owned_pvcs_bound_to_vsts', 'vstatefulset_controller/proof/predicate.rs (pvc binding)', 'vstsOwnedPvcBound cr s', 'natLt 0 (listDynamicObjectTLength (vstsOwned commonKindPersistentVolumeClaim cr s))'),
])
guarantees = []
for name, line, rank in [('vsts_internal_guarantee_create_req', 562, 2), ('vsts_internal_guarantee_get_then_delete_req', 581, 6), ('vsts_internal_guarantee_get_then_update_req', 589, 7), ('no_interfering_request_between_vsts', 544, None)]:
 choose = '(fun (r : Request) => true)' if rank is None else f'(fun (r : Request) => natEq (apiMethodApiRequestRank r) {rank})'
 guarantees.append((name, f'vstatefulset_controller/proof/internal_rely_guarantee.rs:{line}', f'vstsRequestsHold cr id {choose} (vstsNonInterfering cr) s', f'vstsRequestsWitness cr id {choose} s'))
family('vstsGuaranteeFamily', [('cr', 'Stateful'), ('id', 'Int')], guarantees)
family('vstsHelperFamily', [('cr', 'Stateful')], [
 ('all_pods_in_etcd_matching_vsts_have_no_finalizer_or_deletion_timestamp_and_one_owner_ref', 'vstatefulset_controller/proof/helper_invariants.rs:52', 'vstsHelperPods cr s', 'storeAny s.0.0 (fun (k : CommonObjectRef) (o : DynamicObjectT) => vstsPodPremise cr k)'),
 ('all_pvcs_in_etcd_matching_vsts_have_no_finalizer_or_deletion_timestamp_or_owner_ref', 'vstatefulset_controller/proof/helper_invariants.rs:1063', 'vstsHelperPvcs cr s', 'storeAny s.0.0 (fun (k : CommonObjectRef) (o : DynamicObjectT) => vstsPvcPremise cr k)'),
])
rely = []
for name, line, rank in [('vsts_rely_create_req', 57, 2), ('vsts_rely_update_req', 76, 4), ('vsts_rely_conditions_pod_monkey', 17, None)]:
 choose = '(fun (r : Request) => true)' if rank is None else f'(fun (r : Request) => natEq (apiMethodApiRequestRank r) {rank})'
 rely.append((name, f'vstatefulset_controller/trusted/rely_guarantee.rs:{line}', f'vstsRelyHolds {choose} s', f'vstsRelyWitness {choose} s'))
family('vstsRelyFamily', [], rely)
at = 'vstsAtReconcile id (vstsRef cr)'
family('vstsBindingFamily', [('cr', 'Stateful'), ('id', 'Int')], [
 ('vsts_local_pods_and_pvcs_bound_in_local_state', 'vstatefulset_controller/proof/internal_rely_guarantee.rs:613', f'{at} true true (fun (o : Ongoing) (st : StatefulState) (s : ClusterState) => vstsBoundInLocal (vstsRef cr) st) s', f'{at} false false (fun (o : Ongoing) (st : StatefulState) (s : ClusterState) => vstsLocalBindingWitness st) s'),
 ('vsts_local_pods_and_pvcs_bound_with_key', 'vstatefulset_controller/proof/internal_rely_guarantee.rs:640', 'vstsBindingAtKey id (vstsRef cr) s', f'{at} false false (fun (o : Ongoing) (st : StatefulState) (s : ClusterState) => boolAnd (vstsIsAfterList st) (optionIsSome Message o.1)) s'),
])
family('vstsPredicateFamily', [('cr', 'Stateful'), ('id', 'Int')], [
 ('vsts_local_state_is_valid', 'vstatefulset_controller/proof/liveness/state_predicates.rs:192', f'{at} true true (fun (o : Ongoing) (st : StatefulState) (s : ClusterState) => implies (vstsValidStep (vStatefulSetReconcilerSReconcileStep st)) (vstsLocalStateValid (vstsName cr) (vstsNamespace cr) (vstsReplicas cr) st)) s', f'{at} false false (fun (o : Ongoing) (st : StatefulState) (s : ClusterState) => vstsValidStep (vStatefulSetReconcilerSReconcileStep st)) s'),
 ('vsts_pending_list_pod_resp_in_flight', 'vstatefulset_controller/proof/liveness/state_predicates.rs:107', f'{at} true true (fun (o : Ongoing) (st : StatefulState) (s : ClusterState) => implies (vstsIsAfterList st) (optionFold Message Bool true (fun (req : Message) => assuranceListResponseEvery s req (vstsListResponseShape (vstsNamespace cr))) o.1)) s', f'{at} false false (fun (o : Ongoing) (st : StatefulState) (s : ClusterState) => boolAnd (vstsIsAfterList st) (optionFold Message Bool false (assuranceListResponseAny s) o.1)) s'),
])
family('vstsAllLocalBindingFamily', [('id', 'Int')], [
 ('local_pods_and_pvcs_are_bound_to_vsts', 'vstatefulset_controller/proof/internal_rely_guarantee.rs:606', 'ongoingEvery (assuranceOngoing id s) (fun (k : CommonObjectRef) (o : Ongoing) => implies (commonKindEqual (commonObjectRefKind k) vStatefulSetTKind) (vstsBindingAtKey id k s))', 'ongoingAny (assuranceOngoing id s) (fun (k : CommonObjectRef) (o : Ongoing) => commonKindEqual (commonObjectRefKind k) vStatefulSetTKind)'),
])
family('vstsLivenessGoal', [('cr', 'Stateful')], [
 ('vsts_current_state_matches', 'vstatefulset_controller/trusted (ordinal-stable ESR goal)', 'vstsCurrentStateMatches cr s', 'natLt 0 (listDynamicObjectTLength (vstsOwned commonKindPod cr s))'),
])
out.append('def vstsAlways : Stateful -> Int -> Invariants := fun (cr : Stateful) (id : Int) => sequenceAppend Invariant (clusterStructural id) (vstsInvariants cr id)')
vrs_src = 'vreplicaset_controller/proof/helper_invariants/predicate.rs:'
self_msg = '(hostEqual m.0 (hostController id (vrsRef cr)))'
api_dst = '(hostEqual m.1 hostApi)'
def messages(scope, predicate):
 return f'messagePoolEvery s.2 (fun (m : Message) => implies {scope} (optionFold Request Bool true {predicate} (contentGetRequest m.3)))'
def message_witness(scope, predicate='(fun (r : Request) => true)'):
 return f'messagePoolAny s.2 (fun (m : Message) => boolAnd {scope} (optionFold Request Bool false {predicate} (contentGetRequest m.3)))'
family('vrsAlwaysSpecific', [('cr', 'Vrs'), ('id', 'Int')], [
 ('vrs_reconcile_request_only_interferes_with_itself', vrs_src + '237', messages(self_msg, '(vrsSelfRequest cr)'), message_witness(self_msg)),
 ('filtered_pods_invariant_matrix', vrs_src + '359', 'vrsAtReconcile cr id true (vrsFilteredMatrix cr) s', 'vrsAtReconcile cr id false (fun (o : Ongoing) (st : VrsState) (s : ClusterState) => optionIsSome ListPodT (vreplicaSetReconcilerSFilteredPods st)) s'),
 ('local_pods_are_bound_to_vrs_with_key', 'vreplicaset_controller/proof/guarantee.rs:45', 'vrsAtReconcile cr id true (vrsLocalBound cr) s', 'vrsAtReconcile cr id false (fun (o : Ongoing) (st : VrsState) (s : ClusterState) => optionFold ListPodT Bool false (fun (xs : ListPodT) => natLt 0 (listPodTLength xs)) (vreplicaSetReconcilerSFilteredPods st)) s'),
])
family('vrsEventuallyAlways', [('cr', 'Vrs'), ('id', 'Int')], [
 ('garbage_collector_does_not_delete_vrs_pods', vrs_src + '316', messages(f'(boolAnd (hostEqual m.0 hostBuiltin) {api_dst})', '(vrsGcRequest cr s)'), message_witness(f'(boolAnd (hostEqual m.0 hostBuiltin) {api_dst})', 'assuranceBuiltinRequest')),
 ('no_other_pending_request_interferes_with_vrs_reconcile', vrs_src + '175', messages(f'(boolAnd {api_dst} (boolNot {self_msg}))', '(vrsOtherRequest cr s)'), message_witness(f'(boolAnd {api_dst} (boolNot {self_msg}))')),
 ('every_msg_from_key_is_pending_req_msg_of', 'kubernetes_cluster/proof/controller_runtime_safety.rs:911', 'vrsPendingFromKey cr id s', message_witness(self_msg)),
 ('inductive_current_state_matches', 'vreplicaset_controller/proof/predicate.rs:502', 'boolAnd (vrsCurrentStateMatches cr s) (vrsAtReconcile cr id true (vrsInductiveShape cr id) s)', 'optionIsSome Ongoing (ongoingMapGet (vrsRef cr) (assuranceOngoing id s))'),
 ('vrs_in_schedule/reconcile_has_spec_and_uid_as', vrs_src + '449,459', 'vrsScheduledOngoingSpec cr id s', 'boolOr (optionIsSome Ongoing (ongoingMapGet (vrsRef cr) (assuranceOngoing id s))) (optionIsSome DynamicObjectT (resourceStoreGet (vrsRef cr) (assuranceScheduled id s)))'),
 ('no_pending_mutation_request_not_from_controller_on_pods', vrs_src + '340', messages('(vrsNonControllerSource m)', 'vrsNoMutatePod'), message_witness('(vrsNonControllerSource m)')),
])
family('vrsLivenessGoal', [('cr', 'Vrs')], [
 ('current_state_matches', 'vreplicaset_controller/trusted/liveness_theorem.rs:21', 'vrsCurrentStateMatches cr s', 'natLt 0 (listDynamicObjectTLength (vrsMatchingPods cr s))'),
])
out.append('def vrsAlways : Vrs -> Int -> Invariants := fun (cr : Vrs) (id : Int) => sequenceAppend Invariant (clusterStructural id) (vrsAlwaysSpecific cr id)')
out.append('def vrsAllInvariants : Vrs -> Int -> Invariants := fun (cr : Vrs) (id : Int) => sequenceAppend Invariant (vrsAlways cr id) (vrsEventuallyAlways cr id)')
(ROOT / 'src/assurance_families.kan').write_text('\n'.join(line.rstrip() for line in '\n'.join(out).splitlines()) + '\n')
