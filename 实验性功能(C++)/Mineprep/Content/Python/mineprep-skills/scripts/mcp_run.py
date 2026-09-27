"""Unreal MCP HTTP fallback, Python 3.11+. No retries, configuration writes or reset.

Run with --project <directory> and either --code <Python> or --file <UTF-8 file>.
Use --url to override the project's .codex/config.toml Unreal MCP URL.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import socket
import sys
import time
import tomllib
import urllib.error
import urllib.request


class BridgeError(Exception):
    def __init__(self, kind, message, *, uncertain=False):
        super().__init__(message)
        self.kind = kind
        self.uncertain = uncertain


def configured_url(project):
    config_path = Path(project) / '.codex' / 'config.toml'
    try:
        config = tomllib.loads(config_path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise BridgeError('configuration_error', f'Cannot read {config_path}: {exc}') from exc
    servers = config.get('mcp_servers', {})
    if not isinstance(servers, dict):
        raise BridgeError('configuration_error', 'mcp_servers must be a table.')
    server = servers.get('unreal-mcp', {})
    if isinstance(server, dict) and server.get('url'):
        return server['url']
    urls = [s['url'] for name, s in servers.items()
            if 'unreal' in name.lower() and isinstance(s, dict) and s.get('url')]
    if len(urls) == 1:
        return urls[0]
    raise BridgeError('configuration_error', 'No unambiguous Unreal MCP URL; supply --url.')


def _project_key(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


class MCPClient:
    def __init__(self, url, timeout=30):
        if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            raise BridgeError('configuration_error', 'MCP URL must use http:// or https://.')
        self.url = url
        self.timeout = timeout
        self.headers = {'Content-Type': 'application/json',
                        'Accept': 'application/json, text/event-stream'}
        self.next_id = 0

    def rpc(self, method, params=None, *, notification=False, submitted=False):
        self.next_id += 1
        request_id = self.next_id
        body = {'jsonrpc': '2.0', 'method': method}
        if not notification:
            body['id'] = request_id
        if params is not None:
            body['params'] = params
        request = urllib.request.Request(
            self.url, json.dumps(body, ensure_ascii=False).encode('utf-8'), self.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                session = response.headers.get('Mcp-Session-Id')
                if session:
                    self.headers['Mcp-Session-Id'] = session
                if notification:
                    return None
                if 'text/event-stream' in response.headers.get('Content-Type', ''):
                    result = self._read_sse(response, request_id, self.timeout)
                else:
                    raw = response.read(8_000_001)
                    if len(raw) > 8_000_000:
                        raise ValueError('MCP response exceeds client transport limit')
                    result = json.loads(raw.decode('utf-8'))
                if not isinstance(result, dict) or result.get('id') != request_id:
                    raise ValueError('Mismatched JSON-RPC response')
        except (urllib.error.URLError, OSError, socket.timeout) as exc:
            raise BridgeError('connection_error', str(exc), uncertain=submitted) from exc
        except (ValueError, UnicodeError) as exc:
            raise BridgeError('protocol_error', str(exc), uncertain=submitted) from exc
        if 'error' in result:
            raise BridgeError('mcp_error', str(result['error']), uncertain=submitted)
        if 'result' not in result:
            raise BridgeError('protocol_error', 'Missing JSON-RPC result', uncertain=submitted)
        return result['result']

    @staticmethod
    def _read_sse(response, request_id, timeout=30):
        data = []
        size = 0
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('MCP event stream timed out')
            raw = response.readline(8_000_001)
            size += len(raw)
            if size > 8_000_000:
                raise ValueError('MCP event stream exceeds client transport limit')
            if not raw:
                raise ValueError('MCP event stream ended without a result')
            line = raw.decode('utf-8').rstrip('\r\n')
            if not line and data:
                event = json.loads('\n'.join(data))
                data.clear()
                if isinstance(event, dict) and event.get('id') == request_id:
                    return event
            elif line.startswith('data:'):
                data.append(line[5:].lstrip(' '))

    def connect(self):
        result = self.rpc('initialize', {
            'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'mineprep-skill', 'version': '1.0'}})
        if not isinstance(result, dict) or not isinstance(result.get('protocolVersion'), str):
            raise BridgeError('protocol_error', 'Missing negotiated protocol version')
        self.headers['MCP-Protocol-Version'] = result['protocolVersion']
        self.rpc('notifications/initialized', notification=True)
        names = set()
        cursor = None
        seen = set()
        while True:
            listing = self.rpc('tools/list', {'cursor': cursor} if cursor else {})
            if not isinstance(listing, dict) or not isinstance(listing.get('tools'), list):
                raise BridgeError('protocol_error', 'Invalid tools/list result')
            for item in listing['tools']:
                if not isinstance(item, dict) or not isinstance(item.get('name'), str):
                    raise BridgeError('protocol_error', 'Invalid tools/list entry')
                names.add(item['name'])
            cursor = listing.get('nextCursor')
            if not cursor:
                break
            if not isinstance(cursor, str):
                raise BridgeError('protocol_error', 'Invalid tools/list cursor')
            if cursor in seen:
                raise BridgeError('protocol_error', 'Repeated tools/list cursor')
            seen.add(cursor)
        if not {'call_tool', 'describe_toolset'} <= names:
            raise BridgeError('mcp_error', 'Unreal call_tool / describe_toolset unavailable')
        schema = self.tool('describe_toolset', {'toolset_name': 'mcptools.PythonTools'})
        entries = schema.get('tools') if isinstance(schema, dict) else None
        if not isinstance(entries, list) or not any(
                isinstance(t, dict) and isinstance(t.get('name'), str)
                and t['name'].split('.')[-1] == 'run' for t in entries):
            raise BridgeError('mcp_error', 'mcptools.PythonTools.run unavailable')

    def tool(self, name, arguments, *, submitted=False):
        response = self.rpc('tools/call', {'name': name, 'arguments': arguments},
                            submitted=submitted)
        if not isinstance(response, dict):
            raise BridgeError('protocol_error', 'Invalid MCP tool envelope', uncertain=submitted)
        if response.get('isError'):
            raise BridgeError('mcp_error', str(response.get('content', [])), uncertain=submitted)
        try:
            for block in response.get('content', []):
                if block.get('type') == 'text':
                    return json.loads(block['text'])
            raise ValueError('Missing text result')
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise BridgeError('protocol_error', 'Cannot decode Unreal tool result',
                              uncertain=submitted) from exc

    def run(self, code, loglevel=0, *, submitted=False):
        result = self.tool('call_tool', {
            'toolset_name': 'mcptools.PythonTools', 'tool_name': 'run',
            'arguments': {'code': code, 'loglevel': loglevel}}, submitted=submitted)
        try:
            value = result['returnValue']
            value = json.loads(value) if isinstance(value, str) else value
            if not isinstance(value, dict) or not {'ok', 'result', 'logs', 'error'} <= value.keys():
                raise ValueError('Missing Python result fields')
            return value
        except (KeyError, ValueError, TypeError) as exc:
            raise BridgeError('protocol_error', 'Cannot decode Python bridge result',
                              uncertain=submitted) from exc


def execute(project, code, *, url=None, timeout=30, loglevel=0):
    project = Path(project).resolve()
    if not project.is_dir() or not code.strip():
        raise BridgeError('input_error', 'Provide an existing project directory and nonempty code.')
    client = MCPClient(url or configured_url(project), timeout)
    client.connect()
    identity = client.run('unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())')
    if not identity['ok'] or not isinstance(identity['result'], str):
        raise BridgeError('project_error', 'Cannot establish editor project identity.')
    if _project_key(identity['result']) != _project_key(str(project)):
        raise BridgeError('project_mismatch',
                          f"Editor project {identity['result']} differs from {project}; code not submitted.")
    result = client.run(code, loglevel, submitted=True)
    # Python exceptions may follow partial side effects. Never retry them either.
    result['error_kind'] = None if result['ok'] else 'python_error'
    result['outcome'] = 'completed' if result['ok'] else 'execution_failed'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--url')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--code')
    source.add_argument('--file', type=Path)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--loglevel', type=int, choices=(0, 1, 2, 3), default=0)
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise BridgeError('input_error', '--timeout must be positive.')
        code = args.file.read_text(encoding='utf-8-sig') if args.file else args.code
        result = execute(args.project, code, url=args.url,
                         timeout=args.timeout, loglevel=args.loglevel)
    except (OSError, UnicodeError) as exc:
        result = {'ok': False, 'result': None, 'logs': [], 'error': str(exc),
                  'error_kind': 'input_error', 'outcome': 'not_submitted'}
    except BridgeError as exc:
        result = {'ok': False, 'result': None, 'logs': [], 'error': str(exc),
                  'error_kind': exc.kind,
                  'outcome': 'uncertain' if exc.uncertain else 'not_submitted'}
    # ASCII JSON is safe in GBK consoles; the input and HTTP body remain UTF-8.
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
