"""aigis 验证单轮分支 + complete_verification 单测（landing §3.3 判据逐条）。

剧本全部 mock http_send，零真实网络，落盘走 pytest tmp_path。覆盖：
- login() 分诊双条件（retcode -3101、或 aigis 头非空且码值不同）与 message
  文案不参与分诊（research §2.1「不能按文案判断」）；
- x-rpc-aigis 双层解析（data 字符串 / 对象双 fixture 均解出 challenge）；
- 回传头字节级组装：``{session_id};{base64(JSON(票据))}``，v4 补 captcha_id +
  userInfo，gt3 三元组原值无 |jordan（research §4.2/§10.4-5）；
- 重发原样逐字节断言：body 与 login 首轮留存的 body 相等、请求头 = 首轮
  全部键值仅多 x-rpc-aigis 一项、DS 重新生成（research §4.1 拦截器语义）；
- complete_verification 六剧本：重发 0 → ok + save_session_full 落盘无
  expired 键；重发 -3101/aigis 非空 → 新挑战；-3102/-3202 携带新挑战 → 新
  挑战；-3102/-3202 未携带 → 补发一次裸登录取新挑战；-3208/-3235/未知码 →
  MysApiError 不落盘；未 login 先调用 → ValueError——各剧本断言「带票据重发
  恰一次」（单轮语义，无内部循环）。
"""

import base64
import json
import threading
from pathlib import Path

import pytest

from one_dragon.mys.mys_client import AigisChallenge, MysClient
from one_dragon.mys.mys_const import GET_FP_URL, LOGIN_URL
from one_dragon.mys.mys_device import DeviceIdentity
from one_dragon.mys.mys_http import HttpSendResult
from one_dragon.mys.mys_session import (
    SESSION_FILE_NAME,
    MysApiError,
    SessionStore,
)

_VALID_FP = 'abcdef123456'
_USERNAME = 'fixture_user'
_PASSWORD = 'SECRET-PW-fixture-777'

#: 登录响应层 Set-Cookie 名单 fixture（与 test_mys_client.py 同源口径，10 项）
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

#: gt4 形态挑战 data fixture（research §2.2）
_GT4_DATA: dict = {
    'gt': 'captcha-id-fixture',
    'risk_type': 'slide',
    'success': 1,
    'new_captcha': 1,
    'use_v4': True,
}

#: gt3 形态挑战 data fixture（research §2.2）
_GT3_DATA: dict = {
    'gt': 'captcha-id-fixture',
    'challenge': 'challenge-fixture',
    'success': 1,
    'new_captcha': 1,
}

#: v4 票据 fixture（getValidate() 原生产出，缺 captcha_id——组装时应补）
_V4_TICKET: dict = {
    'lot_number': 'lot-fixture',
    'captcha_output': 'output-fixture',
    'pass_token': 'token-fixture',
    'gen_time': '1730000000',
}

#: gt3 票据 fixture（三元组原值）
_GT3_TICKET: dict = {
    'geetest_challenge': 'challenge-fixture',
    'geetest_validate': 'validate-fixture',
    'geetest_seccode': 'seccode-fixture',
}

#: 模糊文案 fixture：实测记录 S6 中 -3101 的 message 即此类文案，
#: 断言分诊不受其影响（research §2.1/§2.3）
_AMBIGUOUS_MESSAGE = '请求频繁，请稍后再试'


class _ScriptedHttpSend:
    """剧本式假发送（零网络）：按「URL 前缀 → 响应」注册表首匹配分流；
    响应为列表时按序出队（序列剧本，如「-3102 拒票据 → 裸重发 -3101」），
    为单个结果时恒返回。未命中前缀即断言失败（防剧本漏路由静默通过）。"""

    def __init__(self, *routes: tuple[str, HttpSendResult | list[HttpSendResult]]) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []
        self._routes: dict[str, HttpSendResult | list[HttpSendResult]] = dict(routes)

    def add_route(self, *routes: tuple[str, HttpSendResult | list[HttpSendResult]]) -> None:
        """登记路由；同前缀再登记即覆盖（测试中途改剧本用）。"""
        for route_prefix, result in routes:
            self._routes[route_prefix] = result

    def __call__(
        self, url: str, method: str, headers: dict[str, str], body: bytes | None
    ) -> HttpSendResult:
        self.calls.append((url, method, dict(headers), body))
        for route_prefix, scripted in self._routes.items():
            if url.startswith(route_prefix):
                if isinstance(scripted, list):
                    assert scripted, f'剧本耗尽（测试序列比预期短）: {method} {url}'
                    return scripted.pop(0)
                return scripted
        raise AssertionError(f'剧本外请求（测试剧本缺路由）: {method} {url}')

    def calls_for(self, prefix: str) -> list[tuple[str, str, dict[str, str], bytes | None]]:
        return [call for call in self.calls if call[0].startswith(prefix)]


