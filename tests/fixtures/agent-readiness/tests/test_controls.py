import asyncio,copy,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import readiness as r
from agent_core import *
BRIEF={'version':'1.0.0','policy_id':'readiness-v1','brief':'[S1] Members see overdue books to return them. [S2] Each overdue loan displays Overdue.'}
TASK={'readiness':'ready','missing_requirement_ids':[],'assessments':[{'rule_id':rule,'met':True,'reason':'The cited text supplies relevant evidence.','citations':[{'statement_id':'S1','quote':'Members see overdue books'}]} for rule in ('R-OBJECTIVE','R-ACCEPTANCE','R-CONSISTENCY')]}
def reply(content,stop='end_turn',usage=None):return {'id':'synthetic-message','request_id':'synthetic-request','model':r.CONFIG['model'],'stop_reason':stop,'content':content,'usage':usage if usage is not None else {'input_tokens':100,'output_tokens':50,'cache_creation_input_tokens':0,'cache_read_input_tokens':0}}
def tool(ident='tool-1',name='get_policy',arguments=None):return reply([{'type':'tool_use','id':ident,'name':name,'input':arguments or {'policy_id':'readiness-v1'}}],'tool_use')
def final(task=None):return reply([{'type':'text','text':json.dumps(task or TASK)}])
class Fake:
    simulated=True
    def __init__(self,responses=None,count=100):self.responses=list(responses if responses is not None else [tool(),final()]);self.requests=[];self.counts=[];self.count_value=count
    async def count(self,request,timeout):
        self.counts.append(copy.deepcopy(request))
        if isinstance(self.count_value,BaseException):raise self.count_value
        return self.count_value
    async def create(self,request,timeout):
        self.requests.append(copy.deepcopy(request));value=self.responses.pop(0)
        if isinstance(value,BaseException):raise value
        if callable(value):return await value()
        return value
@pytest.fixture
def directory(tmp_path):r.Campaign.initialize(tmp_path);return tmp_path
def run(directory,fake=None,value=None):
    fake=fake or Fake();emergency=[]
    result=asyncio.run(r.invoke(BRIEF if value is None else value,transport=fake,campaign_dir=directory,emergency=emergency.append))
    assert r.Draft202012Validator(r.SCHEMAS['return']).is_valid(result)
    if not emergency:
        records=[json.loads(x) for x in (directory/'evidence.jsonl').read_text().splitlines()]
        matched=[x for x in records if x['record_id']==result['evidence_ref'].split('#')[-1]]
        assert len(matched)==1 and matched[0]['disposition']==result['terminal_disposition']
        assert matched[0]['invocation_id']==result['invocation_id'] and matched[0]['core_version']=='0.2.0'
        journal=[json.loads(x) for x in (directory/'campaign.jsonl').read_text().splitlines()]
        reserved=[x for x in journal if x['event']=='reserve' and x.get('invocation_id')==result['invocation_id']]
        attempts=[x for x in records if x['invocation_id']==result['invocation_id'] and x['payload']['record_kind']=='model_attempt']
        assert len(attempts)==len(reserved)
    if result['terminal_disposition']!='success':assert result['task_result'] is None
    return result,fake,emergency
def terminal(directory):return [json.loads(x) for x in (directory/'evidence.jsonl').read_text().splitlines()][-1]
def test_known_good_flow(directory):
    out,fake,_=run(directory);rec=terminal(directory)
    assert out['terminal_disposition']=='success' and len(fake.requests)==2 and len(fake.counts)==2
    assert fake.requests[0]['tool_choice']['name']=='get_policy'
    assert fake.requests[1]['output_config']['format']['type']=='json_schema'
    assert fake.requests[1]['messages'][-1]['content'][0]['tool_use_id']=='tool-1'
    assert (rec['model_attempts'],rec['tool_iterations'],rec['tokens_used'])==(2,1,300)
    assert rec['payload']['parse_diagnostics']['candidate_count']==1 and rec['payload']['simulated'] is True
    assert out['invocation_id']!='synthetic-message'
