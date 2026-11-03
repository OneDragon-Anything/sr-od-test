"""MysAccessController 状态机与三工具单测（landing §3.4 判据全清单）。

控制器测试全部注入假实现（剧本式假 http_send / 假 verifier 工厂 / tmp_path
会话目录），不弹真实浏览器、零真实网络、零真实落盘。序列剧本对照
landing §3.4 完成判据逐条排布：

- 状态机主链：login → verification_required（attempt=1）→ 票据 ok → idle +
  会话落盘（save_session_full 形态）+ get_characters 成功；
- 验证循环上限：票据被拒下发新挑战 → 同端口换题 attempt 递增；attempt≥3 →
  idle + verifier 关闭 + 留档错误在下次调用体现一次；
- 票据回传触发 complete_verification 抛 MysApiError（-3208 密码错误过多）→
  idle + verifier 关闭 + 错误留档下次调用体现一次 + 不落盘不清文件；
- cancelled → idle + verifier 关闭 + 重登走全新验证轮（新 verifier 实例）；
- awaiting 期二次 login：复用现存 URL，新账密即弃（无第二次登录请求）；
- awaiting 期 get_characters：verification_required 信封，不裸打请求；
- awaiting 期 logout：清会话 + idle + verifier 关闭，迟到票据被丢弃（不静默
  重建会话）；
- awaiting 期错配 session_id 回传：配对闸（verifier 层 409 之外的第二道闸）
  独立触发——状态保持 awaiting、attempt 不消耗、不触发 complete_verification；
- 过期标记序列：session_expired → 只打标记（session.json/role.json 保留）→
  标记后 login 不再 already_logged_in → 登录失败（-3208）旧文件原样保留 →
  登录成功整体覆盖、标记消失；
- 装配断言：MysClient/DeviceIdentity 持同一注入 http_send 实例与同一
  SessionStore 实例；缺参构造 TypeError（无默认路径）；
- 三工具信封五态（success/already_logged_in/verification_required/
  session_expired/error）含 1034 专属文案；
- 信封脱敏：全部信封的序列化文本不含账密/cookie/票据；
- 工具 description 含知情声明关键句（经注册函数取 description 文本断言）。

wait_ticket 超时不改状态属阻塞式消费路径（GUI/CLI），MCP 控制器不调用
wait_ticket，无对应剧本（语义已在 aigis_verifier 自身测试锁定）。
"""

import json
import webbrowser
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from one_dragon.mys.aigis_verifier import AigisVerifier
from one_dragon.mys.mys_client import AigisChallenge
from one_dragon.mys.mys_const import (
    GAME_RECORD_BASE_URL,
    GET_FP_URL,
    LOGIN_URL,
    ROLE_LIST_URL,
)
from one_dragon.mys.mys_http import HttpSendResult, RequestsHttpSend
from one_dragon.mys.mys_session import ROLE_FILE_NAME, SESSION_FILE_NAME
from sr_od.backend.mcp import mys_tools
from sr_od.backend.mcp.app import create_mcp_server
from sr_od.backend.mcp.mys_tools import (
    SESSION_EXPIRED_MESSAGE,
    MysAccessController,
    register_mys_tools,
)

#: index 实测结构快照（fixture 固化进测试仓）
INDEX_SNAPSHOT_PATH: Path = (
    Path(__file__).resolve().parents[3] / 'fixtures' / 'mys' / 'hkrpg_index_snapshot.json'
)

_USERNAME = 'fixture_user'
_PASSWORD = 'SECRET-PW-t4-001'
_OTHER_USER = 'OTHER-USER-t4'
_OTHER_PASSWORD = 'OTHER-SECRET-pw-t4'

#: 登录成功剧本下发的会话 cookie（值脱敏断言的凭据样本）
_LOGIN_COOKIES: dict[str, str] = {
    'ltoken_v2': 'ltv2-secret-t4',
    'account_mid_v2': 'mid-secret-t4',
}

#: 枚举信封时可能出现的全部机密样本（账密/cookie 值/票据内容）
_SECRET_SAMPLES: tuple[str, ...] = (
    _USERNAME, _PASSWORD, _OTHER_USER, _OTHER_PASSWORD,
    'ltv2-secret-t4', 'mid-secret-t4', 'lot-number-t4',
)


class _ScriptedHttpSend:
    """剧本式假发送（零网络，与 one_dragon/mys 同款手法）：按「URL 前缀 →
    响应」注册表首匹配分流，未命中即断言失败；记录全部调用供断言。"""

    def __init__(self, *routes: tuple[str, HttpSendResult]) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []
        self._routes: dict[str, HttpSendResult] = dict(routes)

    def add_route(self, *routes: tuple[str, HttpSendResult]) -> None:
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