def _json_result(
    payload: dict,
    *,
    aigis_header: str | None = None,
    set_cookie_lines: list[str] | None = None,
) -> HttpSendResult:
    """构造登录端业务 JSON 响应（按需附 x-rpc-aigis 头与 Set-Cookie 行）。"""
    headers: list[tuple[str, str]] = [('Content-Type', 'application/json')]
    if aigis_header is not None:
        headers.append(('x-rpc-aigis', aigis_header))
    headers.extend(('Set-Cookie', line) for line in (set_cookie_lines or []))
    return HttpSendResult(status=200, headers=headers, body=json.dumps(payload, ensure_ascii=False).encode('utf-8'))


def _fp_ok_result() -> HttpSendResult:
    """getFp 四判据全过的成功响应（设备头带 fp 的形态）。"""
    body = json.dumps({'retcode': 0, 'message': 'OK', 'data': {'code': 200, 'device_fp': _VALID_FP}})
    return HttpSendResult(status=200, headers=[], body=body.encode('utf-8'))


def _aigis_header_value(session_id: str, data: dict, *, data_as_object: bool = False) -> str:
    """外层 x-rpc-aigis 头 fixture：data 按字符串（默认，官方常态）或对象双
    形态嵌入（research §2.2：解析须兼容双形态）。"""
    payload: dict = {'session_id': session_id, 'mmt_type': 1}
    if data_as_object:
        payload['data'] = data
    else:
        payload['data'] = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return json.dumps(payload, ensure_ascii=False)


def _decode_aigis_request_header(value: str) -> tuple[str, dict]:
    """测试侧独立解码回传头（锁线上形态 {session_id};{base64(JSON)}）。"""
    session_id, encoded = value.split(';', 1)
    ticket = json.loads(base64.b64decode(encoded).decode('utf-8'))
    return session_id, ticket


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
    return _ScriptedHttpSend((GET_FP_URL, _fp_ok_result()))


@pytest.fixture
def device(store: SessionStore, send: _ScriptedHttpSend) -> DeviceIdentity:
    return DeviceIdentity(store, send)


@pytest.fixture
def client(store: SessionStore, device: DeviceIdentity, send: _ScriptedHttpSend) -> MysClient:
    return MysClient(store, device, send)


def _prime_verification_flow(
    client: MysClient, send: _ScriptedHttpSend, *, session_id: str = 'session-fixture-1'
) -> AigisChallenge:
    """公共剧本：login 首轮命中 -3101（携带挑战），返回解出的挑战。"""
    send.add_route(
        (
            LOGIN_URL,
            _json_result(
                {'retcode': -3101, 'message': _AMBIGUOUS_MESSAGE},
                aigis_header=_aigis_header_value(session_id, _GT4_DATA),
            ),
        )
    )
    result = client.login(_USERNAME, _PASSWORD)
    assert result.status == 'need_verification'
    assert result.challenge is not None
    return result.challenge


# ---- login 分诊双条件与双层解析 ----


