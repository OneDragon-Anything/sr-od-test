"""MysClient 正常路径与登出单测（landing §3.2 判据逐条；全部 mock http_send
剧本式，零真实网络，落盘走 pytest tmp_path）。

锁的设计约定（design.md §2.2 mys_client / landing §3.2）：
- 构造三参必填无默认（缺任一 TypeError）；
- 登录成功：Set-Cookie 登录响应层名单（10 项）入罐 + save_session_full 整体
  覆盖落盘（产物无 expired 键）+ role.json 清除；acw_tc 等滚动件为第二层
  （滚动后 jar ⊇ 登录名单 + 滚动件，两集合分别对账）；
- 先 mark_expired 再登录成功 → 产物无 expired 键（标记随整体覆盖消失）；
- -3208/-3235/未知码（含首轮不可能出现的 -3102/-3202）→ MysApiError 且不落
  盘不清文件；
- request()：相对路径拼基座、绝对 URL 直用、白名单外主机 ValueError、DS2 按
  q 排序 + URL 编码（测试内独立重算签名串校验）、SESSION_EXPIRED_RETCODES
  各码 → MysSessionExpired（用例参数直接从 mys_session 导出的常量生成）、
  1034 → 裸 MysApiError(1034)、响应 Set-Cookie 滚动入罐保留 expired 标记；
- logout()：session.json 与 role.json 删除、device.json 保留、内存罐清空、
  幂等；
- 密码与 cookie 不出现在任何落盘文件（session.json 为 cookie 唯一指定居所）
  与异常文本。

验证分支（aigis 挑战解析）的实现归本阶段、其行为测试归 landing §3.3 的
test_mys_client_aigis.py，本文件不重复覆盖。
"""

import base64
import hashlib
import json
import threading
from pathlib import Path

import pytest

from one_dragon.mys.mys_client import MysClient
from one_dragon.mys.mys_const import (
    GAME_RECORD_BASE_URL,
    GET_FP_URL,
    LOGIN_SALT,
    LOGIN_URL,
    RECORD_SALT,
    USER_AGENT_DESKTOP_CHROME,
)
from one_dragon.mys.mys_device import DeviceIdentity
from one_dragon.mys.mys_http import HttpSendResult
from one_dragon.mys.mys_session import (
    DEVICE_FILE_NAME,
    ROLE_FILE_NAME,
    SESSION_EXPIRED_RETCODES,
    SESSION_FILE_NAME,
    MysApiError,
    MysSessionExpired,
    SessionStore,
)

_VALID_FP = 'abcdef123456'
_USERNAME = 'fixture_user'
_PASSWORD = 'SECRET-PW-fixture-777'

#: 登录响应层 Set-Cookie 名单（10 项）。口径 = 2026-11-03 实测流量校对记录
#: （teyvat-resin-planner .private/trace.log 登录条目，即 miyoushe-api-flow.md
#: §2.5 引用的登录下发层）；acw_tc 属会话滚动件、不在登录响应层，滚动件断言
#: 见 test_login_session_rolls_into_full_jar。
LOGIN_SET_COOKIES: dict[str, str] = {
    'aliyungf_tc': 'tc-fixture-value',
    'uni_web_token': 'uni-fixture-value',
    'cookie_token_v2': 'ct2-fixture-value',
    'account_mid_v2': 'mid2-fixture-value',
    'account_id_v2': 'aid2-fixture-value',
    'ltoken_v2': 'lt2-fixture-value',
    'ltmid_v2': 'ltm2-fixture-value',
    'ltuid_v2': 'ltu2-fixture-value',
    'account_id': 'aid-fixture-value',
    'ltuid': 'ltu-fixture-value',
}


class _ScriptedHttpSend:
    """剧本式假发送（零网络）：按「URL 前缀 → 响应」注册表首匹配分流，
    未命中即断言失败（防剧本漏路由静默通过）；记录全部调用供断言。"""

    def __init__(self, *routes: tuple[str, HttpSendResult]) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []
        self._routes: dict[str, HttpSendResult] = dict(routes)

    def add_route(self, *routes: tuple[str, HttpSendResult]) -> None:
        """登记路由；同前缀再登记即覆盖（测试中途改剧本用）。"""
        for route_prefix, result in routes:
            self._routes[route_prefix] = result

    def __call__(
        self, url: str, method: str, headers: dict[str, str], body: bytes | None
    ) -> HttpSendResult:
        self.calls.append((url, method, dict(headers), body))
        for route_prefix, result in self._routes.items():
            if url.startswith(route_prefix):
                return result
        raise AssertionError(f'剧本外请求（测试剧本缺路由）: {method} {url}')

    def calls_for(self, prefix: str) -> list[tuple[str, str, dict[str, str], bytes | None]]:
        return [call for call in self.calls if call[0].startswith(prefix)]


