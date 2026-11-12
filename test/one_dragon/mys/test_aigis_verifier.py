"""AigisVerifier 本地验证页服务单测（服务端回传契约逐条）。

零真实外网：服务绑 127.0.0.1 随机端口（port=0），请求全部 requests 打本机
回环；等待类断言用短超时护栏（≤1s）；open_browser 注入记录器断言不弹真实
浏览器（默认 None 构造单独覆盖一条）。

页面 JS 的双缺/取消/onSuccess 分支属浏览器侧行为（pytest 无 JS 引擎，归
实机覆盖），本文件锁其服务端契约：cancelled / ticket 回传的分派、配对校验、
跨站防线——即页面回传 payload 后服务端应表现的行为。
"""

from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
import requests

from one_dragon.mys.aigis_verifier import AigisVerifier
from one_dragon.mys.mys_client import AigisChallenge

#: 短超时护栏（秒）：wait_ticket 等待类断言用，远小于默认 300
_SHORT_WAIT_SECONDS: float = 0.3

_GT4_DATA: dict = {
    'gt': 'captcha-id-fixture',
    'risk_type': 'slide',
    'success': 1,
    'new_captcha': 1,
    'use_v4': True,
}
_GT3_DATA: dict = {
    'gt': 'captcha-id-fixture',
    'challenge': 'challenge-fixture',
    'success': 1,
    'new_captcha': 1,
}
_TICKET: dict = {
    'lot_number': 'lot-1',
    'captcha_output': 'co-1',
    'pass_token': 'pt-1',
    'gen_time': '1730000000',
}


def _challenge(session_id: str, data: dict) -> AigisChallenge:
    return AigisChallenge(session_id=session_id, mmt_type=1, data=data, raw_header='{}')


@pytest.fixture
def browser_calls() -> list[str]:
    """open_browser 注入的记录器（断言不弹真实浏览器）。"""
    return []


@pytest.fixture
def verifier(browser_calls: list[str]) -> Iterator[AigisVerifier]:
    """带浏览器记录器的验证页宿主（收尾 close 释放端口）。"""
    instance = AigisVerifier(open_browser=browser_calls.append)
    yield instance
    instance.close()


def _post_ticket(verify_url: str, payload: dict, headers: dict[str, str] | None = None) -> requests.Response:
    return requests.post(f'{_base_of(verify_url)}/ticket', json=payload, headers=headers, timeout=5)


def _base_of(verify_url: str) -> str:
    """验证页 URL 去掉 /verify 后缀的服务基座（http://127.0.0.1:<port>）。"""
    return verify_url.removesuffix('/verify')


def _origin_of(base_url: str) -> str:
    parts = urlsplit(base_url)
    return f'http://{parts.hostname}:{parts.port}'


# ---- start：端口与 URL 形态 ----


def test_start_binds_random_port_and_url_carries_no_challenge(
    verifier: AigisVerifier, browser_calls: list[str]
) -> None:
    """start 返回 http://127.0.0.1:<随机端口>/verify；URL 不含任何挑战参数；
    open_browser 注入记录器被恰调用一次且参数即该 URL（不弹真实浏览器）。"""
    url = verifier.start(_challenge('session-1', _GT4_DATA))

    assert url.startswith('http://127.0.0.1:')
    assert url.endswith('/verify')
    assert '?' not in url  # 挑战不下沉 URL：无 query 参数
    for forbidden in ('session', 'challenge', 'gt'):
        assert forbidden not in url
    assert browser_calls == [url]


def test_default_open_browser_none_never_opens_browser() -> None:
    """默认 open_browser=None：只返回 URL，不触发任何打开浏览器动作
    （AGENTS.md §7 纪律：外部 IO 回调默认不做事）。"""
    instance = AigisVerifier()
    try:
        url = instance.start(_challenge('session-1', _GT4_DATA))
        assert url.startswith('http://127.0.0.1:')
    finally:
        instance.close()


def test_close_releases_port_and_instance_unusable(verifier: AigisVerifier) -> None:
    """close 释放端口：关闭后对同端口的连接失败；close 幂等；关闭后再 start
    报 RuntimeError（重开验证须新建实例）。"""
    url = verifier.start(_challenge('session-1', _GT4_DATA))
    verifier.close()
    verifier.close()  # 幂等

    with pytest.raises(requests.ConnectionError):
        requests.get(url, timeout=2)
    with pytest.raises(RuntimeError):
        verifier.start(_challenge('session-2', _GT4_DATA))