@pytest.mark.parametrize('value',[{},dict(BRIEF,version='2'),dict(BRIEF,policy_id='other'),dict(BRIEF,brief=''),dict(BRIEF,brief='   '),dict(BRIEF,brief='x'*16001),dict(BRIEF,extra=True),dict(BRIEF,brief=12),'garbage','{"version":"1.0.0","version":"1.0.0"}'])
def test_invalid_input_before_calls(directory,value):
    out,fake,_=run(directory,value=value);assert out['terminal_disposition'] in ('schema_invalid','parse_failed') and not fake.requests and not fake.counts
@pytest.mark.parametrize('case',['unknown_tool','wrong_arguments','duplicate_request','reused_request'])
def test_tool_rejection(directory,case):
    bad=tool()
    if case=='unknown_tool':bad['content'][0]['name']='write_file'
    if case=='wrong_arguments':bad['content'][0]['input']={'path':'/tmp/no'}
    if case=='duplicate_request':bad['content']*=2
    out,_,_=run(directory,Fake([tool(),bad] if case=='reused_request' else [bad]))
    assert out['terminal_disposition']=='tool_error' and terminal(directory)['tool_iterations']==(1 if case=='reused_request' else 0)
@pytest.mark.parametrize('mode',['wrong','duplicate','orphan','duplicate_request'])
def test_core_correlation_negative(mode):
    req=[ToolRequest('1','get_policy',{})];res=[ToolResult('1','get_policy',True,{})]
    if mode=='wrong':res=[ToolResult('1','other',True,{})]
    if mode=='duplicate':res*=2
    if mode=='orphan':res=[ToolResult('2','get_policy',True,{})]
    if mode=='duplicate_request':req*=2
    with pytest.raises(ToolLoopError):correlate_results(req,res)
def test_core_correlation_control():
    req=[ToolRequest('a','get_policy',{}),ToolRequest('b','get_policy',{})]
    res=[ToolResult('b','get_policy',True,{}),ToolResult('a','get_policy',True,{})]
    assert [x.request_id for x in correlate_results(req,res)]==['a','b']
def test_synthetic_write_denied_read_allowed():
    sec=SecurityBoundary();sec.authorize_tool(ToolCapability('read',{},SideEffectClass.NONE),{})
    with pytest.raises(AuthorizationError):sec.authorize_tool(ToolCapability('write',{},SideEffectClass.LOCAL),{})
def test_identity_stamping():assert stamp_identity({'invocation_id':'forged','agent_id':'forged','value':1},{'invocation_id':'trusted'})=={'value':1,'invocation_id':'trusted'}
@pytest.mark.parametrize('raw,ok',[(' \n'+json.dumps(TASK)+' \n',True),('```json\n'+json.dumps(TASK)+'\n```',False),('{',False),(json.dumps(TASK)+json.dumps(TASK),False),('{"readiness":"ready","readiness":"ready"}',False)])
def test_whole_parser(directory,raw,ok):
    out,_,_=run(directory,Fake([tool(),reply([{'type':'text','text':raw}])]))
    assert (out['terminal_disposition']=='success')==ok
    assert 'validation_failure_count' in terminal(directory)['payload']['parse_diagnostics']
def test_core_ambiguity_and_limits():
    schema={'type':'object','properties':{'x':{'type':'integer'}},'required':['x'],'additionalProperties':False}
    assert parse_structured('{"x":1}',schema).diagnostics.schema_valid_count==1
    with pytest.raises(StructuredOutputError) as e:parse_structured('{"x":1} {"x":1}',schema,allow_salvage=True,best_effort=True)
    assert e.value.diagnostics.reason=='ambiguous' and e.value.diagnostics.candidate_count==2
    for raw,limits,reason in [('{}',{'max_input_bytes':1},'byte_limit'),('{"x":[[1]]}',{'max_depth':2},'depth_limit')]:
        with pytest.raises(StructuredOutputError) as error:parse_structured(raw,schema,**limits)
        assert error.value.diagnostics.reason==reason
