"""Mechanical request dispatch and JSON plumbing for the independent handlers."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
api = (root/'src/api_server.kan').read_text().split('def apiHandle :',1)[1]
for name in ['Handle','GetThenUpdate','GetThenDelete','Update','Delete','Create','List','Get']:
    api = api.replace('api'+name, 'oracle'+name)
(root/'src/oracle_dispatch.kan').write_text('def oracleHandle :'+api+'''
def oracleHandleMessage : InstalledTypes -> Message -> ApiState -> prod (ApiState, Message) := fun (it : InstalledTypes) (msg : Message) (s : ApiState) => match msg.3 as self in Content return prod (ApiState, Message) with
  | contentRequest req => let out : ApiOutput := oracleHandle it req s in tuple (out.0, messageFormResponse msg out.1)
  | contentResponse r => tuple (s, msg) | contentExternalRequest r => tuple (s, msg) | contentExternalResponse r => tuple (s, msg)
def oracleAgrees : InstalledTypes -> Request -> ApiState -> Bool := fun (it : InstalledTypes) (req : Request) (s : ApiState) =>
  let ref : ApiOutput := oracleHandle it req s in let actual : ApiOutput := apiHandle it req s in
  boolAnd (apiStateEqual ref.0 actual.0) (apiMethodApiResponseEqual ref.1 actual.1)
''')
wire = (root/'src/api_wire.kan').read_text().split('def apiInvoke :',1)[1]
wire = wire.replace('apiInvoke','oracleInvoke').replace('apiHandle it req s','oracleHandle it req s')
(root/'src/oracle_wire.kan').write_text('def oracleInvoke :'+wire)
