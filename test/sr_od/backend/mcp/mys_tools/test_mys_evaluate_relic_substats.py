"""mys_evaluate_relic_substats 注册层单测（description 契约 + roster_data
双路径信封语义）。

出处：评估工具注册层设计契约（工具描述/Returns 段定死文案、roster_data
缺省自拉与非 success 透传；工具契约正本 = docs/develop/sr_od/backend/mys.md
「MCP 工具」节）。覆盖判据（注册成功、四态信封可达、双路径可达）。计算层行为由
``test/sr_od/backend/mcp/test_relic_eval_tools.py`` 锁定，本文件只锁注册层。

零副作用：控制器经 ``monkeypatch`` 注入桩（模块级 ``_controller`` 预设即被
``_get_controller`` 直接返回），不触网、不装配真实控制器。
"""

from unittest.mock import MagicMock

import pytest

from sr_od.backend.mcp import mys_tools
from sr_od.backend.mcp.mys_tools import register_mys_tools


class _RecordingMcp:
    """记录注册调用的假 mcp：按函数名捕获工具闭包与 annotations 参数。"""

    def __init__(self) -> None:
        self.registered: dict[str, callable] = {}
        self.tool_kwargs: dict[str, dict] = {}

    def tool(self, **kwargs) -> callable:
        def decorator(fn) -> callable:
            self.registered[fn.__name__] = fn
            self.tool_kwargs[fn.__name__] = kwargs
            return fn

        return decorator


class _StubController:
    """桩控制器：get_roster_detail 返回预设信封并计数调用。"""

    def __init__(self, envelope: dict) -> None:
        self.envelope = envelope
        self.calls = 0

    def get_roster_detail(self) -> dict:
        self.calls += 1
        return self.envelope


def _register_tool(monkeypatch: pytest.MonkeyPatch, stub: _StubController) -> callable:
    """注册工具并返回闭包（控制器桩预设进模块级单例槽位）。"""
    monkeypatch.setattr(mys_tools, '_controller', stub)
    fake = _RecordingMcp()
    register_mys_tools(fake, MagicMock(name='SrBackendContext'))
    return fake.registered['mys_evaluate_relic_substats']


def test_registered_name_annotations_and_description_contract() -> None:
    """注册成功 + 名称/只读标注/title/description 定死文案关键句
    （design §2.2 描述与 Returns 段逐字落地的可核查锚点）。"""
    fake = _RecordingMcp()
    register_mys_tools(fake, MagicMock(name='SrBackendContext'))

    assert 'mys_evaluate_relic_substats' in fake.registered
    annotations = fake.tool_kwargs['mys_evaluate_relic_substats']['annotations']
    assert annotations.readOnlyHint is True
    assert annotations.title == '评估遗器有效词条'

    doc = fake.registered['mys_evaluate_relic_substats'].__doc__ or ''
    assert doc.startswith('评估遗器副词条的命中情况')
    assert '本工具不内置任何默认口径' in doc
    assert '未传口径的角色不评估' in doc
    assert '共评估 N 名角色，M 名未命中名册' in doc
    assert 'session_expired' in doc and 'verification_required' in doc
    assert '``criteria`` 为空列表' in doc
    assert '角色明细' in doc


def test_roster_data_default_fetches_then_evaluates(monkeypatch: pytest.MonkeyPatch) -> None:
    """roster_data 缺省路径：经控制器自拉名册，success 载荷传入计算层。"""
    roster = [{
        'name': '卡芙卡', 'relics': [], 'ornaments': [],
    }]
    stub = _StubController({'status': 'success', 'message': 'ok', 'data': roster})
    fn = _register_tool(monkeypatch, stub)

    envelope = fn(criteria=[{'character_name': '卡芙卡', 'effective_substats': ['暴击率']}])

    assert stub.calls == 1
    assert envelope['status'] == 'success'
    assert envelope['data']['results']['卡芙卡']['total_rolls'] == 0


def test_non_success_envelope_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """自拉路径非 success 信封原样透传（session_expired 形态，同一信封对象）。"""
    expired = {'status': 'session_expired', 'message': '数据已过期', 'data': None}
    fn = _register_tool(monkeypatch, _StubController(expired))

    result = fn(criteria=[{'character_name': '卡芙卡', 'effective_substats': ['暴击率']}])
    assert result is expired  # 原样透传（同一信封对象）


def test_error_envelope_reachable_with_roster_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    """error 态经工具层可达：criteria 空列表 → 计算层 error 信封直返
    （roster_data 显式传入时不触控制器，error 判定先于评估）。"""
    fn = _register_tool(monkeypatch, _StubController(
        {'status': 'error', 'message': '不应被调用', 'data': None},
    ))

    result = fn(criteria=[], roster_data=[{'name': '卡芙卡', 'relics': [], 'ornaments': []}])

    assert result['status'] == 'error'
    assert 'criteria 为空列表' in result['message']


def test_explicit_roster_data_skips_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """roster_data 传入路径：不调控制器，直接对传入名册评估。"""
    stub = _StubController({'status': 'error', 'message': '不应被调用', 'data': None})
    fn = _register_tool(monkeypatch, stub)

    envelope = fn(
        criteria=[{'character_name': '黑天鹅', 'effective_substats': ['暴击']}],
        roster_data=[{'name': '黑天鹅', 'relics': [], 'ornaments': []}],
    )

    assert stub.calls == 0
    assert envelope['status'] == 'success'
    assert '黑天鹅' in envelope['data']['results']