@pytest.mark.parametrize('change',['readiness','missing','duplicate_rule','citation_id','quote','reason','identity','conflict'])
def test_task_invariants(directory,change):
    t=copy.deepcopy(TASK)
    if change=='readiness':t['readiness']='needs_clarification'
    if change=='missing':t['missing_requirement_ids']=['R-OBJECTIVE']
    if change=='duplicate_rule':t['assessments'][1]['rule_id']='R-OBJECTIVE'
    if change=='citation_id':t['assessments'][0]['citations'][0]['statement_id']='S99'
    if change=='quote':t['assessments'][0]['citations'][0]['quote']='invented'
    if change=='reason':t['assessments'][0]['reason']=' '
    if change=='identity':t['invocation_id']='forged'
    if change=='conflict':t['assessments'][2]['met']=False;t['missing_requirement_ids']=['R-CONSISTENCY'];t['readiness']='needs_clarification'
    assert run(directory,Fake([tool(),final(t)]))[0]['terminal_disposition'] in ('schema_invalid','parse_failed')
def test_clarification_control(directory):
    t=copy.deepcopy(TASK);t['readiness']='needs_clarification';t['missing_requirement_ids']=['R-ACCEPTANCE'];t['assessments'][1]['met']=False
    assert run(directory,Fake([tool(),final(t)]))[0]['terminal_disposition']=='success'
@pytest.mark.parametrize('stop',['max_tokens','refusal','pause_turn','unknown',None])
def test_stop_fail_closed(directory,stop):
    bad=final();bad['stop_reason']=stop
    assert run(directory,Fake([tool(),bad]))[0]['terminal_disposition']=='provider_error'
@pytest.mark.parametrize('block',[{'type':'thinking','thinking':'secret reasoning'},{'type':'unknown'},{'type':'text','text':''}])
def test_blocks_and_empty_refusal(directory,block):
    assert run(directory,Fake([tool(),reply([block])]))[0]['terminal_disposition']=='provider_error'
    assert 'secret reasoning' not in (directory/'evidence.jsonl').read_text()
def test_policy_required(directory):assert run(directory,Fake([final()]))[0]['terminal_disposition']=='tool_error'
@pytest.mark.parametrize('usage',[{}, {'input_tokens':True,'output_tokens':2},{'input_tokens':-1,'output_tokens':2},{'input_tokens':1,'output_tokens':float('nan')},{'input_tokens':{'invalid':float('nan')},'output_tokens':1},{'input_tokens':1,'output_tokens':2,'cache_read_input_tokens':10}])
def test_unknown_usage(directory,usage):
    out,fake,_=run(directory,Fake([reply([{'type':'text','text':'x'}],usage=usage)]));rec=terminal(directory)
    assert out['terminal_disposition']=='provider_error' and rec['model_attempts']==1 and rec['tokens_used']==201024
    assert rec['payload']['usage_status']=='unknown' and len(fake.requests)==1
@pytest.mark.parametrize('error,disposition',[(RuntimeError('synthetic-provider-fault'),'provider_error'),(asyncio.CancelledError(),'cancelled'),(asyncio.TimeoutError(),'budget_exhausted')])
def test_fault_accounted_once(directory,error,disposition):
    out,fake,_=run(directory,Fake([error]));rec=terminal(directory)
    assert out['terminal_disposition']==disposition and rec['model_attempts']==1
    assert rec['payload']['usage_status']=='unknown' and len(fake.requests)==1
@pytest.mark.parametrize('count',[8001,-1,True])
def test_preflight_reject(directory,count):
    out,fake,_=run(directory,Fake(count=count));assert out['terminal_disposition']!='success' and not fake.requests and terminal(directory)['model_attempts']==0
def test_count_boundary_control(directory):assert run(directory,Fake(count=8000))[0]['terminal_disposition']=='success'
@pytest.mark.parametrize('key,value,expected',[('max_model_attempts',1,'model_attempt_limit'),('max_tool_iterations',0,'budget_tool_iterations'),('max_tokens',201023,'prospective_tokens'),('max_spend',.205119,'prospective_spend'),('max_wall_seconds',0,'budget_wall_time')])
def test_invocation_ceiling(directory,monkeypatch,key,value,expected):
    monkeypatch.setitem(r.CONFIG['invocation'],key,value);out,_,_=run(directory)
    assert out['terminal_disposition']=='budget_exhausted' and out['error']['code']==expected
