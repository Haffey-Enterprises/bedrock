"""One sequential specialist; all transport dependencies are injected for offline tests."""
from __future__ import annotations
import bootstrap
import asyncio, dataclasses, fcntl, hashlib, json, math, os, re, sys, time, uuid
from pathlib import Path
from jsonschema import Draft202012Validator
from agent_core import (Budget, BudgetExhausted, InvocationContext, emit_evidence,
    parse_structured, stamp_identity, StructuredOutputError, ParsePath, CORE_VERSION,
    ToolCapability, ToolRequest, ToolResult, ToolRegistry, check_capability,
    correlate_results, ToolLoopError, SecurityBoundary, SideEffectClass,
    AuthorizationError, TerminalDisposition as D, ContentKind)
from transport import count_request
ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'config-1.0.0.json').read_text())
SCHEMAS={name:json.loads((ROOT/'schemas'/f'{name}-1.0.0.json').read_text())
         for name in ('input','task','native-task','return','error','tool-input','tool-result')}
PROMPT=(ROOT/'prompts/system-1.0.0.txt').read_text()
RULES={'R-OBJECTIVE','R-ACCEPTANCE','R-CONSISTENCY'}
EXCLUDE=Path(os.environ['BEDROCK_HYGIENE_FILE'])
EVIDENCE_ROOT=Path(os.environ['BEDROCK_FIXTURE_EVIDENCE_ROOT']).resolve()

def digest(value):
    data=value if isinstance(value,bytes) else value.encode() if isinstance(value,str) else encode(value).encode()
    return hashlib.sha256(data).hexdigest()

def encode(value): return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)

def scrub(text):
    # Local work hygiene source; never record its content or embed its terms.
    for term in EXCLUDE.read_text().splitlines():
        term=term.strip()
        if term and not term.startswith('#'):
            text=re.sub(re.escape(term),'Haffey Enterprises',text,flags=re.IGNORECASE)
    return text

def validate(value, schema):
    if not Draft202012Validator(schema).is_valid(value):
        raise Halt(D.SCHEMA_INVALID,'schema_invalid')

class Halt(Exception):
    def __init__(self,disposition,code): self.disposition,self.code=disposition,code

class StorageError(Exception): pass

def append_json(path, value):
    """Durable append plus exact JSONL readback; no overwrite of observations."""
    line=encode(value)+'\n'
    try:
        with path.open('a',encoding='utf-8') as out:
            out.write(line);out.flush();os.fsync(out.fileno())
        with path.open(encoding='utf-8') as inp: lines=inp.readlines()
        if not lines or lines[-1] != line: raise StorageError('readback_mismatch')
        for item in lines: json.loads(item)
    except (OSError,ValueError) as error:
        raise StorageError('persistence_failed') from error