def _json_result(payload: dict, set_cookie_lines: list[str] | None = None) -> HttpSendResult:
    """构造业务 JSON 响应（按需附 Set-Cookie 行）。"""
    headers: list[tuple[str, str]] = [('Content-Type', 'application/json')]
    headers.extend(('Set-Cookie', line) for line in (set_cookie_lines or []))
    return HttpSendResult(status=200, headers=headers, body=json.dumps(payload).encode('utf-8'))


def _fp_ok_result() -> HttpSendResult:
    """getFp 四判据全过的成功响应（设备头带 fp 的形态）。"""
    body = json.dumps({'retcode': 0, 'message': 'OK', 'data': {'code': 200, 'device_fp': _VALID_FP}})
    return HttpSendResult(status=200, headers=[], body=body.encode('utf-8'))


def _login_success_result() -> HttpSendResult:
    """登录成功响应剧本：Set-Cookie 十件（登录响应层名单 fixture 逐项下发）。"""
    lines = [f'{name}={value}; Path=/; HttpOnly' for name, value in LOGIN_SET_COOKIES.items()]
    return _json_result({'retcode': 0, 'message': 'OK', 'data': {}}, lines)


def _parse_cookie_header(header_value: str) -> dict[str, str]:
    """测试侧解析 Cookie 头为字典（独立于实现，锁线上形态）。"""
    return dict(pair.split('=', 1) for pair in header_value.split('; '))


def _snapshot_files(session_dir: Path) -> dict[str, bytes]:
    """目录内全部文件字节快照（断言失败剧本零落盘/零改动用）。"""
    return {
        entry.name: entry.read_bytes()
        for entry in session_dir.iterdir()
        if entry.is_file()
    }


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path, threading.Lock())


@pytest.fixture
def send() -> _ScriptedHttpSend:
    """带 getFp 成功剧本的假发送（登录/业务路由由各测试按剧本追加）。"""
    return _ScriptedHttpSend((GET_FP_URL, _fp_ok_result()))


@pytest.fixture
def device(store: SessionStore, send: _ScriptedHttpSend) -> DeviceIdentity:
    """真实 DeviceIdentity（fp 走假剧本）——登录/请求头组装走全真代码路径。"""
    return DeviceIdentity(store, send)


@pytest.fixture
def client(store: SessionStore, device: DeviceIdentity, send: _ScriptedHttpSend) -> MysClient:
    return MysClient(store, device, send)


# ---- 构造契约 ----


def test_constructor_params_all_required(
    store: SessionStore, device: DeviceIdentity, send: _ScriptedHttpSend
) -> None:
    """三参必填无默认：缺任一构造即 TypeError（无默认路径存在性断言）。"""
    with pytest.raises(TypeError):
        MysClient()
    with pytest.raises(TypeError):
        MysClient(store)
    with pytest.raises(TypeError):
        MysClient(store, device)
    MysClient(store, device, send)  # 全参可构造


# ---- 登录成功路径 ----


def _login_success(client: MysClient, send: _ScriptedHttpSend) -> None:
    """公共剧本：登记登录成功响应并执行 login，返回供逐项断言。"""
    send.add_route((LOGIN_URL, _login_success_result()))
    client.login(_USERNAME, _PASSWORD)


