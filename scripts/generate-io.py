"""Typed Kubernetes request construction and response projections."""
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=['''-- Io.void has no inhabitants, so these controllers use Kubernetes I/O only.
def Request : Type 0 := ApiMethodApiRequest
def Response : Type 0 := ApiMethodApiResponse
def ApiError : Type 0 := ApiMethodApiError
def ApiResult : (0 A : Type 0) -> Type 0 := fun (0 A : Type 0) => Either ApiError A
def apiOk : (0 A : Type 0) -> A -> ApiResult A := fun (0 A : Type 0) (x : A) => inj 1 of 2 x
def apiError : (0 A : Type 0) -> ApiError -> ApiResult A := fun (0 A : Type 0) (e : ApiError) => inj 0 of 2 e
def apiResultOption : (0 A : Type 0) -> ApiResult A -> Option A := fun (0 A : Type 0) (r : ApiResult A) =>
  case r with | 0 (e : ApiError) => none A | 1 (x : A) => some A x
def apiResponseOk : (0 A : Type 0) -> Option (ApiResult A) -> Option A := fun (0 A : Type 0) (r : Option (ApiResult A)) =>
  optionBind (ApiResult A) A r (fun (x : ApiResult A) => apiResultOption A x)
''']
names=['Get','List','Create','Delete','Update','UpdateStatus','GetThenDelete','GetThenUpdate','GetThenUpdateStatus']
for name in names:
    a='ListDynamicObjectT' if name=='List' else 'Ghost' if name in ['Delete','GetThenDelete'] else 'DynamicObjectT'
    out.append(f'def response{name} : Option Response -> Option (ApiResult {a}) := fun (response : Option Response) =>\n'
               f'  optionBind Response (ApiResult {a}) response (fun (r : Response) =>\n'
               f'    match r as self in ApiMethodApiResponse return Option (ApiResult {a}) with\n'+ '\n'.join(
                f'    | apiMethodApiResponse{n}Response x => '+(f'some (ApiResult {a}) (apiMethod{name}ResponseRes x)' if n==name else f'none (ApiResult {a})') for n in names)+')')
    out.append(f'def makeResponse{name} : ApiResult {a} -> Response := fun (r : ApiResult {a}) => apiMethodApiResponse{name}Response (apiMethod{name}ResponseMake r)')
requests=[
('Get',[('key','CommonObjectRef')]),('List',[('kind','CommonKind'),('ns','Bytes')]),
('Create',[('ns','Bytes'),('obj','DynamicObjectT')]),('Delete',[('key','CommonObjectRef'),('preconditions','Option ApiMethodPreconditions')]),
('Update',[('ns','Bytes'),('name','Bytes'),('obj','DynamicObjectT')]),('UpdateStatus',[('ns','Bytes'),('name','Bytes'),('obj','DynamicObjectT')]),
('GetThenDelete',[('key','CommonObjectRef'),('owner','OwnerReferenceT')]),
('GetThenUpdate',[('ns','Bytes'),('name','Bytes'),('owner','OwnerReferenceT'),('obj','DynamicObjectT')]),
('GetThenUpdateStatus',[('ns','Bytes'),('name','Bytes'),('owner','OwnerReferenceT'),('obj','DynamicObjectT')])]
for name,fields in requests:
    out.append(f'def request{name} : '+ ' -> '.join(t for _,t in fields) + ' -> Request := fun '+
               ' '.join(f'({x} : {t})' for x,t in fields)+f' => apiMethodApiRequest{name}Request (apiMethod{name}RequestMake '+ ' '.join(x for x,_ in fields)+')')
(root/'src/io.kan').write_text('\n\n'.join(out)+'\n')
