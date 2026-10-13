"""Direct native Messages adapter. No provider operation occurs on import."""
import os

COUNT_KEYS = {'messages','model','system','thinking','tool_choice','tools','output_config'}

def count_request(request):
    return {k:v for k,v in request.items() if k in COUNT_KEYS}

class NativeAnthropic:
    simulated = False
    def __init__(self):
        self.client = None

    def _client(self):
        if self.client is None:
            from identity import verify_binding
            verify_binding()
            key = os.environ.get('ANTHROPIC_API_KEY')
            if not key:
                raise RuntimeError('missing_explicit_api_key')
            # SDK 1.8.0 merges custom headers from env; disallow that override.
            if 'ANTHROPIC_CUSTOM_HEADERS' in os.environ:
                raise RuntimeError('custom_headers_not_allowed')
            from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient
            self.client = AsyncAnthropic(
                api_key=key, base_url='https://api.anthropic.com',
                webhook_key='', max_retries=0, _token_cache=None,
                http_client=DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False),
                _strict_response_validation=True,
            )
        return self.client

    async def count(self, request, timeout):
        result = await self._client().messages.count_tokens(**count_request(request), timeout=timeout)
        return result.input_tokens

    async def create(self, request, timeout):
        parameters=dict(request)
        temperature=parameters.pop('temperature')
        result = await self._client().messages.create(**parameters, extra_body={'temperature':temperature}, timeout=timeout)
        # Never persist raw SDK objects, headers, error bodies, or reasoning.
        blocks=[]
        for block in result.content:
            if block.type == 'text':
                blocks.append({'type':'text','text':block.text})
            elif block.type == 'tool_use':
                blocks.append({'type':'tool_use','id':block.id,'name':block.name,'input':block.input})
            else:
                blocks.append({'type':block.type})
        u=result.usage
        return {'id':result.id,'request_id':getattr(result,'_request_id',None),
                'model':result.model,'stop_reason':result.stop_reason,'content':blocks,
                'usage':{'input_tokens':u.input_tokens,'output_tokens':u.output_tokens,
                         'cache_creation_input_tokens':getattr(u,'cache_creation_input_tokens',None),
                         'cache_read_input_tokens':getattr(u,'cache_read_input_tokens',None)}}

    async def close(self):
        if self.client is not None:
            await self.client.close()