def test_login_success_persists_session_and_clears_role(
    store: SessionStore, tmp_path: Path, client: MysClient, send: _ScriptedHttpSend
) -> None:
    """登录成功：10 项名单入罐 + save_session_full 形态落盘（无 expired 键）
    + role.json 清除（登录态换绑强制重新发现）。"""
    store.save_role({'role_id': '100000001', 'server': 'prod_gf_cn'})
    _login_success(client, send)

    saved = json.loads((tmp_path / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['schema_version'] == 1
    assert saved['saved_at']
    assert saved['cookies'] == LOGIN_SET_COOKIES  # 与登录响应名单逐项一致
    assert 'expired' not in saved  # save_session_full 形态（无 expired 键）
    assert store.load_cookies() == LOGIN_SET_COOKIES
    assert store.load_role() is None  # role.json 已清除
    assert not (tmp_path / ROLE_FILE_NAME).exists()


def test_login_request_headers_and_encrypted_body(
    store: SessionStore, client: MysClient, send: _ScriptedHttpSend
) -> None:
    """登录请求形态：十件套头（5 显式 + 设备三件 + Content-Type + ds）与
    RSA 加密 body（account/password 均密文，非明文）。"""
    _login_success(client, send)

    login_calls = send.calls_for(LOGIN_URL)
    assert len(login_calls) == 1
    _, method, headers, body = login_calls[0]
    assert method == 'POST'
    assert headers['Content-Type'] == 'application/json'
    assert headers['x-rpc-app_id'] == 'bll8iq97cem8'
    assert headers['x-rpc-client_type'] == '4'
    assert headers['x-rpc-source'] == 'v2.webLogin'
    assert headers['x-rpc-game_biz'] == 'bbs_cn'
    assert headers['x-rpc-sdk_version'] == '2.31.0'
    assert headers['x-rpc-device_id'] == store.load_device()
    assert headers['x-rpc-platform'] == '4'
    assert headers['x-rpc-device_fp'] == _VALID_FP
    assert 'Cookie' not in headers  # 登录请求不携带旧会话 cookie
    # ds 三段式 {t},{r},{md5(salt=LOGIN_SALT&t&r)}（口径 flow.md §2.3）
    t_value, r_value, digest = headers['ds'].split(',')
    expected_digest = hashlib.md5(f'salt={LOGIN_SALT}&t={t_value}&r={r_value}'.encode()).hexdigest()
    assert digest == expected_digest

    body_payload = json.loads((body or b'').decode('utf-8'))
    assert set(body_payload.keys()) == {'account', 'password'}
    assert body_payload['account'] != _USERNAME
    assert body_payload['password'] != _PASSWORD
    # RSA 1024 位密文 → 128 字节 → base64 172 字符（flow.md §2.2）
    assert len(base64.b64decode(body_payload['password'])) == 128
    assert len(base64.b64decode(body_payload['account'])) == 128


def test_login_session_rolls_into_full_jar(
    store: SessionStore, tmp_path: Path, client: MysClient, send: _ScriptedHttpSend
) -> None:
    """第二层滚动件对账：登录下发 10 项之后，业务响应滚动下发 acw_tc，
    滚动后 jar ⊇ 登录名单 + 滚动件（两集合分别对账）。"""
    _login_success(client, send)
    send.add_route(
        (GAME_RECORD_BASE_URL + 'hkrpg/api/index',
         _json_result({'retcode': 0, 'message': 'OK', 'data': {}}, ['acw_tc=roll-1; Path=/'])),
    )
    client.request('hkrpg/api/index', {'role_id': '1001', 'server': 'prod_gf_cn'})

    rolled = {**LOGIN_SET_COOKIES, 'acw_tc': 'roll-1'}
    assert store.load_cookies() == rolled  # 罐 ⊇ 登录名单 + 滚动件
    saved = json.loads((tmp_path / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['cookies'] == rolled

    # 第二个请求的 Cookie 头 = 内存罐线上形态（逐项 == 登录 10 项 + acw_tc）
    send.add_route(
        (GAME_RECORD_BASE_URL + 'hkrpg/api/note',
         _json_result({'retcode': 0, 'message': 'OK', 'data': {}})),
    )
    client.request('hkrpg/api/note', {'role_id': '1001', 'server': 'prod_gf_cn'})
    note_calls = send.calls_for(GAME_RECORD_BASE_URL + 'hkrpg/api/note')
    assert _parse_cookie_header(note_calls[0][2]['Cookie']) == rolled


def test_login_overwrites_expired_mark(
    store: SessionStore, tmp_path: Path, client: MysClient, send: _ScriptedHttpSend
) -> None:
    """先 mark_expired 再登录成功：整体覆盖后产物无 expired 键（标记消失）。"""
    store.save_cookies({'stale': 'x'})
    store.mark_expired()
    assert store.is_expired() is True
    _login_success(client, send)

    saved = json.loads((tmp_path / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert 'expired' not in saved
    assert saved['cookies'] == LOGIN_SET_COOKIES
    assert store.is_expired() is False


@pytest.mark.parametrize(
    'retcode',
    [-3208, -3235, -3102, -3202, -1001],
    ids=['wrong-password', 'account-risk', 'ticket-rejected-3102', 'ticket-rejected-3202', 'unknown'],
)
def test_login_error_codes_raise_and_leave_files_untouched(
    store: SessionStore,
    tmp_path: Path,
    device: DeviceIdentity,
    client: MysClient,
    send: _ScriptedHttpSend,
    retcode: int,
) -> None:
    """登录失败码：MysApiError 且不落盘不清文件（重登失败时旧数据原样保留，
    design.md §2.6）。-3102/-3202 首轮不可能出现（无票据可拒），出现按未知
    码上抛（design.md §2.2 login 分诊）。"""
    store.save_cookies({'keep': '1'})
    store.save_role({'role_id': '9', 'server': 'prod_gf_cn'})
    device.get_headers()  # 预热设备头：device.json 先行落盘，快照含三文件全集
    snapshot = _snapshot_files(tmp_path)
    send.add_route(
        (LOGIN_URL, _json_result({'retcode': retcode, 'message': 'failed fixture'}))
    )

    with pytest.raises(MysApiError) as error_info:
        client.login(_USERNAME, _PASSWORD)
    assert error_info.value.code == retcode
    assert _snapshot_files(tmp_path) == snapshot  # 无新文件、无内容改动


# ---- request() ----


def test_request_relative_path_joins_record_base(
    client: MysClient, send: _ScriptedHttpSend
) -> None:
    """相对路径拼 game_record 基座；game_record 头全集 + DS2 在场；空罐不带
    Cookie 头；成功返回 data 字段。"""
    send.add_route(
        (
            GAME_RECORD_BASE_URL + 'hkrpg/api/index',
            _json_result({'retcode': 0, 'message': 'OK', 'data': {'list': [1, 2]}}),
        )
    )
    data = client.request('hkrpg/api/index', {'server': 'prod_gf_cn', 'role_id': '1001'})

    assert data == {'list': [1, 2]}
    url, method, headers, body = send.calls_for(GAME_RECORD_BASE_URL)[0]
    assert url == GAME_RECORD_BASE_URL + 'hkrpg/api/index?role_id=1001&server=prod_gf_cn'
    assert method == 'GET'
    assert body is None
    assert headers['Content-Type'] == 'application/json'
    assert headers['User-Agent'] == USER_AGENT_DESKTOP_CHROME
    assert headers['x-rpc-app_version'] == '2.11.1'
    assert headers['x-rpc-client_type'] == '5'
    assert headers['Referer'] == 'https://webstatic.mihoyo.com/'
    assert headers['x-rpc-device_id'] != ''
    assert len(headers['ds'].split(',')) == 3  # DS2 三段式在场（密码学断言见下条）
    assert 'Cookie' not in headers  # 未登录（空罐）不带 Cookie 头


def test_request_absolute_url_passes_through(
    client: MysClient, send: _ScriptedHttpSend
) -> None:
    """白名单内绝对 URL 直用（不做基座拼接），query 仍追加并参与 DS2 签名。"""
    absolute_url = 'https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie'
    send.add_route(
        (absolute_url, _json_result({'retcode': 0, 'message': 'OK', 'data': {'list': []}}))
    )
    data = client.request(absolute_url, {'game_biz': 'hkrpg_cn'})

    assert data == {'list': []}
    url, method, _, _ = send.calls_for(absolute_url)[0]
    assert url == f'{absolute_url}?game_biz=hkrpg_cn'
    assert method == 'GET'


def test_request_rejects_non_whitelisted_target(
    client: MysClient, send: _ScriptedHttpSend
) -> None:
    """白名单外主机 / 非 https 绝对 URL：ValueError，且不发出任何请求。"""
    with pytest.raises(ValueError):
        client.request('https://evil.example.com/game_record/app/hkrpg/api/index', {})
    with pytest.raises(ValueError):
        client.request('http://api-takumi.mihoyo.com/game_record/app/hkrpg/api/index', {})
    assert send.calls == []  # 拒绝发生在发请求之前（凭据不外发）


def test_request_ds_signature_sorted_and_url_encoded(
    client: MysClient, send: _ScriptedHttpSend
) -> None:
    """DS2 按 q 排序 + URLSearchParams 口径 URL 编码：query 乱序插入、值含
    空格与保留字符（~），测试侧独立重算签名串（排序 + 编码 + b 恒空）比对
    ds 头摘要。"""
    send.add_route(
        (
            GAME_RECORD_BASE_URL + 'hkrpg/api/index',
            _json_result({'retcode': 0, 'message': 'OK', 'data': {}}),
        )
    )
    client.request('hkrpg/api/index', {'zparam': '~x', 'role_id': '9 9', 'aparam': '1'})

    url, _, headers, _ = send.calls_for(GAME_RECORD_BASE_URL)[0]
    # URL query 串 = 按 key 排序 + URLSearchParams 口径编码（空格→+，~→%7E）
    assert url.endswith('?aparam=1&role_id=9+9&zparam=%7Ex')
    # 测试侧独立重算：salt/t/r/b(空)/q(排序+编码) → md5
    t_value, r_value, digest = headers['ds'].split(',')
    expected_q = 'aparam=1&role_id=9+9&zparam=%7Ex'
    sign_string = f'salt={RECORD_SALT}&t={t_value}&r={r_value}&b=&q={expected_q}'
    assert digest == hashlib.md5(sign_string.encode('utf-8')).hexdigest()
    assert 100001 <= int(r_value) <= 200000  # DS2 的 r 取值域（flow.md §4.1）


@pytest.mark.parametrize('retcode', sorted(SESSION_EXPIRED_RETCODES))
def test_request_expired_codes_map_to_session_expired(
    client: MysClient, send: _ScriptedHttpSend, retcode: int
) -> None:
    """会话失效映射：SESSION_EXPIRED_RETCODES 各码 → MysSessionExpired。
    用例参数直接从 mys_session 导出的常量生成——映射若硬编码码值、与常量
    脱钩，本条随常量修订立即失败。"""
    send.add_route(
        (
            GAME_RECORD_BASE_URL + 'hkrpg/api/index',
            _json_result({'retcode': retcode, 'message': 'Please login'}),
        )
    )
    with pytest.raises(MysSessionExpired) as error_info:
        client.request('hkrpg/api/index', {'role_id': '1001', 'server': 'prod_gf_cn'})
    assert error_info.value.code == retcode
    assert isinstance(error_info.value, MysApiError)


def test_request_risk_control_1034_is_bare_api_error(
    client: MysClient, send: _ScriptedHttpSend
) -> None:
    """1034 裸错误语义：按通用非 0 分支抛 MysApiError(1034)（不是
    MysSessionExpired 子类）；验证链本迭代不实现（design.md §1）。"""
    send.add_route(
        (
            GAME_RECORD_BASE_URL + 'hkrpg/api/index',
            _json_result({'retcode': 1034, 'message': '请求遇到验证码'}),
        )
    )
    with pytest.raises(MysApiError) as error_info:
        client.request('hkrpg/api/index', {'role_id': '1001', 'server': 'prod_gf_cn'})
    assert error_info.value.code == 1034
    assert type(error_info.value) is MysApiError  # 裸错误，非任何子类


def test_request_rolling_keeps_expired_mark(
    store: SessionStore, tmp_path: Path, device: DeviceIdentity, send: _ScriptedHttpSend
) -> None:
    """响应 Set-Cookie 滚动入罐走 save_cookies：expired 标记保留不抹除。
    场景按真实生命周期排布——会话先落盘（带过期标记），客户端构造时从盘
    恢复罐（跨进程续用），滚动在罐既有内容上合并。"""
    store.save_session_full({'ltoken_v2': 'keep-value'})
    store.mark_expired()
    client = MysClient(store, device, send)  # 罐播种 = {'ltoken_v2': 'keep-value'}
    send.add_route(
        (
            GAME_RECORD_BASE_URL + 'hkrpg/api/index',
            _json_result({'retcode': 0, 'message': 'OK', 'data': {}}, ['acw_tc=roll-9; Path=/']),
        )
    )
    client.request('hkrpg/api/index', {'role_id': '1001', 'server': 'prod_gf_cn'})

    saved = json.loads((tmp_path / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['expired'] is True  # 滚动续存保留过期标记
    assert saved['cookies'] == {'ltoken_v2': 'keep-value', 'acw_tc': 'roll-9'}
    assert store.is_expired() is True


def test_request_rolls_cookies_on_non_2xx_response(
    store: SessionStore, tmp_path: Path, client: MysClient, send: _ScriptedHttpSend
) -> None:
    """非 2xx 响应同样滚动收取（miyoushe-api-flow.md §4.4「无论成败都收取」）：
    滚动收取在业务分诊之前，服务端滚动下发不因业务失败而中断。"""
    send.add_route(
        (
            GAME_RECORD_BASE_URL + 'hkrpg/api/index',
            HttpSendResult(
                status=502,
                headers=[('Set-Cookie', 'acw_tc=roll-on-error; Path=/')],
                body=b'bad gateway',
            ),
        )
    )
    with pytest.raises(MysApiError) as error_info:
        client.request('hkrpg/api/index', {'role_id': '1001', 'server': 'prod_gf_cn'})
    assert error_info.value.code == 502

    saved = json.loads((tmp_path / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['cookies'] == {'acw_tc': 'roll-on-error'}  # 失败响应的滚动件已入罐落盘
    assert store.load_cookies() == {'acw_tc': 'roll-on-error'}


# ---- logout ----


def test_logout_clears_files_and_jar_idempotent(
    store: SessionStore, tmp_path: Path, client: MysClient, send: _ScriptedHttpSend
) -> None:
    """登出：session.json 与 role.json 删除、device.json 保留、内存罐清空
    （后续请求不带 Cookie 头）、幂等。"""
    store.save_device('123e4567-e89b-12d3-a456-426614174000')
    _login_success(client, send)
    store.save_role({'role_id': '7', 'server': 'prod_gf_cn'})
    send.add_route(
        (GAME_RECORD_BASE_URL, _json_result({'retcode': 0, 'message': 'OK', 'data': {}}))
    )

    client.logout()
    assert not (tmp_path / SESSION_FILE_NAME).exists()
    assert not (tmp_path / ROLE_FILE_NAME).exists()
    assert (tmp_path / DEVICE_FILE_NAME).exists()
    client.request('hkrpg/api/index', {'role_id': '1', 'server': 'prod_gf_cn'})
    _, _, headers, _ = send.calls_for(GAME_RECORD_BASE_URL)[0]
    assert 'Cookie' not in headers  # 内存罐已清空

    client.logout()  # 幂等：无会话再登出不报错
    assert not (tmp_path / SESSION_FILE_NAME).exists()
    assert (tmp_path / DEVICE_FILE_NAME).exists()


# ---- 凭据红线 ----


def test_credentials_never_leak_to_disk_or_exceptions(
    store: SessionStore, tmp_path: Path, client: MysClient, send: _ScriptedHttpSend
) -> None:
    """密码与 cookie 不出现在任何落盘文件与异常文本：session.json 是 cookie
    唯一指定居所（design.md §2.6），其余落盘文件与全部异常文本零凭据。"""
    _login_success(client, send)
    # 业务请求失败剧本：服务端 message 为普通文案，异常不得携带请求头/cookie/密码
    send.add_route(
        (
            GAME_RECORD_BASE_URL,
            _json_result({'retcode': -3208, 'message': 'Wrong password fixture'}),
        )
    )
    with pytest.raises(MysApiError) as request_error:
        client.request('hkrpg/api/index', {'role_id': '1001', 'server': 'prod_gf_cn'})
    # 登录失败剧本：错误密码再次登录，异常不得携带任何凭据
    send.add_route(
        (LOGIN_URL, _json_result({'retcode': -3208, 'message': 'Wrong password fixture'}))
    )
    with pytest.raises(MysApiError) as login_error:
        client.login(_USERNAME, 'ANOTHER-SECRET-pw-42')

    secrets = [_USERNAME, _PASSWORD, 'ANOTHER-SECRET-pw-42', *LOGIN_SET_COOKIES.values()]
    exception_texts = [str(request_error.value), str(login_error.value)]
    for text in exception_texts:
        for secret in secrets:
            assert secret not in text

    # 落盘扫描：密码/账号不出现在任何文件；cookie 只允许出现在 session.json
    for entry in tmp_path.iterdir():
        if not entry.is_file():
            continue
        file_bytes = entry.read_bytes().decode('utf-8', errors='replace')
        assert _USERNAME not in file_bytes
        for secret in (_PASSWORD, 'ANOTHER-SECRET-pw-42'):
            assert secret not in file_bytes
        if entry.name != SESSION_FILE_NAME:
            for cookie_value in LOGIN_SET_COOKIES.values():
                assert cookie_value not in file_bytes