@pytest.mark.parametrize('kind',['model','tool','tokens','spend','deadline'])
def test_campaign_ceiling(directory,kind):
    c=r.Campaign(directory)
    if kind in ('model','tokens','spend'):
        for i in range(24 if kind=='model' else 1):
            c.event('reserve',attempt_id=f'seed-{i}');c.event('usage',attempt_id=f'seed-{i}',status='known',input_tokens=300000 if kind=='tokens' else 1,output_tokens=0,spend_micros=800000 if kind=='spend' else 1)
    if kind=='tool':
        for i in range(16):c.event('tool_dispatch',request_id=f'seed-{i}')
    if kind=='deadline':
        events=[json.loads(x) for x in c.path.read_text().splitlines()];events[0]['started_epoch']-=901;c.path.write_text('\n'.join(json.dumps(x) for x in events)+'\n')
    out,fake,_=run(directory);assert out['terminal_disposition']=='budget_exhausted'
    if kind!='tool':assert not fake.requests
def test_two_tools_then_third_denied(directory):
    response=tool('1');response['content']+=tool('2')['content']+tool('3')['content']
    assert run(directory,Fake([response]))[0]['terminal_disposition']=='budget_exhausted'
    assert terminal(directory)['model_attempts']==1 and terminal(directory)['tool_iterations']==2
def test_provider_bound(directory):
    bad=tool();bad['usage']['output_tokens']=1025
    assert run(directory,Fake([bad]))[0]['terminal_disposition']=='budget_exhausted'
def test_equality_no_success(directory,monkeypatch):
    monkeypatch.setitem(r.CONFIG['invocation'],'max_spend',.20512);bad=tool();bad['usage'].update(input_tokens=200000,output_tokens=1024)
    assert run(directory,Fake([bad]))[0]['terminal_disposition']=='budget_exhausted'
def test_campaign_survives_invocations(directory):
    assert run(directory)[0]['invocation_id']!=run(directory)[0]['invocation_id']
    assert terminal(directory)['payload']['campaign_snapshot']['model_attempts']==4
def test_unknown_reservation_blocks(directory):
    r.Campaign(directory).event('reserve',attempt_id='unresolved');out,fake,_=run(directory)
    assert out['error']['code']=='unresolved_usage_reservation' and not fake.requests
def test_failure_blocks_next(directory):
    run(directory,Fake([RuntimeError()]));out,fake,_=run(directory)
    assert out['error']['code']=='campaign_stopped' and not fake.requests
def test_reset_denied(directory):
    with pytest.raises(FileExistsError):r.Campaign.initialize(directory)
def test_persistence_failure(directory,monkeypatch):
    original=r.append_json
    def fail(path,value):
        if path.name=='evidence.jsonl':raise r.StorageError('simulated_disk_error')
        return original(path,value)
    monkeypatch.setattr(r,'append_json',fail);out,fake,emergency=run(directory)
    assert out['error']['code']=='persistence_failed' and out['evidence_ref'].startswith('stderr:') and emergency
    assert len(fake.requests)==1 and emergency[-1]['model_attempts']==1
def test_core_identity():
    import agent_core
    assert Path(agent_core.__file__).resolve()==Path(__import__('importlib.metadata',fromlist=['distribution']).distribution('agent-core').locate_file('agent_core/__init__.py')).resolve() and CORE_VERSION=='0.2.0'
def test_jsonl_readback(directory):
    path=directory/'control.jsonl';r.append_json(path,{'a':1});assert json.loads(path.read_text())=={'a':1};path.write_text('malformed\n')
    with pytest.raises(r.StorageError):r.append_json(path,{'b':2})


def test_native_final_request_shape(directory):
    out,fake,_=run(directory)
    assert fake.requests[1]['tools']==fake.requests[0]['tools']
    assert fake.requests[1]['tool_choice']=={'type':'none'}