class _FakeVerifier:
    """假验证页宿主：URL 为实例常量（同端口语义——真实 verifier 同实例 start
    复用同端口）；close 后再 start 直接断言失败（镜像真实生命周期约束）。
    deliver 模拟页面回传：经控制器注册的 on_ticket 回调进入控制器。"""

    def __init__(self) -> None:
        self.started: list[AigisChallenge] = []
        self.url: str = 'http://127.0.0.1:9527/verify'
        self.closed: bool = False
        self.on_ticket: Callable[[dict], None] | None = None

    def start(self, challenge: AigisChallenge) -> str:
        assert not self.closed, '已关闭的 verifier 不应被再次 start'
        self.started.append(challenge)
        return self.url

    def close(self) -> None:
        self.closed = True

    def deliver(self, payload: dict) -> None:
        assert self.on_ticket is not None, '控制器未注册回传回调'
        self.on_ticket(dict(payload))


@pytest.fixture
def send() -> _ScriptedHttpSend:
    """带 getFp 成功剧本的假发送（登录/业务路由由各测试按剧本追加）。"""
    fp_body = json.dumps({'retcode': 0, 'message': 'OK', 'data': {'code': 200, 'device_fp': 'fp-t4-ok'}})
    return _ScriptedHttpSend((GET_FP_URL, HttpSendResult(200, [], fp_body.encode('utf-8'))))


@pytest.fixture
def verifiers() -> list[_FakeVerifier]:
    """工厂产出的全部假 verifier（按创建顺序；下标 0 = 首轮验证）。"""
    return []


@pytest.fixture
def verifier_factory(verifiers: list[_FakeVerifier]) -> Callable[[], _FakeVerifier]:
    def _factory() -> _FakeVerifier:
        verifier = _FakeVerifier()
        verifiers.append(verifier)
        return verifier
    return _factory


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """实例 mys 会话目录形态（config/<实例>/mys 的 tmp 等价物）。"""
    return tmp_path / 'mys'


@pytest.fixture
def controller(
    session_dir: Path, send: _ScriptedHttpSend, verifier_factory: Callable[[], _FakeVerifier]
) -> MysAccessController:
    return MysAccessController(session_dir, send, verifier_factory)


# ---- 剧本响应构造 ----


def _json_result(payload: dict, set_cookie_lines: list[str] | None = None) -> HttpSendResult:
    headers: list[tuple[str, str]] = [('Content-Type', 'application/json')]
    headers.extend(('Set-Cookie', line) for line in (set_cookie_lines or []))
    return HttpSendResult(status=200, headers=headers, body=json.dumps(payload).encode('utf-8'))


def _need_verification_result(session_id: str) -> HttpSendResult:
    """-3101 + x-rpc-aigis 挑战响应（data 为字符串形态，走双层解析真实链路）。"""
    outer = {
        'session_id': session_id,
        'mmt_type': 1,
        'data': json.dumps({'use_v4': True, 'gt': 'gt-fixture-t4'}),
    }
    headers = [('x-rpc-aigis', json.dumps(outer))]
    return HttpSendResult(
        status=200, headers=headers,
        body=json.dumps({'retcode': -3101, 'message': '需要验证'}).encode('utf-8'),
    )


def _login_ok_result() -> HttpSendResult:
    lines = [f'{name}={value}; Path=/; HttpOnly' for name, value in _LOGIN_COOKIES.items()]
    return _json_result({'retcode': 0, 'message': 'OK', 'data': {}}, lines)


def _code_result(code: int) -> HttpSendResult:
    return _json_result({'retcode': code, 'message': 'fixture business failure'})


def _ticket() -> dict:
    """v4 形态票据样本（值任意，分诊只看 retcode）。"""
    return {'lot_number': 'lot-number-t4', 'captcha_output': 'co-t4', 'pass_token': 'pt-t4'}


def _roles_ok_route() -> tuple[str, HttpSendResult]:
    """角色发现成功剧本（单条崩铁国服角色）。"""
    role = {
        'game_biz': 'hkrpg_cn', 'game_uid': '100000001', 'region': 'prod_gf_cn',
        'region_name': '星穹列车', 'nickname': 'fixture', 'level': 60,
        'is_chosen': True, 'is_official': True, 'is_banned': False, 'unmask': [],
    }
    return (ROLE_LIST_URL, _json_result({'retcode': 0, 'message': 'OK', 'data': {'list': [role]}}))


def _index_snapshot_route() -> tuple[str, HttpSendResult]:
    snapshot = json.loads(INDEX_SNAPSHOT_PATH.read_bytes().decode('utf-8'))
    return (
        GAME_RECORD_BASE_URL + 'hkrpg/api/index',
        _json_result({'retcode': 0, 'message': 'OK', 'data': snapshot['data']}),
    )


def _assert_envelope_shape(envelope: dict) -> None:
    assert set(envelope.keys()) == {'status', 'message', 'data'}


# ---- 状态机主链 ----