@pytest.mark.parametrize(
    'retcode,data_as_object',
    [
        (-3101, False),  # 双条件之「码值」：NeedAigis 本码
        (-3006, True),  # 双条件之「头」：码值不同但 aigis 头非空，仍进验证分支
    ],
    ids=['need-aigis-retcode', 'aigis-header-with-other-retcode'],
)
def test_login_dispatch_double_condition_ignores_message(
    client: MysClient,
    send: _ScriptedHttpSend,
    retcode: int,
    data_as_object: bool,
) -> None:
    """分诊双条件：码值 -3101、或 aigis 头非空（码值不同）都进验证分支；
    message 用模糊文案 fixture（不能按文案判断，research §2.1）。"""
    send.add_route(
        (
            LOGIN_URL,
            _json_result(
                {'retcode': retcode, 'message': _AMBIGUOUS_MESSAGE},
                aigis_header=_aigis_header_value(
                    'session-fixture-1', _GT4_DATA, data_as_object=data_as_object
                ),
            ),
        )
    )
    result = client.login(_USERNAME, _PASSWORD)
    assert result.status == 'need_verification'
    assert result.challenge is not None
    assert result.challenge.session_id == 'session-fixture-1'


@pytest.mark.parametrize('data_as_object', [False, True], ids=['data-as-string', 'data-as-object'])
def test_login_challenge_parses_both_data_shapes(
    client: MysClient, send: _ScriptedHttpSend, data_as_object: bool
) -> None:
    """双层解析：data 为字符串 / 为对象两 fixture 均解出同一挑战参数。"""
    send.add_route(
        (
            LOGIN_URL,
            _json_result(
                {'retcode': -3101, 'message': _AMBIGUOUS_MESSAGE},
                aigis_header=_aigis_header_value(
                    'session-fixture-1', _GT4_DATA, data_as_object=data_as_object
                ),
            ),
        )
    )
    result = client.login(_USERNAME, _PASSWORD)
    assert result.challenge is not None
    assert result.challenge.session_id == 'session-fixture-1'
    assert result.challenge.mmt_type == 1
    assert result.challenge.data == _GT4_DATA


# ---- 回传头字节级组装 ----


@pytest.mark.parametrize(
    'ticket,expected_assembled',
    [
        (
            _V4_TICKET,
            {
                **_V4_TICKET,
                'captcha_id': _GT4_DATA['gt'],
                'userInfo': {'session_id': 'session-fixture-1'},
            },
        ),
        (_GT3_TICKET, _GT3_TICKET),
    ],
    ids=['v4-adds-captcha-id-and-userinfo', 'gt3-triple-untouched'],
)
def test_complete_verification_resend_header_byte_composition(
    client: MysClient,
    send: _ScriptedHttpSend,
    ticket: dict,
    expected_assembled: dict,
) -> None:
    """回传头字节级断言：第一段 == session_id；第二段 base64 解码 + JSON 解析
    == 期望票据（v4 补 captcha_id+userInfo / gt3 三元组原值）。"""
    challenge = _prime_verification_flow(client, send)
    send.add_route(
        (
            LOGIN_URL,
            _json_result(
                {'retcode': 0, 'message': 'OK'},
                set_cookie_lines=[f'{k}={v}; Path=/' for k, v in LOGIN_SET_COOKIES.items()],
            ),
        )
    )
    result = client.complete_verification(challenge, dict(ticket))
    assert result.status == 'ok'

    resend_calls = send.calls_for(LOGIN_URL)
    assert len(resend_calls) == 2  # login 首轮 + 票据重发恰一次（单轮语义）
    resend_headers = resend_calls[1][2]
    header_value = resend_headers['x-rpc-aigis']
    if ticket is _GT3_TICKET:
        assert '|jordan' not in header_value  # gt3 原值透传，不拼后缀
    session_part, ticket_part = _decode_aigis_request_header(header_value)
    assert session_part == 'session-fixture-1'
    assert ticket_part == expected_assembled
    # 原样重发口径：不带 Cookie 头（与首轮一致），DS 重新生成（三段式在场）
    assert 'Cookie' not in resend_headers
    assert len(resend_headers['ds'].split(',')) == 3