class Campaign:
    """Durable adapter journal; replay consumption through real core Budget APIs."""
    def __init__(self,directory):
        self.directory=Path(directory).resolve()
        if not self.directory.is_relative_to(EVIDENCE_ROOT): raise StorageError('evidence_location_denied')
        self.path=self.directory/'campaign.jsonl';self.lock=None;self.events=[]
        self.budget=None

    @classmethod
    def initialize(cls,directory):
        state=cls(directory);state.directory.mkdir(parents=True,exist_ok=True)
        # Exclusive creation prohibits silently resetting an existing campaign.
        with state.path.open('x',encoding='utf-8') as out:
            out.write(encode({'event':'init','campaign_id':str(uuid.uuid4()),
                'started_epoch':time.time(),'limits':CONFIG['campaign'],'max_invocations':CONFIG['max_invocations']})+'\n')
            out.flush();os.fsync(out.fileno())
        return state

    def __enter__(self):
        self.lock=(self.directory/'campaign.lock').open('a')
        try:
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (self.directory/'STOP').exists(): raise Halt(D.BUDGET_EXHAUSTED,'campaign_stopped')
            self.events=[json.loads(line) for line in self.path.read_text().splitlines()]
            if not self.events or self.events[0].get('event') != 'init': raise StorageError('invalid_campaign')
            init=self.events[0]
            if init['limits'] != CONFIG['campaign'] or init['max_invocations'] != CONFIG['max_invocations']:
                raise StorageError('campaign_config_changed')
            remaining=init['started_epoch']+CONFIG['campaign']['max_wall_seconds']-time.time()
            if remaining > CONFIG['campaign']['max_wall_seconds']:raise Halt(D.BUDGET_EXHAUSTED,'clock_rollback')
            self.budget=Budget(**{**CONFIG['campaign'],'max_wall_seconds':max(0,remaining)})
            reservations={e['attempt_id']:e for e in self.events if e['event']=='reserve'}
            completions={e['attempt_id']:e for e in self.events if e['event']=='usage'}
            for ident,event in reservations.items():
                usage=completions.get(ident)
                if usage is None or usage['status'] != 'known':
                    self.budget.record_model_attempt(tokens=201024,spend=.20512)
                    raise Halt(D.BUDGET_EXHAUSTED,'unresolved_usage_reservation')
                self.budget.record_model_attempt(tokens=usage['input_tokens']+usage['output_tokens'],spend=usage['spend_micros']/1e6)
            for event in self.events:
                if event['event']=='tool_dispatch':self.budget.record_tool_iteration()
                if event['event']=='terminal' and event['disposition'] != 'success':
                    raise Halt(D.BUDGET_EXHAUSTED,'campaign_previous_failure')
            starts={e['invocation_id'] for e in self.events if e['event']=='invocation'}
            ends={e['invocation_id'] for e in self.events if e['event']=='terminal'}
            if starts-ends:raise Halt(D.BUDGET_EXHAUSTED,'interrupted_invocation')
            if len(starts)>=CONFIG['max_invocations']:raise Halt(D.BUDGET_EXHAUSTED,'invocation_limit')
            self.budget.check('model')
            return self
        except BaseException:
            self.__exit__(None,None,None);raise

    def __exit__(self,*_):
        if self.lock:
            fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close();self.lock=None

    def event(self,kind,**fields):
        event={'event':kind,'epoch':time.time(),**fields}
        append_json(self.path,event);self.events.append(event)

    def stop(self):
        try:
            with (self.directory/'STOP').open('a') as file:file.write('failed\n');file.flush();os.fsync(file.fileno())
        except OSError: pass # The returned emergency record explicitly reports persistence failure.

    def remaining(self,invocation):
        return min(invocation.max_wall_seconds-invocation.snapshot().elapsed_seconds,
                   self.budget.max_wall_seconds-self.budget.snapshot().elapsed_seconds)

    def admit(self,invocation,kind):
        invocation.check(kind);self.budget.check(kind)
        if kind=='model':
            for budget in (invocation,self.budget):
                snap=budget.snapshot()
                if snap.max_tokens-snap.tokens_used<201024:raise Halt(D.BUDGET_EXHAUSTED,'prospective_tokens')
                if round((snap.max_spend-snap.spend_used)*1e6)<205120:raise Halt(D.BUDGET_EXHAUSTED,'prospective_spend')


def statements(brief):
    # Canonical IDs are application-owned, including briefs with supplied markers.
    pieces=re.split(r'\[S\d+\]',brief)
    pieces=[p.strip() for p in pieces if p.strip()]
    return {f'S{i}':text for i,text in enumerate(pieces or [brief],1)}


def verify_task(task,st):
    validate(task,SCHEMAS['task'])
    assessments=task['assessments']
    if {a['rule_id'] for a in assessments} != RULES or len(assessments)!=3:
        raise Halt(D.SCHEMA_INVALID,'rule_set_mismatch')
    missing={a['rule_id'] for a in assessments if not a['met']}
    if set(task['missing_requirement_ids']) != missing:raise Halt(D.SCHEMA_INVALID,'missing_set_mismatch')
    if (task['readiness']=='ready') != (not missing):raise Halt(D.SCHEMA_INVALID,'readiness_mismatch')
    for a in assessments:
        if not a['reason'].strip():raise Halt(D.SCHEMA_INVALID,'empty_reason')
        ids=set()
        for c in a['citations']:
            if c['statement_id'] not in st or not c['quote'].strip() or c['quote'] not in st[c['statement_id']]:
                raise Halt(D.SCHEMA_INVALID,'ungrounded_citation')
            ids.add(c['statement_id'])
        if a['rule_id']=='R-CONSISTENCY' and not a['met'] and len(ids)<2:
            raise Halt(D.SCHEMA_INVALID,'conflict_needs_two_statements')