def test_login_verification_then_ticket_ok_completes(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
    verifiers: list[_FakeVerifier],
) -> None:
    """主链：login → verification_required（attempt=1，回调已注册）→ 票据 ok →
    会话落盘（save_session_full 形态）+ idle（get_characters 真实成功）。"""
    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    env = controller.login(_USERNAME, _PASSWORD)

    _assert_envelope_shape(env)
    assert env['status'] == 'verification_required'
    assert '最多 3 次' in env['message']
    assert len(verifiers) == 1
    assert env['data']['url'] == verifiers[0].url
    assert [c.session_id for c in verifiers[0].started] == ['s-1']
    assert verifiers[0].on_ticket is not None  # 回调已注册（票据可送达）

    # 票据回传 ok：会话整体覆盖落盘、verifier 关闭
    send.add_route((LOGIN_URL, _login_ok_result()))
    verifiers[0].deliver({'session_id': 's-1', 'ticket': _ticket()})
    assert verifiers[0].closed is True
    saved = json.loads((session_dir / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert 'expired' not in saved  # save_session_full 形态（无 expired 键）
    assert saved['cookies'] == _LOGIN_COOKIES

    # idle 证明：get_characters 走真实数据请求成功（发现 + index）
    send.add_route(_roles_ok_route(), _index_snapshot_route())
    env2 = controller.get_characters()
    _assert_envelope_shape(env2)
    assert env2['status'] == 'success'
    assert [c['name'] for c in env2['data']] == ['藿藿', '米沙']


def test_verification_loop_capped_at_three_then_error_lingers(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
    verifiers: list[_FakeVerifier],
) -> None:
    """验证循环上限：票据被拒 → 同端口换题（attempt 递增，≤3）→ attempt≥3 →
    idle + verifier 关闭 + 留档错误在下次调用体现一次。"""
    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    controller.login(_USERNAME, _PASSWORD)

    send.add_route((LOGIN_URL, _need_verification_result('s-2')))
    verifiers[0].deliver({'session_id': 's-1', 'ticket': _ticket()})
    assert [c.session_id for c in verifiers[0].started] == ['s-1', 's-2']
    # 同端口语义：换题复用同一 verifier 实例（URL 不变），awaiting 期可观察
    env_mid = controller.get_characters()
    assert env_mid['status'] == 'verification_required'
    assert env_mid['data']['url'] == verifiers[0].url

    send.add_route((LOGIN_URL, _need_verification_result('s-3')))
    verifiers[0].deliver({'session_id': 's-2', 'ticket': _ticket()})
    assert [c.session_id for c in verifiers[0].started] == ['s-1', 's-2', 's-3']

    # 第 3 张票据仍被拒（attempt=3 ≥ 上限）→ 放弃：verifier 关闭、不再开新题
    send.add_route((LOGIN_URL, _need_verification_result('s-4')))
    verifiers[0].deliver({'session_id': 's-3', 'ticket': _ticket()})
    assert verifiers[0].closed is True
    assert len(verifiers[0].started) == 3
    assert len(send.calls_for(LOGIN_URL)) == 4  # 首轮 login + 3 次带票据重发

    # 留档错误在下次调用体现一次（design.md §2.4 验证循环第 2 步）
    env_err = controller.get_characters()
    assert env_err['status'] == 'error'
    assert '3 次未通过' in env_err['message']
    # 消费即清除：下次调用走正常业务路径（此处剧本给失效码）
    controller.store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index', _code_result(10001)))
    assert controller.get_characters()['status'] == 'session_expired'


def test_ticket_delivery_error_resets_and_leaves_files_untouched(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
    verifiers: list[_FakeVerifier],
) -> None:
    """验证循环异常路径：awaiting 期票据回传触发 complete_verification 抛
    MysApiError(-3208)（密码错误过多）→ 状态回 idle + verifier 关闭 + 错误
    留档在下次调用体现一次（-3208 与服务端文案透传）+ 不落盘不清文件
    （design.md §2.4 验证循环处置：无「失败清罐」路径）。"""
    # 预置会话（带过期标记——否则 login 走 already_logged_in 不进验证轮）
    # 与角色缓存：异常处置不得动它们
    controller.store.save_session_full({'ltoken_v2': 'keep-t4'})
    controller.store.mark_expired()
    controller.store.save_role({'role_id': '7', 'server': 'prod_gf_cn'})

    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    controller.login(_USERNAME, _PASSWORD)
    snapshot = {p.name: p.read_bytes() for p in session_dir.iterdir() if p.is_file()}

    send.add_route((LOGIN_URL, _json_result(
        {'retcode': -3208, 'message': '密码错误次数过多，请稍后再试'})))
    verifiers[0].deliver({'session_id': 's-1', 'ticket': _ticket()})
    assert verifiers[0].closed is True  # verifier 关闭
    assert len(send.calls_for(LOGIN_URL)) == 2  # 带票据重发恰一次，不补发
    files_after = {p.name: p.read_bytes() for p in session_dir.iterdir() if p.is_file()}
    assert files_after == snapshot  # 零落盘零改动（含 device.json）

    # 状态回 idle：错误留档在下次调用体现一次（若仍在 awaiting，会先撞状态闸
    # 返回 verification_required，看不到 error）
    env_err = controller.get_characters()
    assert env_err['status'] == 'error'
    assert '人机验证失败(retcode=-3208)' in env_err['message']
    assert '密码错误次数过多' in env_err['message']

    # 消费即清除：下次调用走正常业务路径（预置会话带过期标记 → 过期短路信封）
    assert controller.get_characters()['status'] == 'session_expired'


def test_cancelled_resets_then_new_login_builds_new_verifier(
    controller: MysAccessController, send: _ScriptedHttpSend, verifiers: list[_FakeVerifier],
) -> None:
    """cancelled 回传 → idle + verifier 关闭；重登走全新验证轮（新 verifier
    实例，不复用已关闭旧实例）。"""
    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    controller.login(_USERNAME, _PASSWORD)

    verifiers[0].deliver({'session_id': 's-1', 'cancelled': True})
    assert verifiers[0].closed is True

    send.add_route((LOGIN_URL, _need_verification_result('s-9')))
    env = controller.login(_USERNAME, _PASSWORD)
    assert env['status'] == 'verification_required'
    assert len(verifiers) == 2  # 全新 verifier 实例
    assert verifiers[1].started[0].session_id == 's-9'
    assert env['data']['url'] == verifiers[1].url


# ---- awaiting 期并发语义 ----


def test_second_login_while_awaiting_reuses_url_and_discards_credentials(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
    verifiers: list[_FakeVerifier],
) -> None:
    """awaiting 期二次 login：复用现存 URL、新账密即弃（无第二次登录请求）；
    原票据仍可用（丢弃调用不破坏状态）。"""
    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    controller.login(_USERNAME, _PASSWORD)

    env = controller.login(_OTHER_USER, _OTHER_PASSWORD)
    assert env['status'] == 'verification_required'
    assert env['data']['url'] == verifiers[0].url
    assert len(send.calls_for(LOGIN_URL)) == 1  # 新账密未产生第二次登录请求

    send.add_route((LOGIN_URL, _login_ok_result()))
    verifiers[0].deliver({'session_id': 's-1', 'ticket': _ticket()})
    saved = json.loads((session_dir / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['cookies'] == _LOGIN_COOKIES  # 会话来自首轮票据，非被弃账密


def test_get_characters_while_awaiting_does_not_fire_requests(
    controller: MysAccessController, send: _ScriptedHttpSend, verifiers: list[_FakeVerifier],
) -> None:
    """awaiting 期 get_characters：verification_required 信封（附现存 URL），
    不裸打任何数据/发现请求。"""
    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    controller.login(_USERNAME, _PASSWORD)

    env = controller.get_characters()
    assert env['status'] == 'verification_required'
    assert env['data']['url'] == verifiers[0].url
    assert send.calls_for(GAME_RECORD_BASE_URL) == []
    assert send.calls_for(ROLE_LIST_URL) == []


def test_logout_while_awaiting_cancels_and_drops_late_ticket(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
    verifiers: list[_FakeVerifier],
) -> None:
    """awaiting 期 logout：清会话 + idle + verifier 关闭；迟到票据被丢弃
    （不静默重建会话，design.md §2.4 并发语义第 3 条）。"""
    # 预置过期会话与角色缓存：过期态下 login 进入验证轮，登出须连旧文件一起清
    controller.store.save_session_full({'stale': 'v'})
    controller.store.mark_expired()
    controller.store.save_role({'role_id': '9', 'server': 'prod_gf_cn'})

    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    env = controller.login(_USERNAME, _PASSWORD)
    assert env['status'] == 'verification_required'  # 过期 → 跳过已登录判定

    env_out = controller.logout()
    assert env_out['status'] == 'success'
    assert verifiers[0].closed is True
    assert not (session_dir / SESSION_FILE_NAME).exists()
    assert not (session_dir / ROLE_FILE_NAME).exists()

    # 迟到票据：状态闸丢弃——无重发请求、无会话重建
    send.add_route((LOGIN_URL, _login_ok_result()))
    verifiers[0].deliver({'session_id': 's-1', 'ticket': _ticket()})
    assert len(send.calls_for(LOGIN_URL)) == 1  # 票据未触发 complete_verification
    assert not (session_dir / SESSION_FILE_NAME).exists()

    # 会话确未重建：后续数据请求按无会话剧本走真实请求并失败
    send.add_route(_roles_ok_route())
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index', _code_result(10001)))
    assert controller.get_characters()['status'] == 'session_expired'


def test_ticket_session_id_mismatch_while_awaiting_discarded(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
    verifiers: list[_FakeVerifier],
) -> None:
    """awaiting 期错配回传独立触发配对闸（verifier 层 409 之外的第二道闸，
    design.md §2.4 迟到票据双重防护）：payload.session_id 与当前挑战不一致 →
    丢弃——状态保持 awaiting、不触发 complete_verification、attempt 不消耗
    （后续换题不受错配挤占）。"""
    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    controller.login(_USERNAME, _PASSWORD)

    # 错配回传携带合法形态票据：若配对闸失效会触发重发，断言锁的才是
    # 「配对闸」而非「无票据兜底」；错配两次，把 attempt 挤占放大到可观测
    send.add_route((LOGIN_URL, _login_ok_result()))
    verifiers[0].deliver({'session_id': 's-wrong-1', 'ticket': _ticket()})
    verifiers[0].deliver({'session_id': 's-wrong-2', 'ticket': _ticket()})
    assert len(send.calls_for(LOGIN_URL)) == 1  # 未触发 complete_verification
    assert verifiers[0].closed is False  # 验证轮未被打断
    assert [c.session_id for c in verifiers[0].started] == ['s-1']  # 未换题
    env = controller.get_characters()
    assert env['status'] == 'verification_required'  # 状态保持 awaiting
    assert env['data']['url'] == verifiers[0].url

    # attempt 未被错配消耗：正确票据被拒换题仍走「未达上限」分支——若错配
    # 各消耗一次，attempt 已 ≥3，此处会直接放弃而不开新题 s-2
    send.add_route((LOGIN_URL, _need_verification_result('s-2')))
    verifiers[0].deliver({'session_id': 's-1', 'ticket': _ticket()})
    assert [c.session_id for c in verifiers[0].started] == ['s-1', 's-2']
    assert verifiers[0].closed is False

    # 换题后正确票据照常收口（丢弃路径未污染状态机）
    send.add_route((LOGIN_URL, _login_ok_result()))
    verifiers[0].deliver({'session_id': 's-2', 'ticket': _ticket()})
    assert verifiers[0].closed is True
    assert len(send.calls_for(LOGIN_URL)) == 3  # 首轮 + 被拒重发 + 成功重发
    saved = json.loads((session_dir / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['cookies'] == _LOGIN_COOKIES


def test_logout_idempotent_without_session(controller: MysAccessController) -> None:
    """无会话登出幂等：连续两次均 success。"""
    assert controller.logout()['status'] == 'success'
    assert controller.logout()['status'] == 'success'


# ---- 过期标记序列 ----


def test_expired_mark_sequence_preserves_files_until_success(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
) -> None:
    """过期标记序列（landing §3.4 判据）：session_expired → 只打标记
    （session.json 保留 + role.json 保留）→ 标记后 login 不再
    already_logged_in → 登录失败（-3208）旧文件原样保留 → 登录成功整体
    覆盖、标记消失。过期清罐序列不存在。"""
    controller.store.save_session_full({'ltoken_v2': 'keep-t4'})
    controller.store.save_role({'role_id': '5', 'server': 'prod_gf_cn'})

    # 1) 会话失效：标记写入 + 文件保留 + 信封 session_expired
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index', _code_result(10001)))
    env = controller.get_characters()
    assert env['status'] == 'session_expired'
    assert env['message'] == SESSION_EXPIRED_MESSAGE
    saved = json.loads((session_dir / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['expired'] is True
    assert saved['cookies'] == {'ltoken_v2': 'keep-t4'}  # cookies 原样保留
    assert (session_dir / ROLE_FILE_NAME).exists()

    # 2) 标记后登录：不再 already_logged_in（跳过判定走正常登录）；
    #    登录失败（-3208）→ 旧文件原样保留
    send.add_route((LOGIN_URL, _code_result(-3208)))
    env_fail = controller.login(_USERNAME, _PASSWORD)
    assert env_fail['status'] == 'error'
    assert 'retcode=-3208' in env_fail['message']
    assert json.loads((session_dir / SESSION_FILE_NAME).read_bytes().decode('utf-8')) == saved
    assert (session_dir / ROLE_FILE_NAME).exists()

    # 3) 登录成功：save_session_full 整体覆盖 → 标记消失
    send.add_route((LOGIN_URL, _login_ok_result()))
    env_ok = controller.login(_USERNAME, _PASSWORD)
    assert env_ok['status'] == 'success'
    saved_ok = json.loads((session_dir / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert 'expired' not in saved_ok
    assert saved_ok['cookies'] == _LOGIN_COOKIES


# ---- 装配断言 ----


def test_assembly_wiring_same_store_and_injected_send(
    tmp_path: Path, verifiers: list[_FakeVerifier], verifier_factory: Callable[[], _FakeVerifier],
) -> None:
    """装配断言（landing §3.4 判据）：控制器构造的 MysClient/DeviceIdentity
    持有传入的 http_send 实例与同一 SessionStore 实例（同实例同锁）；缺任一
    构造参数 → TypeError（无默认路径）。"""
    fake_send = _ScriptedHttpSend()
    controller = MysAccessController(tmp_path, fake_send, verifier_factory)

    assert controller.client._store is controller.device._store is controller.store
    assert controller.client._http_send is fake_send
    assert controller.device._http_send is fake_send

    with pytest.raises(TypeError):
        MysAccessController()  # 全缺
    with pytest.raises(TypeError):
        MysAccessController(tmp_path, fake_send)  # 缺 verifier_factory


def test_real_assembly_injects_requests_and_webbrowser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真装配链（运行入口形态）：RequestsHttpSend 单实例贯穿 client/device，
    默认 verifier 工厂产出 AigisVerifier 且 open_browser 接 webbrowser.open
    （monkeypatch 拦截，不弹真实浏览器）。"""
    real = MysAccessController(tmp_path, RequestsHttpSend(), mys_tools._default_verifier_factory)
    assert isinstance(real.client._http_send, RequestsHttpSend)
    assert real.client._http_send is real.device._http_send

    calls: list[str] = []
    monkeypatch.setattr(webbrowser, 'open', lambda url: calls.append(url))
    verifier = mys_tools._default_verifier_factory()
    assert isinstance(verifier, AigisVerifier)
    assert verifier._open_browser is mys_tools._open_verify_page  # 装配链闭合
    mys_tools._open_verify_page('http://127.0.0.1:1/verify')
    assert calls == ['http://127.0.0.1:1/verify']


# ---- 信封五态与脱敏 ----


def test_envelope_five_states_and_risk_control_1034(
    controller: MysAccessController, send: _ScriptedHttpSend, verifiers: list[_FakeVerifier],
) -> None:
    """信封五态齐全 + 1034 专属文案。"""
    # already_logged_in（无请求：不主动探测官方接口）
    controller.store.save_session_full({'ok': 'v'})
    env_logged = controller.login(_USERNAME, _PASSWORD)
    assert env_logged['status'] == 'already_logged_in'
    assert send.calls_for(LOGIN_URL) == []

    # session_expired
    controller.store.mark_expired()
    controller.store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index', _code_result(10001)))
    env_expired = controller.get_characters()
    assert env_expired['status'] == 'session_expired'

    # verification_required
    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    env_verify = controller.login(_USERNAME, _PASSWORD)
    assert env_verify['status'] == 'verification_required'
    assert env_verify['data']['url'] == verifiers[0].url

    # 取消回位（idle），logout 清掉过期标记（真实恢复路径），继续剩余两态
    verifiers[0].deliver({'session_id': 's-1', 'cancelled': True})
    controller.logout()
    controller.store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})

    # error（1034 专属文案）
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index',
                    _json_result({'retcode': 1034, 'message': '请求遇到验证码'})))
    env_1034 = controller.get_characters()
    assert env_1034['status'] == 'error'
    assert env_1034['message'] == mys_tools.RISK_CONTROL_1034_MESSAGE

    # error（通用业务码）
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index', _code_result(-1)))
    env_err = controller.get_characters()
    assert env_err['status'] == 'error'
    assert 'retcode=-1' in env_err['message']

    # success（角色列表）
    send.add_route(_roles_ok_route(), _index_snapshot_route())
    env_ok = controller.get_characters()
    assert env_ok['status'] == 'success'
    assert isinstance(env_ok['data'], list) and env_ok['data']


def test_envelopes_never_contain_credentials(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
    verifiers: list[_FakeVerifier],
) -> None:
    """信封脱敏（landing §3.4 判据）：全部信封的序列化文本不含账号/密码/
    cookie 值/票据内容。"""
    collected: list[dict] = []

    controller.store.save_session_full({'ltoken_v2': 'ltv2-secret-t4', 'account_mid_v2': 'mid-secret-t4'})
    collected.append(controller.login(_USERNAME, _PASSWORD))  # already_logged_in
    controller.store.mark_expired()
    controller.store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index', _code_result(10001)))
    collected.append(controller.get_characters())  # session_expired
    send.add_route((LOGIN_URL, _need_verification_result('s-1')))
    collected.append(controller.login(_USERNAME, _PASSWORD))  # verification_required
    collected.append(controller.login(_OTHER_USER, _OTHER_PASSWORD))  # awaiting 复用

    send.add_route((LOGIN_URL, _login_ok_result()))
    verifiers[0].deliver({'session_id': 's-1', 'ticket': _ticket()})  # 票据 ok（不在信封）

    send.add_route(_roles_ok_route(), _index_snapshot_route())
    collected.append(controller.get_characters())  # success（data=角色数组）

    controller.logout()  # 回到 idle
    send.add_route((LOGIN_URL, _code_result(-3208)))
    collected.append(controller.login(_USERNAME, _PASSWORD))  # error（登录失败）

    for envelope in collected:
        _assert_envelope_shape(envelope)
        text = json.dumps(envelope, ensure_ascii=False)
        for secret in _SECRET_SAMPLES:
            assert secret not in text, f'信封泄露机密样本: {secret}'


# ---- 工具注册与 description ----


def test_tool_descriptions_and_registration() -> None:
    """三工具注册 + mys_login description 含知情声明关键句（landing §3.4 判据：
    经注册函数取 description 文本断言）。注册期不构建控制器（MagicMock backend
    零副作用）。"""
    mcp = FastMCP('t4-tools')
    register_mys_tools(mcp, MagicMock(name='SrBackendContext'))

    names = set(mcp._tool_manager._tools.keys())
    assert {'mys_login', 'mys_logout', 'mys_get_characters'} <= names

    login_desc = mcp._tool_manager._tools['mys_login'].description
    assert '密码会作为工具参数传入大模型上下文' in login_desc
    assert '是否继续由使用者自行决定' in login_desc
    assert 'config/当前实例/mys/session.json' in login_desc
    assert '密码不落盘' in login_desc


def test_app_server_mounts_mys_tools() -> None:
    """create_mcp_server 挂载三工具（app.py 装配点）。"""
    mcp = create_mcp_server(MagicMock(name='SrBackendContext'))
    assert {'mys_login', 'mys_logout', 'mys_get_characters'} <= set(mcp._tool_manager._tools.keys())


# ---- mys_get_roster_detail（changes/mys-roster-detail design.md §2 契约 5：
# 信封五态与 mys_get_characters 完全一致 + detail 序列化载荷形态 + 脱敏）----

#: index 全量明细自造样例（T-2 交付 fixture：结构对照 2026-11-03 实测快照，
#: id/名值自造不绑真账号；甲全量形态 / 乙无光锥无遗器 / 丙遗器缺件三形态）
DETAIL_SAMPLE_PATH: Path = (
    Path(__file__).resolve().parents[3] / 'fixtures' / 'mys' / 'hkrpg_index_detail_sample.json'
)

#: 新工具 description 的定死开头段（任务书原文，锁「描述文案定死」）
ROSTER_DETAIL_DESC_OPENING: str = (
    '获取崩坏:星穹铁道全角色名册明细（每名角色的遗器六件套词条明细/位面饰品/'
    '星魂/行迹/属性面板，词条与面板属性均为中文名）。数据量较大（64 角色全量）。'
    '会话过期时返回 session_expired 并提示重新登录，不清除任何本机数据'
)


def _detail_sample_route() -> tuple[str, HttpSendResult]:
    snapshot = json.loads(DETAIL_SAMPLE_PATH.read_bytes().decode('utf-8'))
    return (
        GAME_RECORD_BASE_URL + 'hkrpg/api/index',
        _json_result({'retcode': 0, 'message': 'OK', 'data': snapshot['data']}),
    )


def test_get_roster_detail_success_payload_shape(
    controller: MysAccessController, send: _ScriptedHttpSend,
) -> None:
    """success：detail 序列化载荷形态断言（契约 3/4 冻结字段集经
    character_to_dict 逐层展开）——顶层十字段+五组明细、子结构字段名集合、
    中文字段随载荷、times 透传；乙无光锥无遗器形态照常出载荷。"""
    controller.store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    send.add_route(_detail_sample_route())

    env = controller.get_roster_detail()

    _assert_envelope_shape(env)
    assert env['status'] == 'success'
    assert env['message'] == '共获取 3 名角色明细'
    data = env['data']
    assert isinstance(data, list) and len(data) == 3
    assert [item['name'] for item in data] == ['样例角色甲', '样例角色乙', '样例角色丙']

    # 甲（全量形态）：顶层冻结字段集 + 轻口径中文字段 + 光锥摘要
    first = data[0]
    assert set(first.keys()) == {
        'id', 'name', 'level', 'rarity', 'rank', 'element', 'element_cn',
        'base_type', 'base_type_cn', 'equip', 'relics', 'ornaments', 'ranks',
        'skills', 'properties',
    }
    assert first['element_cn'] == '火'
    assert first['base_type_cn'] == '巡猎'
    assert first['equip'] == {'name': '样例光锥・晨昏线', 'level': 80, 'rank': 1, 'rarity': 5}

    # 遗器六件套：pos_cn 部位查表、main/subs 词条三元组（times 透传）
    relic = first['relics'][0]
    assert set(relic.keys()) == {'name', 'pos', 'pos_cn', 'rarity', 'level', 'main', 'subs'}
    assert relic['pos_cn'] == '头部'
    assert relic['main'] == {'name_cn': '生命值', 'value': '705', 'times': 0}
    assert relic['subs'][0] == {'name_cn': '防御力', 'value': '59', 'times': 3}
    # 位面饰品与遗器同构映射
    assert first['ornaments'][0]['pos_cn'] == '位面球'
    assert first['ornaments'][0]['main'] == {'name_cn': '生命值', 'value': '43.2%', 'times': 0}
    # 星魂：全量透传解锁状态，无 pos_cn（星魂 pos 是星魂序号，禁查部位表）
    assert set(first['ranks'][0].keys()) == {'pos', 'name', 'desc', 'is_unlocked'}
    assert [r['is_unlocked'] for r in first['ranks']] == [True, True, False, False, False, False]
    # 行迹：name 取 remake 标签，终结技两段分段文案
    skill = first['skills'][2]
    assert set(skill.keys()) == {'name', 'level', 'is_activated', 'stages'}
    assert skill['name'] == '终结技'
    assert len(skill['stages']) == 2
    assert set(skill['stages'][0].keys()) == {'name', 'desc', 'level'}
    # 面板属性行：name_cn 查表 + base/add/final 字符串透传
    assert set(first['properties'][0].keys()) == {'name_cn', 'base', 'add', 'final'}
    assert first['properties'][0] == {
        'name_cn': '生命值', 'base': '2406', 'add': '2005', 'final': '4411',
    }

    # 乙（无光锥无遗器形态）：equip=None + 空明细数组照常出载荷
    second = data[1]
    assert second['equip'] is None
    assert second['relics'] == []
    assert second['ornaments'] == []


def test_get_roster_detail_while_awaiting_does_not_fire_requests(
    controller: MysAccessController, send: _ScriptedHttpSend, verifiers: list[_FakeVerifier],
) -> None:
    """awaiting 期 get_roster_detail：verification_required 信封（附现存 URL），
    不裸打任何数据/发现请求（契约 5：信封语义与 mys_get_characters 完全一致）。"""
    send.add_route((LOGIN_URL, _need_verification_result('s-rd-1')))
    controller.login(_USERNAME, _PASSWORD)

    env = controller.get_roster_detail()
    _assert_envelope_shape(env)
    assert env['status'] == 'verification_required'
    assert env['data']['url'] == verifiers[0].url
    assert send.calls_for(GAME_RECORD_BASE_URL) == []
    assert send.calls_for(ROLE_LIST_URL) == []


def test_get_roster_detail_expired_and_risk_control_states(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
) -> None:
    """session_expired（过期标记写入文件，旧文件原样保留）+ 1034 专属文案 +
    通用业务码透传（契约 5：三态语义与 mys_get_characters 完全一致）。"""
    controller.store.save_session_full({'ltoken_v2': 'keep-t4'})
    controller.store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})

    # 服务端会话失效码 → session_expired 信封 + 过期标记落盘 + 文件保留
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index', _code_result(10001)))
    env = controller.get_roster_detail()
    _assert_envelope_shape(env)
    assert env['status'] == 'session_expired'
    assert env['message'] == SESSION_EXPIRED_MESSAGE
    saved = json.loads((session_dir / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['expired'] is True
    assert saved['cookies'] == {'ltoken_v2': 'keep-t4'}
    assert (session_dir / ROLE_FILE_NAME).exists()

    # 标记后调用：本地过期短路直接信封返回，零新增请求（calls_for 含首调用那次）
    env_short = controller.get_roster_detail()
    assert env_short['status'] == 'session_expired'
    assert len(send.calls_for(GAME_RECORD_BASE_URL)) == 1

    # 整体覆盖清除标记（登录成功同款路径）→ 1034 专属文案
    controller.store.save_session_full({'ok': 'v'})
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index',
                    _json_result({'retcode': 1034, 'message': '请求遇到验证码'})))
    env_1034 = controller.get_roster_detail()
    assert env_1034['status'] == 'error'
    assert env_1034['message'] == mys_tools.RISK_CONTROL_1034_MESSAGE

    # 通用业务码 → error 透传 retcode
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index', _code_result(-1)))
    env_err = controller.get_roster_detail()
    assert env_err['status'] == 'error'
    assert '获取角色明细失败(retcode=-1)' in env_err['message']


def test_get_roster_detail_envelopes_never_contain_credentials(
    controller: MysAccessController, session_dir: Path, send: _ScriptedHttpSend,
    verifiers: list[_FakeVerifier],
) -> None:
    """信封脱敏（沿用 landing §3.4 判据）：detail 序列化载荷与全部信封的
    序列化文本不含账号/密码/cookie 值/票据内容。"""
    collected: list[dict] = []

    # success：会话带机密 cookie，明细载荷（fixture 自造名值）不得携带它们
    controller.store.save_session_full({'ltoken_v2': 'ltv2-secret-t4', 'account_mid_v2': 'mid-secret-t4'})
    controller.store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    send.add_route(_detail_sample_route())
    collected.append(controller.get_roster_detail())
    assert collected[-1]['status'] == 'success'

    # session_expired：本地短路（零新增请求，calls_for 含 success 那一次）
    controller.store.mark_expired()
    collected.append(controller.get_roster_detail())
    assert collected[-1]['status'] == 'session_expired'
    assert len(send.calls_for(GAME_RECORD_BASE_URL)) == 1

    # verification_required（过期态 login 进验证轮）+ awaiting 期复用
    send.add_route((LOGIN_URL, _need_verification_result('s-rd-2')))
    collected.append(controller.login(_USERNAME, _PASSWORD))
    collected.append(controller.login(_OTHER_USER, _OTHER_PASSWORD))
    verifiers[0].deliver({'session_id': 's-rd-2', 'cancelled': True})  # 回 idle
    controller.logout()  # 清文件回干净态

    # error（1034 专属文案）：重置会话后打风险码
    controller.store.save_session_full({'ok': 'v'})
    controller.store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    send.add_route((GAME_RECORD_BASE_URL + 'hkrpg/api/index',
                    _json_result({'retcode': 1034, 'message': '请求遇到验证码'})))
    collected.append(controller.get_roster_detail())

    assert len(collected) == 5
    for envelope in collected:
        _assert_envelope_shape(envelope)
        text = json.dumps(envelope, ensure_ascii=False)
        for secret in _SECRET_SAMPLES:
            assert secret not in text, f'信封泄露机密样本: {secret}'


def test_roster_detail_tool_description_and_registration() -> None:
    """mys_get_roster_detail 注册 + description 含定死文案关键句（经注册函数取
    description 文本断言）。注册期不构建控制器（MagicMock backend 零副作用）。"""
    mcp = FastMCP('t3-roster-detail-tools')
    register_mys_tools(mcp, MagicMock(name='SrBackendContext'))

    assert 'mys_get_roster_detail' in set(mcp._tool_manager._tools.keys())

    desc = mcp._tool_manager._tools['mys_get_roster_detail'].description
    assert desc.startswith(ROSTER_DETAIL_DESC_OPENING)
    assert '遗器' in desc
    assert '不清除任何本机数据' in desc