def test_complete_verification_resend_replays_first_round_body_and_headers(
    client: MysClient, send: _ScriptedHttpSend
) -> None:
    """原样重发逐字节断言（research §4.1：官方前端拦截器「config 原样重发」）：
    重发 body 与 login 首轮留存的 body 逐字节相等（防误换新加密产物）；
    请求头与首轮全部键值一致，仅新增 x-rpc-aigis 一项；DS 与首轮不同
    （重新生成，r 每次随机）。"""
    challenge = _prime_verification_flow(client, send)
    send.add_route(
        (
            LOGIN_URL,
            _json_result(
                {'retcode': 0, 'message': 'OK'},
                set_cookie_lines=[f'{k}={v}; Path=/' for k, v in LOGIN_SET_COOKIES.items()],
            ),
        )
    )
    result = client.complete_verification(challenge, dict(_V4_TICKET))
    assert result.status == 'ok'

    login_calls = send.calls_for(LOGIN_URL)
    assert len(login_calls) == 2  # login 首轮 + 带票据重发恰一次（单轮语义）
    (_, _first_method, first_headers, first_body) = login_calls[0]
    (_, _resend_method, resend_headers, resend_body) = login_calls[1]
    assert resend_body == first_body  # body 逐字节相等（bytes 全量比对）

    # 头集合 = 首轮 ∪ {x-rpc-aigis}（仅多一项）；除 ds 外其余键值与首轮一致
    # （登录十件套 + 设备头三件原样复用；首轮无 Cookie，重发也不得引入）
    assert set(resend_headers) == set(first_headers) | {'x-rpc-aigis'}
    for name, value in first_headers.items():
        if name != 'ds':
            assert resend_headers[name] == value
    assert resend_headers['ds'] != first_headers['ds']  # DS 重新生成（r 随机）


# ---- complete_verification 分诊剧本 ----