def get_policy(policy_id):
    if policy_id!='readiness-v1':raise ToolLoopError('unknown_policy')
    data=json.loads(scrub((ROOT/'policy.json').read_text()))
    validate(data,SCHEMAS['tool-result']);return data


def usage_of(response):
    u=response.get('usage')
    if not isinstance(u,dict):return None
    for k in ('input_tokens','output_tokens'):
        if type(u.get(k)) is not int or u[k]<0:return None
    for k in ('cache_creation_input_tokens','cache_read_input_tokens'):
        if u.get(k) not in (None,0):return None
    return {'input_tokens':u['input_tokens'],'output_tokens':u['output_tokens'],
            'spend_micros':u['input_tokens']+5*u['output_tokens']}


def safe_response(response):
    """Persist permitted synthetic blocks only, even for injected fixture transports."""
    if not isinstance(response,dict):return {'invalid_response_type':type(response).__name__}
    result={k:response.get(k) for k in ('id','request_id','model','stop_reason')}
    usage=response.get('usage')
    fields=('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')
    result['usage']={k:usage.get(k) for k in fields} if isinstance(usage,dict) else {'invalid_type':type(usage).__name__}
    blocks=response.get('content')
    result['content']=[]
    if isinstance(blocks,list):
        for b in blocks:
            if not isinstance(b,dict):result['content'].append({'type':'invalid'});continue
            allowed=('type','text') if b.get('type')=='text' else ('type','id','name','input') if b.get('type')=='tool_use' else ('type',)
            result['content'].append({k:b[k] for k in allowed if k in b})
    def content_safe(value,depth=0):
        if depth>64:return {'invalid_type':'depth_limit'}
        if value is None or isinstance(value,(str,bool,int)):return value
        if isinstance(value,float):return value if math.isfinite(value) else {'invalid_type':'nonfinite_number'}
        if isinstance(value,list):return [content_safe(x,depth+1) for x in value]
        if isinstance(value,dict):return {str(k):content_safe(v,depth+1) for k,v in value.items()}
        return {'invalid_type':type(value).__name__}
    return json.loads(scrub(encode(content_safe(result))))