# ---- 验证页与挑战下发 ----


def test_verify_page_serves_dual_geetest_scripts_and_csp(verifier: AigisVerifier) -> None:
    """GET /verify 返回内嵌 HTML：gt4 + gt3 双组件脚本同载、no-referrer meta、
    CSP 白名单头在场（geetest/mihoyo/webstatic 域）。"""
    verify_url = verifier.start(_challenge('session-1', _GT4_DATA))
    response = requests.get(verify_url, timeout=5)

    assert response.status_code == 200
    csp = response.headers['Content-Security-Policy']
    assert csp.startswith("default-src 'self'")
    assert 'geetest.com' in csp
    assert 'webstatic.mihoyo.com' in csp
    html = response.text
    assert 'https://webstatic.mihoyo.com/dora/lib/geetest/v4/gt4.js' in html
    assert 'https://static.geetest.com/static/js/gt.0.5.0.js' in html
    assert '<meta name="referrer" content="no-referrer">' in html


def test_get_challenge_returns_pending_challenge(verifier: AigisVerifier) -> None:
    """GET /challenge 返回当前 pending 挑战 JSON（页面取题数据源）。"""
    verify_url = verifier.start(_challenge('session-1', _GT4_DATA))
    response = requests.get(f'{_base_of(verify_url)}/challenge', timeout=5)

    assert response.status_code == 200
    payload = response.json()
    assert payload['session_id'] == 'session-1'
    assert payload['data'] == _GT4_DATA


def test_start_new_challenge_refresh_gets_latest(verifier: AigisVerifier) -> None:
    """二次 start（新挑战）后 GET /challenge 返回新挑战——刷新页面即取最新
    题目（服务端持有模式核心语义，不存在旧 URL 解旧题）。"""
    first_url = verifier.start(_challenge('session-1', _GT4_DATA))
    second_url = verifier.start(_challenge('session-2', _GT3_DATA))
    assert first_url == second_url  # 同端口复用，URL 不变

    payload = requests.get(f'{_base_of(second_url)}/challenge', timeout=5).json()
    assert payload['session_id'] == 'session-2'
    assert payload['data'] == _GT3_DATA


# ---- POST /ticket：防线与配对 ----


def test_post_ticket_matching_session_delivers(
    verifier: AigisVerifier, browser_calls: list[str]
) -> None:
    """配对合格的票据回传：wait_ticket 取回原 payload、on_ticket 恰调用一次；
    回调记录器与阻塞等待两条消费通路拿到同一份内容。"""
    on_ticket_seen: list[dict] = []
    verifier.on_ticket = on_ticket_seen.append
    verify_url = verifier.start(_challenge('session-1', _GT4_DATA))

    response = _post_ticket(verify_url, {'session_id': 'session-1', 'ticket': _TICKET})
    assert response.status_code == 200

    delivered = verifier.wait_ticket(_SHORT_WAIT_SECONDS)
    assert delivered == {'session_id': 'session-1', 'ticket': _TICKET}
    assert on_ticket_seen == [{'session_id': 'session-1', 'ticket': _TICKET}]
    assert browser_calls == [verify_url]  # open_browser 只在 start 被调


def test_post_ticket_session_mismatch_rejected_409(verifier: AigisVerifier) -> None:
    """session_id 与 pending 不一致 → 409 丢弃（防旧页面解旧题的迟到票据
    污染新一轮挑战），不进 wait_ticket。"""
    base_url = verifier.start(_challenge('session-1', _GT4_DATA))

    response = _post_ticket(base_url, {'session_id': 'stale-old-session', 'ticket': _TICKET})
    assert response.status_code == 409
    assert verifier.wait_ticket(_SHORT_WAIT_SECONDS) is None