def test_complete_verification_success_collects_and_persists(
    store: SessionStore, tmp_path: Path, client: MysClient, send: _ScriptedHttpSend
) -> None:
    """重发 retcode 0 → ok：Set-Cookie 全量入罐 + save_session_full 整体覆盖
    落盘（先 mark_expired 再成功，产物无 expired 键）+ role.json 清除
    （与 login 成功路径同一收取逻辑，验证完成即登录事件完成）。"""
    challenge = _prime_verification_flow(client, send)
    store.save_cookies({'stale': 'x'})
    store.mark_expired()
    store.save_role({'role_id': '100000001', 'server': 'prod_gf_cn'})
    send.add_route(
        (
            LOGIN_URL,
            _json_result(
                {'retcode': 0, 'message': 'OK'},
                set_cookie_lines=[f'{k}={v}; Path=/' for k, v in LOGIN_SET_COOKIES.items()],
            ),
        )
    )
    result = client.complete_verification(challenge, dict(_V4_TICKET))

    assert result.status == 'ok'
    assert result.challenge is None
    assert len(send.calls_for(LOGIN_URL)) == 2  # 带票据重发恰一次
    saved = json.loads((tmp_path / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['cookies'] == LOGIN_SET_COOKIES
    assert 'expired' not in saved  # 整体覆盖形态
    assert store.is_expired() is False
    assert store.load_role() is None  # 登录态换绑后强制重新发现角色定位


def test_complete_verification_new_challenge_on_resend_3101(
    client: MysClient, send: _ScriptedHttpSend
) -> None:
    """重发 -3101 → need_verification + 新挑战（从该响应 aigis 头解析）；
    重发恰一次，无内部循环。"""
    challenge = _prime_verification_flow(client, send)
    send.add_route(
        (
            LOGIN_URL,
            _json_result(
                {'retcode': -3101, 'message': _AMBIGUOUS_MESSAGE},
                aigis_header=_aigis_header_value('session-fixture-2', _GT4_DATA),
            ),
        )
    )
    result = client.complete_verification(challenge, dict(_V4_TICKET))

    assert result.status == 'need_verification'
    assert result.challenge is not None
    assert result.challenge.session_id == 'session-fixture-2'  # 新会话，非旧挑战复用
    assert len(send.calls_for(LOGIN_URL)) == 2


@pytest.mark.parametrize('retcode', [-3102, -3202], ids=['rejected-3102', 'rejected-3202'])
def test_complete_verification_rejected_with_new_challenge(
    client: MysClient, send: _ScriptedHttpSend, retcode: int
) -> None:
    """-3102/-3202 票据被拒且响应携带新 aigis 头 → 直接解析为新挑战返回
    need_verification（不补发裸登录）。"""
    challenge = _prime_verification_flow(client, send)
    send.add_route(
        (
            LOGIN_URL,
            _json_result(
                {'retcode': retcode, 'message': '图片验证码失败'},
                aigis_header=_aigis_header_value('session-fixture-2', _GT4_DATA),
            ),
        )
    )
    result = client.complete_verification(challenge, dict(_V4_TICKET))

    assert result.status == 'need_verification'
    assert result.challenge is not None
    assert result.challenge.session_id == 'session-fixture-2'
    assert len(send.calls_for(LOGIN_URL)) == 2  # 未补发裸登录


@pytest.mark.parametrize('retcode', [-3102, -3202], ids=['rejected-3102', 'rejected-3202'])
def test_complete_verification_rejected_without_challenge_bare_resend(
    client: MysClient, send: _ScriptedHttpSend, retcode: int
) -> None:
    """-3102/-3202 未携带新 aigis 头 → 自动补发一次裸 loginByPassword（无票据）
    取 -3101 新挑战后 need_verification（单轮语义：补发只此一层）。"""
    challenge = _prime_verification_flow(client, send)
    send.add_route(
        (
            LOGIN_URL,
            [
                # 第一次（带票据重发）：票据被拒且无新挑战
                _json_result({'retcode': retcode, 'message': '图片验证码失败'}),
                # 第二次（裸补发）：下发 -3101 新挑战
                _json_result(
                    {'retcode': -3101, 'message': _AMBIGUOUS_MESSAGE},
                    aigis_header=_aigis_header_value('session-fixture-2', _GT4_DATA),
                ),
            ],
        )
    )
    result = client.complete_verification(challenge, dict(_V4_TICKET))

    assert result.status == 'need_verification'
    assert result.challenge is not None
    assert result.challenge.session_id == 'session-fixture-2'

    login_calls = send.calls_for(LOGIN_URL)
    assert len(login_calls) == 3  # 首轮 + 票据重发 + 裸补发恰一次
    assert 'x-rpc-aigis' in login_calls[1][2]  # 第一次带票据
    assert 'x-rpc-aigis' not in login_calls[2][2]  # 补发为裸登录（无票据）


@pytest.mark.parametrize(
    'retcode',
    [-3208, -3235, -1001],
    ids=['wrong-password', 'account-risk', 'unknown'],
)
def test_complete_verification_terminal_codes_raise_and_leave_files_untouched(
    store: SessionStore,
    tmp_path: Path,
    device: DeviceIdentity,
    client: MysClient,
    send: _ScriptedHttpSend,
    retcode: int,
) -> None:
    """-3208/-3235/未知码同 login 分诊：MysApiError 上抛、不落盘不清文件、
    不补发裸登录（无 aigis 头且非票据被拒码）。"""
    store.save_cookies({'keep': '1'})
    store.save_role({'role_id': '9', 'server': 'prod_gf_cn'})
    device.get_headers()  # 预热设备头：device.json 先行落盘，快照含文件全集
    snapshot = _snapshot_files(tmp_path)
    challenge = _prime_verification_flow(client, send)
    send.add_route(
        (LOGIN_URL, _json_result({'retcode': retcode, 'message': 'failed fixture'}))
    )

    with pytest.raises(MysApiError) as error_info:
        client.complete_verification(challenge, dict(_V4_TICKET))
    assert error_info.value.code == retcode
    assert _snapshot_files(tmp_path) == snapshot  # 零落盘零改动
    assert len(send.calls_for(LOGIN_URL)) == 2  # 不补发裸登录


def test_complete_verification_requires_prior_login(
    client: MysClient, send: _ScriptedHttpSend
) -> None:
    """未 login 先调用 complete_verification：无重发基座可复用，ValueError
    且不发出任何请求。"""
    challenge = AigisChallenge(
        session_id='session-fixture-1', mmt_type=1, data=dict(_GT4_DATA), raw_header='{}'
    )
    with pytest.raises(ValueError):
        client.complete_verification(challenge, dict(_V4_TICKET))
    assert send.calls == []