async def invoke(input_value,*,transport,campaign_dir,emergency=None):
    """Callable fixture/fleet seam. Production caller supplies NativeAnthropic explicitly."""
    ctx=InvocationContext(agent_id='requirements-readiness',session_id='HEB-154',
        project_id='HEB-154',run_id='bounded-trial',agent_version='1.0.0')
    inv=Budget(**CONFIG['invocation']); campaign=Campaign(campaign_dir)
    evidence_path=campaign.directory/'evidence.jsonl'
    disposition=D.PROVIDER_ERROR;error='unhandled_error';task=None;parse_path=None
    diagnostics=None;raw_hash=digest(b'');children=[];usage_totals={'input_tokens':0,'output_tokens':0,'spend_micros':0}
    usage_status='known';st={};entered=False;started=False;terminal_record=None;sanitized=False;failed_tool=None
    boundary=SecurityBoundary()
    registry=ToolRegistry([ToolCapability('get_policy',SCHEMAS['tool-input'],SideEffectClass.NONE,True,'Read the fixed local readiness policy. Interface 1.0.0.')])
    requests_seen=[];results_seen=[]
    def persist(record):append_json(evidence_path,record.to_dict())
    def child(kind,disp,payload):
        rec=emit_evidence(ctx,disp,budget_snapshot=inv.snapshot(),payload={'record_kind':kind,**payload})
        children.append(rec.record_id);persist(rec)
    try:
        campaign.__enter__();entered=True
        campaign.event('invocation',invocation_id=ctx.invocation_id);started=True
        if isinstance(input_value,str):
            input_value=parse_structured(scrub(input_value),SCHEMAS['input'],allow_salvage=False).data
        else:
            input_value=json.loads(scrub(encode(input_value)))
        validate(input_value,SCHEMAS['input'])
        if not input_value['brief'].strip():raise Halt(D.SCHEMA_INVALID,'empty_brief')
        st=statements(input_value['brief'])
        messages=[{'role':'user','content':encode(boundary.tag(ContentKind.USER,{'policy_id':input_value['policy_id'],'statements':st}))}]
        for attempt in range(1,CONFIG['invocation']['max_model_attempts']+1):
            campaign.admit(inv,'model')
            request={'model':CONFIG['model'],'max_tokens':1024,'temperature':0,
                'thinking':{'type':'disabled'},'stream':False,'system':PROMPT,'messages':messages.copy()}
            request['tools']=[{'name':'get_policy','description':'Read readiness-v1 local policy. Capability version 1.0.0; read-only and idempotent.','input_schema':SCHEMAS['tool-input']}]
            if not results_seen:
                request['tool_choice']={'type':'tool','name':'get_policy','disable_parallel_tool_use':True}
            else:
                request['tool_choice']={'type':'none'}
                request['output_config']={'format':{'type':'json_schema','schema':SCHEMAS['native-task']}}
            timeout=campaign.remaining(inv)
            if timeout<=0:raise Halt(D.BUDGET_EXHAUSTED,'deadline')
            campaign.event('preflight_dispatch',invocation_id=ctx.invocation_id,attempt=attempt,request=count_request(request),request_sha256=digest(count_request(request)))
            try:
                async with asyncio.timeout(timeout):count=await transport.count(request,timeout)
            except asyncio.TimeoutError:raise Halt(D.BUDGET_EXHAUSTED,'preflight_timeout')
            except asyncio.CancelledError:raise
            except Exception:raise Halt(D.PROVIDER_ERROR,'preflight_provider_error')
            campaign.event('preflight_result',invocation_id=ctx.invocation_id,attempt=attempt,input_tokens=count)
            if type(count) is not int or count<0:raise Halt(D.PROVIDER_ERROR,'invalid_preflight_count')
            if count>8000:raise Halt(D.BUDGET_EXHAUSTED,'preflight_input_limit')
            campaign.admit(inv,'model')
            timeout=campaign.remaining(inv)
            attempt_id=f'{ctx.invocation_id}:{attempt}'
            campaign.event('reserve',invocation_id=ctx.invocation_id,attempt_id=attempt_id,
                input_tokens=200000,output_tokens=1024,spend_micros=205120,
                request=request,request_sha256=digest(request),timeout=timeout)
            # The reservation precedes exactly this physical create call. No SDK retries.
            response=None;fault=None
            try:
                async with asyncio.timeout(timeout):response=await transport.create(request,timeout)
            except asyncio.CancelledError:fault='cancelled'
            except asyncio.TimeoutError:fault='timeout'
            except Exception:fault='provider_error'
            usage=usage_of(response) if isinstance(response,dict) else None
            if usage is None:
                usage_status='unknown'
                inv.record_model_attempt(tokens=201024,spend=.20512)
                campaign.budget.record_model_attempt(tokens=201024,spend=.20512)
                campaign.event('usage',attempt_id=attempt_id,status='unknown',accounting_basis='retained_reservation')
            else:
                inv.record_model_attempt(tokens=usage['input_tokens']+usage['output_tokens'],spend=usage['spend_micros']/1e6)
                campaign.budget.record_model_attempt(tokens=usage['input_tokens']+usage['output_tokens'],spend=usage['spend_micros']/1e6)
                campaign.event('usage',attempt_id=attempt_id,status='known',**usage)
                for k in usage_totals:usage_totals[k]+=usage[k]
            captured=safe_response(response)
            child('model_attempt',D.CANCELLED if fault=='cancelled' else D.PROVIDER_ERROR if fault or usage is None else D.SUCCESS,
                {'attempt':attempt,'attempt_id':attempt_id,'simulated':bool(transport.simulated),
                 'provider':'anthropic','model':CONFIG['model'],'request':request,'request_sha256':digest(request),
                 'response':captured,'response_sha256':digest(captured),
                 'original_text_block_sha256':[{'index':i,'sha256':digest(b['text'])} for i,b in enumerate(response.get('content',[])) if isinstance(b,dict) and b.get('type')=='text' and isinstance(b.get('text'),str)] if isinstance(response,dict) and isinstance(response.get('content'),list) else [],
                 'usage_status':usage_status,
                 'usage':usage,'fault':fault,'stop_reason':captured.get('stop_reason'),
                 'retry_cause':None,'timeout_seconds':timeout})
            if fault=='cancelled':raise Halt(D.CANCELLED,'cancelled_during_dispatch_usage_unknown')
            if fault=='timeout':raise Halt(D.BUDGET_EXHAUSTED,'dispatch_timeout_usage_unknown')
            if fault:raise Halt(D.PROVIDER_ERROR,fault)
            if usage is None:raise Halt(D.PROVIDER_ERROR,'unknown_usage')
            if usage['input_tokens']>200000 or usage['output_tokens']>1024:
                raise Halt(D.BUDGET_EXHAUSTED,'provider_usage_exceeds_reservation')
            for b in (inv,campaign.budget):
                if b.snapshot().exhausted_shared():raise Halt(D.BUDGET_EXHAUSTED,'shared_budget_exhausted')
            if response.get('model')!=CONFIG['model']:raise Halt(D.PROVIDER_ERROR,'model_identity_mismatch')
            stop=response.get('stop_reason');blocks=response.get('content')
            if not isinstance(blocks,list) or not blocks:raise Halt(D.PROVIDER_ERROR,'invalid_content')
            if stop not in ('tool_use','end_turn'):raise Halt(D.PROVIDER_ERROR,'unsupported_stop_reason')
            if any(not isinstance(b,dict) or b.get('type') not in ('text','tool_use') for b in blocks):raise Halt(D.PROVIDER_ERROR,'unsupported_content_block')
            if stop=='tool_use':
                if results_seen:raise Halt(D.TOOL_ERROR,'tool_request_when_disabled')
                calls=[]
                for b in blocks:
                    if b['type']=='text':
                        if not isinstance(b.get('text'),str):raise Halt(D.PROVIDER_ERROR,'invalid_text')
                        continue
                    if not isinstance(b.get('id'),str) or not b['id']:raise Halt(D.TOOL_ERROR,'invalid_tool_id')
                    req=ToolRequest(b['id'],b.get('name'),b.get('input'))
                    check_capability(registry,req.name,req.arguments)
                    calls.append(req)
                if not calls:raise Halt(D.TOOL_ERROR,'missing_tool_request')
                # Core rejects duplicates across previous rounds and this batch before dispatch.
                correlate_results(requests_seen+calls,results_seen)
                new_results=[]
                for req in calls:
                    campaign.admit(inv,'tool')
                    cap=check_capability(registry,req.name,req.arguments);boundary.authorize_tool(cap,req.arguments)
                    campaign.event('tool_dispatch',invocation_id=ctx.invocation_id,request_id=req.request_id,name=req.name,arguments=req.arguments)
                    inv.record_tool_iteration();campaign.budget.record_tool_iteration()
                    try:
                        value=get_policy(**req.arguments)
                    except Exception:
                        failed_tool={'attempt':attempt,'request_id':req.request_id,'name':req.name,'actual_dispatch':True,'error_code':'local_policy_failed'}
                        child('tool_execution',D.TOOL_ERROR,failed_tool)
                        raise Halt(D.TOOL_ERROR,'local_policy_failed')
                    result=ToolResult(req.request_id,req.name,True,value)
                    new_results.append(result)
                    try:
                        child('tool_execution',D.SUCCESS,{'attempt':attempt,'tool_request':dataclasses.asdict(req),'tool_result':dataclasses.asdict(result),'capability_version':'1.0.0','actual_dispatch':True})
                    except Exception:
                        failed_tool={'attempt':attempt,'request_id':req.request_id,'name':req.name,'actual_dispatch':True,'execution_status':'completed','evidence_status':'persistence_failed'}
                        raise
                requests_seen+=calls;results_seen+=new_results
                ordered=correlate_results(requests_seen,results_seen)
                if len(ordered)!=len(requests_seen):raise Halt(D.TOOL_ERROR,'missing_tool_result')
                messages.append({'role':'assistant','content':captured['content']})
                messages.append({'role':'user','content':[{'type':'tool_result','tool_use_id':r.request_id,'content':encode(boundary.tag(ContentKind.TOOL_RESULT,r.content))} for r in new_results]})
                continue
            if any(b['type']!='text' for b in blocks):raise Halt(D.PROVIDER_ERROR,'end_turn_with_tool')
            if len(blocks)!=1 or not isinstance(blocks[0].get('text'),str):raise Halt(D.PROVIDER_ERROR,'invalid_final_blocks')
            if not results_seen:raise Halt(D.TOOL_ERROR,'policy_tool_required')
            original_raw=blocks[0]['text'];raw_hash=digest(original_raw)
            raw=scrub(original_raw);sanitized=raw!=original_raw
            if not raw.strip():raise Halt(D.PROVIDER_ERROR,'empty_final_refusal')
            parsed=parse_structured(raw,SCHEMAS['task'],allow_salvage=False,best_effort=False)
            parse_path=parsed.parse_path;diagnostics=dataclasses.asdict(parsed.diagnostics)
            verify_task(parsed.data,st)
            stamped=stamp_identity(parsed.data,ctx.identity_map())
            task={k:stamped[k] for k in SCHEMAS['task']['properties']}
            disposition=D.SUCCESS;error=None;break
        else:raise Halt(D.BUDGET_EXHAUSTED,'model_attempt_limit')
    except StructuredOutputError as exc:
        disposition=D.PARSE_FAILED;error='structured_output_failed';parse_path=exc.parse_path;diagnostics=dataclasses.asdict(exc.diagnostics)
    except BudgetExhausted as exc:disposition=D.BUDGET_EXHAUSTED;error='budget_'+exc.dimension
    except Halt as exc:disposition,error=exc.disposition,exc.code
    except AuthorizationError:disposition=D.TOOL_DENIED;error='authorization_denied'
    except ToolLoopError:disposition=D.TOOL_ERROR;error='tool_contract_failed'
    except asyncio.CancelledError:disposition=D.CANCELLED;error='cancelled'
    except StorageError:disposition=D.PROVIDER_ERROR;error='persistence_failed'
    except Exception:disposition=D.PROVIDER_ERROR;error='internal_error'
    finally:
        if disposition != D.SUCCESS:task=None
        if disposition==D.SUCCESS:
            if inv.snapshot().exhausted_shared() or campaign.budget.snapshot().exhausted_shared():
                disposition=D.BUDGET_EXHAUSTED;error='deadline_or_shared_limit_at_terminal';task=None
        payload={'record_kind':'invocation','simulated':bool(transport.simulated),'provider':'anthropic',
            'profile':'direct-messages-1.0.0','model':CONFIG['model'],'prompt_version':'1.0.0','prompt_sha256':digest(PROMPT),
            'schema_version':'1.0.0','schema_sha256':digest((ROOT/'schemas/task-1.0.0.json').read_bytes()),
            'core_import':bootstrap.agent_core.__file__,'core_version':CORE_VERSION,'children':children,
            'parse_diagnostics':diagnostics,'response_text_sha256':raw_hash,'model_text_sanitized':sanitized,'failed_tool_observation':failed_tool,'usage_status':usage_status,
            'known_usage':usage_totals,'accounting_basis':'actual' if usage_status=='known' else 'actual_plus_retained_reservation',
            'error_code':error,'budget_remaining':dataclasses.asdict(inv.snapshot()),
            'campaign_snapshot':dataclasses.asdict(campaign.budget.snapshot()) if campaign.budget else None}
        terminal_record=emit_evidence(ctx,disposition,parse_path=parse_path,budget_snapshot=inv.snapshot(),payload=payload)
        ref=f'{evidence_path}#{terminal_record.record_id}'
        prior_persisted=False
        try:
            persist(terminal_record);prior_persisted=True
            if started:campaign.event('terminal',invocation_id=ctx.invocation_id,disposition=disposition.value,evidence_id=terminal_record.record_id)
        except Exception:
            disposition=D.PROVIDER_ERROR;error='persistence_failed';task=None
            terminal_record=emit_evidence(ctx,disposition,parse_path=parse_path,budget_snapshot=inv.snapshot(),payload={**payload,'error_code':error,'persistence_status':'failed','supersedes_record_id':terminal_record.record_id,'prior_record_persistence':'confirmed' if prior_persisted else 'unknown'})
            ref='stderr:'+terminal_record.record_id
            (emergency or (lambda rec: print(encode(rec),file=sys.stderr)))(terminal_record.to_dict())
        if disposition!=D.SUCCESS:campaign.stop()
        if entered:campaign.__exit__(None,None,None)
    envelope=stamp_identity({'version':'1.0.0','evidence_ref':ref,'terminal_disposition':disposition.value,'task_result':task,'error':None if error is None else {'code':error}},ctx.identity_map(),identity_keys=('invocation_id',))
    validate(envelope,SCHEMAS['return'])
    return envelope