def test_post_ticket_cross_site_and_foreign_origin_denied_403(
    verifier: AigisVerifier,
) -> None:
    """跨站防线（照参考实现 server.mjs:16 手法）：sec-fetch-site=cross-site 或
    Origin 非本服务 → 403；同源标头（same-origin + 本服务 Origin）不受影响。"""
    base_url = verifier.start(_challenge('session-1', _GT4_DATA))
    payload = {'session_id': 'session-1', 'ticket': _TICKET}

    cross_site = _post_ticket(base_url, payload, headers={'Sec-Fetch-Site': 'cross-site'})
    assert cross_site.status_code == 403
    foreign_origin = _post_ticket(base_url, payload, headers={'Origin': 'http://evil.example.com'})
    assert foreign_origin.status_code == 403
    assert verifier.wait_ticket(_SHORT_WAIT_SECONDS) is None  # 拒绝的回传不进等待方

    same_origin = _post_ticket(
        base_url,
        payload,
        headers={'Sec-Fetch-Site': 'same-origin', 'Origin': _origin_of(base_url)},
    )
    assert same_origin.status_code == 200
    assert verifier.wait_ticket(_SHORT_WAIT_SECONDS) == {'session_id': 'session-1', 'ticket': _TICKET}


def test_post_ticket_contract_violation_400(verifier: AigisVerifier) -> None:
    """契约外回传（既无 ticket 也非 cancelled）→ 400，不进等待方。"""
    base_url = verifier.start(_challenge('session-1', _GT4_DATA))

    response = _post_ticket(base_url, {'session_id': 'session-1'})
    assert response.status_code == 400
    assert verifier.wait_ticket(_SHORT_WAIT_SECONDS) is None


# ---- 取消语义与超时语义 ----


def test_cancelled_payload_dispatched_to_both_consumers(verifier: AigisVerifier) -> None:
    """cancelled 回传（页面双缺/关闭/出错时发出）：按取消语义记录并分派给
    wait_ticket 与 on_ticket 两条消费通路。"""
    on_ticket_seen: list[dict] = []
    verifier.on_ticket = on_ticket_seen.append
    base_url = verifier.start(_challenge('session-1', _GT4_DATA))

    response = _post_ticket(base_url, {'session_id': 'session-1', 'cancelled': True})
    assert response.status_code == 200

    delivered = verifier.wait_ticket(_SHORT_WAIT_SECONDS)
    assert delivered == {'session_id': 'session-1', 'cancelled': True}
    assert on_ticket_seen == [{'session_id': 'session-1', 'cancelled': True}]


def test_wait_ticket_timeout_keeps_service_and_pending_intact(
    verifier: AigisVerifier,
) -> None:
    """wait_ticket 超时：返回 None，只结束等待调用本身——pending 不变、服务
    仍可用（超时后回传照样可达）。"""
    base_url = verifier.start(_challenge('session-1', _GT4_DATA))

    assert verifier.wait_ticket(_SHORT_WAIT_SECONDS) is None
    payload = requests.get(f'{_base_of(base_url)}/challenge', timeout=5).json()
    assert payload['session_id'] == 'session-1'  # pending 未被超时清理

    _post_ticket(base_url, {'session_id': 'session-1', 'ticket': _TICKET})
    assert verifier.wait_ticket(1.0) == {'session_id': 'session-1', 'ticket': _TICKET}


def test_start_new_challenge_clears_previous_payload(verifier: AigisVerifier) -> None:
    """start 挂载新挑战 = 新一轮验证：上一轮回传被清空，等待方拿不到旧票据。"""
    base_url = verifier.start(_challenge('session-1', _GT4_DATA))
    _post_ticket(base_url, {'session_id': 'session-1', 'ticket': _TICKET})
    assert verifier.wait_ticket(_SHORT_WAIT_SECONDS) is not None

    verifier.start(_challenge('session-2', _GT4_DATA))
    assert verifier.wait_ticket(_SHORT_WAIT_SECONDS) is None  # 旧轮票据不再可达


def test_on_ticket_callback_exception_does_not_break_service(
    verifier: AigisVerifier,
) -> None:
    """on_ticket 回调抛异常：服务线程不倒（回传已记录，wait_ticket 仍可达）。"""

    def _boom(_: dict) -> None:
        raise RuntimeError('controller callback exploded')

    verifier.on_ticket = _boom
    base_url = verifier.start(_challenge('session-1', _GT4_DATA))

    response = _post_ticket(base_url, {'session_id': 'session-1', 'ticket': _TICKET})
    assert response.status_code == 200
    assert verifier.wait_ticket(_SHORT_WAIT_SECONDS) == {'session_id': 'session-1', 'ticket': _TICKET}