def test_failed_tool_child(directory,monkeypatch):
    def failed(_policy_id=None,**kwargs):raise OSError('synthetic')
    monkeypatch.setattr(r,'get_policy',failed)
    out,_,_=run(directory)
    records=[json.loads(x) for x in (directory/'evidence.jsonl').read_text().splitlines()]
    assert out['terminal_disposition']=='tool_error'
    child=[x for x in records if x['payload']['record_kind']=='tool_execution']
    assert len(child)==1 and child[0]['disposition']=='tool_error'
    assert terminal(directory)['tool_iterations']==1

def test_load_hygiene_without_term_artifact(directory):
    terms=[x.strip() for x in r.EXCLUDE.read_text().splitlines() if x.strip() and not x.lstrip().startswith('#')]
    assert terms, 'hygiene source control must be populated'
    task=copy.deepcopy(TASK);task['assessments'][0]['reason']=terms[0]
    prelude=tool();prelude['content'].insert(0,{'type':'text','text':terms[0]})
    out,fake,_=run(directory,Fake([prelude,final(task)]))
    reused_clean=all(term.lower() not in r.encode(fake.requests[-1]).lower() for term in terms)
    assert reused_clean
    replaced=out['task_result']['assessments'][0]['reason']=='Haffey Enterprises'
    assert replaced
    assert terminal(directory)['payload']['model_text_sanitized'] is True
    # Boolean assertion keeps private terms out of failure diagnostics.
    clean=all(term.lower() not in (directory/'evidence.jsonl').read_text().lower() for term in terms)
    assert clean

def test_native_sdk_mock_wire(directory,monkeypatch):
    import anthropic,httpx2
    from transport import NativeAnthropic,count_request
    requests=[]
    synthetic_key=__import__('uuid').uuid4().hex
    async def handler(request):
        assert str(request.url).startswith('https://api.anthropic.com/')
        assert request.headers['x-api-key']==synthetic_key
        body=json.loads(request.content);requests.append((request.url.path,body))
        if request.url.path.endswith('/count_tokens'):
            return httpx2.Response(200,json={'input_tokens':100})
        body_response=tool() if len([p for p,_ in requests if p=='/v1/messages'])==1 else final()
        body_response.pop('request_id');body_response.update(type='message',role='assistant',stop_sequence=None)
        return httpx2.Response(200,json=body_response,headers={'request-id':'synthetic'})
    original=anthropic.DefaultAsyncHttpxClient
    def client(**kwargs):return original(**kwargs,transport=httpx2.MockTransport(handler))
    monkeypatch.setattr(anthropic,'DefaultAsyncHttpxClient',client)
    monkeypatch.setenv('ANTHROPIC_API_KEY',synthetic_key)
    monkeypatch.delenv('ANTHROPIC_CUSTOM_HEADERS',raising=False)
    monkeypatch.setenv('ANTHROPIC_BASE_URL','https://invalid.example')
    native=NativeAnthropic();native.simulated=True
    native_errors=[]
    original_create=native.create
    async def diagnostic_create(request,timeout):
        try:return await original_create(request,timeout)
        except Exception as error:
            import traceback
            native_errors.append(type(error).__name__)
            native_errors.extend(f'{x.filename}:{x.lineno}:{x.name}' for x in traceback.extract_tb(error.__traceback__))
            cause=error.__cause__
            if cause is not None:
                native_errors.append(type(cause).__name__)
                if hasattr(cause,'errors'):
                    native_errors.extend(str(x['loc'])+':'+x['type'] for x in cause.errors())
            raise
    native.create=diagnostic_create
    async def go():
        result=await r.invoke(BRIEF,transport=native,campaign_dir=directory)
        assert native.client.max_retries==0
        await native.close();return result
    result=asyncio.run(go())
    assert result['terminal_disposition']=='success',native_errors
    assert [p for p,_ in requests]==['/v1/messages/count_tokens','/v1/messages','/v1/messages/count_tokens','/v1/messages']
    for i in (0,2):assert requests[i][1]==count_request(requests[i+1][1])
    assert requests[-1][1]['tool_choice']=={'type':'none'}
    assert requests[-1][1]['output_config']['format']['schema']==r.SCHEMAS['native-task']
    assert synthetic_key not in (directory/'evidence.jsonl').read_text()
    # This is SDK serialization exercised over an in-memory HTTP transport, not provider evidence.

