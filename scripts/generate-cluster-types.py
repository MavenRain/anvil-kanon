"""Concrete ordered maps for cluster state and installed models."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
out = ['''-- Source cluster records, with stateless unit hosts erased.
def ExternalProgram : Type 0 := prod (Value, (Value -> Value -> ResourceStore -> prod (Value, Value)))
def ControllerBundle : Type 0 := prod (ControllerProgram, Option ExternalProgram)
def Actor : Type 0 := prod (ControllerState, Option Value, Bool)
def actorEqual : Actor -> Actor -> Bool := fun (a : Actor) (b : Actor) => boolAnd (controllerStateEqual a.0 b.0) (boolAnd (optionEqual Value valueEqual a.1 b.1) (boolEqual a.2 b.2))''']
for typ, value, eq in [("ActorMap", "Actor", "actorEqual"), ("ModelMap", "ControllerBundle", None)]:
    f = typ[0].lower() + typ[1:]
    out.append(f'''mu {typ} : Type 0 := | {f}Nil : {typ} | {f}Cons (key : Int) (value : {value}) (tail : {typ}) : {typ}
def rec {f}Get : Int -> {typ} -> Option {value} := fun (key : Int) (s : {typ}) =>
  match s as self in {typ} return Option {value} with | {f}Nil => none {value}
  | {f}Cons k v t => (case (intEqual key k) with | 1 (u : Unit) => some {value} v | 0 (u : Unit) => {f}Get key t)
def rec {f}Set : Int -> {value} -> {typ} -> {typ} := fun (key : Int) (value : {value}) (s : {typ}) =>
  match s as self in {typ} return {typ} with | {f}Nil => {f}Cons key value {f}Nil
  | {f}Cons k v t => (case (intEqual key k) with | 1 (u : Unit) => {f}Cons key value t
    | 0 (u : Unit) => (case (intLess key k) with | 1 (u : Unit) => {f}Cons key value s | 0 (u : Unit) => {f}Cons k v ({f}Set key value t)))
def rec {f}Size : {typ} -> Nat := fun (s : {typ}) => match s as self in {typ} return Nat with
  | {f}Nil => 0 | {f}Cons k v t => natAdd 1 ({f}Size t)
def rec {f}Fold : (0 A : Type 0) -> {typ} -> A -> (Int -> {value} -> A -> A) -> A := fun (0 A : Type 0) (s : {typ}) (acc : A) (f : Int -> {value} -> A -> A) =>
  match s as self in {typ} return A with | {f}Nil => acc | {f}Cons k v t => {f}Fold A t (f k v acc) f''')
    if eq:
        out.append(f'''def rec {f}Equal : {typ} -> {typ} -> Bool := fun (a : {typ}) (b : {typ}) =>
  match a as self in {typ} return Bool with | {f}Nil => natEq ({f}Size b) 0
  | {f}Cons k v t => (match b as self in {typ} return Bool with | {f}Nil => false
    | {f}Cons l w r => boolAnd (intEqual k l) (boolAnd ({eq} v w) ({f}Equal t r)))''')
out.append('''def ClusterConfig : Type 0 := prod (InstalledTypes, ModelMap)
def ClusterState : Type 0 := prod (ApiState, ActorMap, MessagePool, Int, Bool, Bool)
def clusterStateEqual : ClusterState -> ClusterState -> Bool := fun (a : ClusterState) (b : ClusterState) =>
  boolAnd (apiStateEqual a.0 b.0) (boolAnd (actorMapEqual a.1 b.1) (boolAnd (messagePoolEqual a.2 b.2)
    (boolAnd (intEqual a.3 b.3) (boolAnd (boolEqual a.4 b.4) (boolEqual a.5 b.5)))))
mu MonkeyStep : Type 0 := | monkeyCreate : MonkeyStep | monkeyUpdate : MonkeyStep | monkeyUpdateStatus : MonkeyStep | monkeyDelete : MonkeyStep
mu ClusterStep : Type 0 :=
| stepApi (recv : Option Message) : ClusterStep
| stepBuiltin (key : CommonObjectRef) : ClusterStep
| stepController (id : Int) (recv : Option Message) (key : Option CommonObjectRef) : ClusterStep
| stepSchedule (id : Int) (key : CommonObjectRef) : ClusterStep
| stepRestart (id : Int) : ClusterStep
| stepDisableCrash (id : Int) : ClusterStep
| stepDrop (msg : Message) (error : ApiError) : ClusterStep
| stepDisableDrop : ClusterStep
| stepMonkey (pod : PodT) : ClusterStep
| stepDisableMonkey : ClusterStep
| stepExternal (id : Int) (recv : Option Message) : ClusterStep
| stepStutter : ClusterStep
mu ClusterStates : Type 0 := | clusterStatesNil : ClusterStates | clusterStatesCons (state : ClusterState) (tail : ClusterStates) : ClusterStates
def rec clusterStatesAppend : ClusterStates -> ClusterStates -> ClusterStates := fun (a : ClusterStates) (b : ClusterStates) => match a as self in ClusterStates return ClusterStates with
  | clusterStatesNil => b | clusterStatesCons h t => clusterStatesCons h (clusterStatesAppend t b)
def clusterStatesOption : Option ClusterState -> ClusterStates := fun (o : Option ClusterState) => optionFold ClusterState ClusterStates clusterStatesNil (fun (s : ClusterState) => clusterStatesCons s clusterStatesNil) o
def rec clusterStatesContains : ClusterState -> ClusterStates -> Bool := fun (s : ClusterState) (xs : ClusterStates) => match xs as self in ClusterStates return Bool with
  | clusterStatesNil => false | clusterStatesCons h t => boolOr (clusterStateEqual s h) (clusterStatesContains s t)
mu Successors : Type 0 := | successorsNil : Successors | successorsCons (step : ClusterStep) (state : ClusterState) (tail : Successors) : Successors
def rec successorsAppend : Successors -> Successors -> Successors := fun (a : Successors) (b : Successors) => match a as self in Successors return Successors with
  | successorsNil => b | successorsCons step state tail => successorsCons step state (successorsAppend tail b)
def rec successorsFor : ClusterStep -> ClusterStates -> Successors := fun (step : ClusterStep) (xs : ClusterStates) => match xs as self in ClusterStates return Successors with
  | clusterStatesNil => successorsNil | clusterStatesCons h t => successorsCons step h (successorsFor step t)
def rec successorsStates : Successors -> ClusterStates := fun (xs : Successors) => match xs as self in Successors return ClusterStates with
  | successorsNil => clusterStatesNil | successorsCons step state tail => clusterStatesCons state (successorsStates tail)
def rec successorsFold : (0 A : Type 0) -> Successors -> A -> (A -> ClusterStep -> ClusterState -> A) -> A := fun (0 A : Type 0) (xs : Successors) (acc : A) (f : A -> ClusterStep -> ClusterState -> A) =>
  match xs as self in Successors return A with | successorsNil => acc | successorsCons step state tail => successorsFold A tail (f acc step state) f
def Bound : Type 0 := prod (Int, Int, Int, Int, Int, Int, Int, ListPodT)
def boundDefault : Bound := tuple (nonnegative 8, nonnegative 4, nonnegative 2, nonnegative 16, nonnegative 32, nonnegative 8, nonnegative 16, listPodTNil)''')
(root / "src/cluster_types.kan").write_text("\n\n".join(out) + "\n")
print("Generated concrete cluster maps and transition types")