def test_actual_timeout_cancels_coroutine(directory,monkeypatch):
    monkeypatch.setitem(r.CONFIG['invocation'],'max_wall_seconds',.02)
    observed=[]
    async def pending():
        try:await asyncio.Event().wait()
        finally:observed.append('cancelled')
    out,_,_=run(directory,Fake([pending]))
    assert out['terminal_disposition']=='budget_exhausted' and observed==['cancelled']
    assert terminal(directory)['model_attempts']==1 and terminal(directory)['payload']['usage_status']=='unknown'

def test_external_cancellation_propagates(directory):
    entered=asyncio.Event();cancelled=[]
    async def pending():
        entered.set()
        try:await asyncio.Event().wait()
        finally:cancelled.append(True)
    async def go():
        task=asyncio.create_task(r.invoke(BRIEF,transport=Fake([pending]),campaign_dir=directory))
        await entered.wait();task.cancel();return await task
    assert asyncio.run(go())['terminal_disposition']=='cancelled' and cancelled==[True]
    assert terminal(directory)['model_attempts']==1

def test_campaign_invocation_count(directory):
    c=r.Campaign(directory)
    for i in range(8):
        c.event('invocation',invocation_id=f'seed-{i}');c.event('terminal',invocation_id=f'seed-{i}',disposition='success')
    out,fake,_=run(directory);assert out['error']['code']=='invocation_limit' and not fake.requests

def test_concurrency_lock(directory):
    with r.Campaign(directory):
        with pytest.raises(BlockingIOError):
            with r.Campaign(directory):pass

def test_core_model_attempt_limit_control():
    b=Budget(max_model_attempts=3)
    for _ in range(3):b.check('model');b.record_model_attempt(tokens=1,spend=0)
    with pytest.raises(BudgetExhausted) as error:b.check('model')
    assert error.value.dimension=='model_attempts'

def test_shared_token_equality_control():
    b=Budget(max_tokens=1);b.record_model_attempt(tokens=1,spend=0)
    assert b.snapshot().exhausted_shared()=='tokens'

def test_native_no_retry_http_failure(directory,monkeypatch):
    import anthropic,httpx2
    from transport import NativeAnthropic
    calls=[]
    async def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith('/count_tokens'):return httpx2.Response(200,json={'input_tokens':100})
        return httpx2.Response(500,json={'type':'error','error':{'type':'api_error','message':'synthetic failure'}})
    original=anthropic.DefaultAsyncHttpxClient
    monkeypatch.setattr(anthropic,'DefaultAsyncHttpxClient',lambda **kwargs:original(**kwargs,transport=httpx2.MockTransport(handler)))
    monkeypatch.setenv('ANTHROPIC_API_KEY',__import__('uuid').uuid4().hex)
    monkeypatch.delenv('ANTHROPIC_CUSTOM_HEADERS',raising=False)
    native=NativeAnthropic();native.simulated=True
    async def go():
        try:return await r.invoke(BRIEF,transport=native,campaign_dir=directory)
        finally:await native.close()
    out=asyncio.run(go())
    assert out['terminal_disposition']=='provider_error'
    assert calls==['/v1/messages/count_tokens','/v1/messages']
    assert terminal(directory)['model_attempts']==1 and terminal(directory)['payload']['usage_status']=='unknown'


def test_terminal_commit_failure_supersedes_success(directory,monkeypatch):
    original=r.Campaign.event
    def fail(self,kind,**fields):
        if kind=='terminal':raise r.StorageError('synthetic_terminal_commit_failure')
        return original(self,kind,**fields)
    monkeypatch.setattr(r.Campaign,'event',fail)
    out,_,emergency=run(directory)
    assert out['terminal_disposition']=='provider_error' and out['task_result'] is None
    persisted=terminal(directory)
    assert persisted['disposition']=='success'
    assert emergency[-1]['payload']['supersedes_record_id']==persisted['record_id']
    assert emergency[-1]['payload']['prior_record_persistence']=='confirmed'
