"""接管链整体切换行为锁(接管域)。

锁面(设计依据 = §2.2/§2.3):

1. **位面 op 6 node 流程锁**:识别位面1 → 点开位面2 → 识别位面2 →
   点开位面3 → 识别位面3 → 上报 全链走通;三张位面卡各点一次 + 每位面
   点 boss 节点(动态定位);采集 op 零关闭动作(开/关转场归编排 op)。
   附属机制挂点随流程验:节点台账 plane_detail 源 + boss 位回填、敌人
   难度参考值逐位面落账(三识别 node 各读、上报节点落账)、词缀效果
   账本登记恰一次。识别域读法(节点条/类型名标签/SIFT/词缀/难度)桩化,
   画面门与点击/写门真跑(fixture 帧 + 真 screen_info area + 真容器)。
2. **识别失败响亮失败锁**:桩 SIFT 恒未命中 → 识别 node 重试耗尽 →
   op fail(状态含 SIFT 未命中);失败零写容器(无 None/占位/降级分支),
   点击有界(重试账收敛,看门狗零触发)。
3. **node1 入口门锁**:非位面详情屏 = fail + 存证截图,不进重试空转。
4. **entry 编排锁**:真值跳过门(容器已有位面真值 → 零点击直通成功,
   防手动调起白开白关详情屏)/ 画面不合法 fail + 存证 / 备战进详情 →
   委派 → 关闭全链(委派子 op 桩化,编排责任面单测)。
5. **prep 触发委派锁**:触发谓词 = 容器无位面真值;半开帧(节点条
   不可读)不委派、等下轮免费重判;委派结果透传(失败 = round_fail
   交外循环失败链,不自旋)。
6. **点开转移证据锁**:详情条联动判据(节点编号 OCR 位面段 = 目标位面;
   读不出 = 未联动)。

fixture 帧:screens/货币战争-位面详情/位面详情全屏.png(详情屏判定)、
screens/货币战争-备战/shop_closed_a8_start.webp(备战双锚语料帧)。
纹章风头像证据帧仅存档备查,不进测试面。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.kernel.cw_exec_state import (
    get_node_ledger,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)

_PREP_FRAME = ('货币战争-备战', 'shop_closed_a8_start')
_DETAIL_FRAME = ('货币战争-位面详情', '位面详情全屏')

_BOSS_NAMES = ['幻胧生物', '巨鹿制药', '镜泊集团']


# ==================== 桩面装配 ====================


def _fake_slots() -> list:
    """详情条槽桩:末位 node_type=None → 台账落账经位置先验回填 'boss'。"""
    return [SimpleNamespace(cx=100, cy=40, state='idle', node_type='battle'),
            SimpleNamespace(cx=300, cy=40, state='idle', node_type='reward'),
            SimpleNamespace(cx=500, cy=40, state='idle', node_type=None)]


def _stub_intel_reads(monkeypatch, *, sift_names: list[str | None],
                      affixes: list[str] | None = None) -> dict:
    """识别域读法桩化(模块属性级,monkeypatch 自动还原)。

    - read_plane_detail_nodes → 恒 3 槽(可定位 boss 圆心);
    - read_detail_node_type_label → 恒「首领节点」;
    - match_boss_sift → 按 sift_names 序列逐位面出参(None = 未命中);
    - read_plane_detail_difficulty → 逐次递增(验逐位面同帧顺带读);
    - read_detail_affixes → affixes。
    """
    from sr_od.application.currency_war.obs import cw_briefing_obs as cbo
    from sr_od.application.currency_war.obs import cw_node_reader
    from sr_od.application.currency_war.obs import cw_observation as cwo

    calls = {'difficulty': [], 'sift': []}
    monkeypatch.setattr(cwo, 'read_plane_detail_nodes',
                        lambda ctx, screen: _fake_slots())
    monkeypatch.setattr(cwo, 'read_detail_node_type_label',
                        lambda ctx, screen: '首领节点')
    monkeypatch.setattr(cwo, '_BOSS_TEMPLATES', {'stub模板': object()},
                        raising=False)
    monkeypatch.setattr(cwo, 'read_plane_detail_difficulty',
                        lambda ctx, screen: calls['difficulty'].append(1)
                        or (100 + 10 * len(calls['difficulty'])))

    def _sift(gray, templates):
        idx = len(calls['sift'])
        calls['sift'].append(1)
        if idx >= len(sift_names) or sift_names[idx] is None:
            return None
        return (sift_names[idx], 30)   # (boss 名, 好匹配数)

    monkeypatch.setattr(cw_node_reader, 'match_boss_sift', _sift)
    if affixes is not None:
        monkeypatch.setattr(cbo, 'read_detail_affixes',
                            lambda ctx, screen: list(affixes))
    return calls


def _install_session(test_context, monkeypatch) -> SimpleNamespace:
    """挂对局 session 桩(容器经 game_state_of 惰性建,读回断言)。"""
    sess = SimpleNamespace()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=sess), raising=False)
    return sess


def _fixture_controller(test_context, monkeypatch,
                        phases: list[dict]) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    ctrl.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    monkeypatch.setattr(ctrl, 'mouse_move', lambda pos: None, raising=False)
    return ctrl


def _rect_of(test_context, screen_name: str, area_name: str):
    area = test_context.screen_loader.get_area(screen_name, area_name)
    assert area is not None, f'建档缺失:{screen_name}/{area_name}'
    return area.pc_rect


def _in_rect(point, rect) -> bool:
    return rect.x1 <= point.x <= rect.x2 and rect.y1 <= point.y <= rect.y2


def _run_op(test_context, op) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


# ==================== 1. 位面 op 6 node 流程锁 ====================


def test_plane_intel_six_node_pipeline_flow(test_context, monkeypatch) -> None:
    """6 node 管线全链:三卡点选 + 每位面 boss 节点点击 + 上报写门 +
    附属机制三挂点(台账/难度/词缀登记)。红 = 管线结构或挂点接线断裂。"""
    if not test_context.has_screen(*_DETAIL_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_DETAIL_FRAME[0]}/{_DETAIL_FRAME[1]}.png')

    sess = _install_session(test_context, monkeypatch)
    calls = _stub_intel_reads(monkeypatch, sift_names=_BOSS_NAMES,
                              affixes=['灼热轰炸'])
    ctrl = _fixture_controller(test_context, monkeypatch, [{'frame': _DETAIL_FRAME}])

    from sr_od.application.currency_war.kernel import cw_affix_effects as afe
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import (
        CwScreenPlaneIntel,
    )

    class _WatchedIntel(WatchdogOperationMixin, CwScreenPlaneIntel):
        pass

    op = _WatchedIntel(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    # 转移证据按选卡序回 1/2/3(证据判据本体另测;fixture 帧只承载位面1)
    picked = {'n': 0}

    def _evidence(screen):
        picked['n'] += 1
        return min(picked['n'], 3)

    monkeypatch.setattr(op, '_plane_no_on_detail_bar', _evidence)
    register_calls: list = []
    monkeypatch.setattr(afe, 'register_affixes_from_names',
                        lambda sess_, names: register_calls.append((sess_, names))
                        or {'灼热轰炸': 'spec灼热轰炸'})

    res = _run_op(test_context, op)

    assert res.success, f'6 node 管线未走通:{res!r}'
    assert op._watchdog_round_count <= 12, (
        f'成功路径轮次应有界:{op._watchdog_round_count}')
    # 点选面:三张位面卡各点一次 + 三个 boss 节点(动态圆心落节点条内)
    card_rects = [_rect_of(test_context, '货币战争-位面详情', f'按钮-位面卡{i}')
                  for i in (1, 2, 3)]
    node_bar = _rect_of(test_context, '货币战争-位面详情', '区域-节点条')
    close_rect = _rect_of(test_context, '货币战争-位面详情', '按钮-关闭位面详情')
    for i, rect in enumerate(card_rects):
        assert sum(1 for p in ctrl.recorded_clicks if _in_rect(p, rect)) == 1, (
            f'位面卡{i} 应恰点一次:{ctrl.recorded_clicks}')
    assert sum(1 for p in ctrl.recorded_clicks if _in_rect(p, node_bar)) == 3, (
        f'三个 boss 节点应各点一次:{ctrl.recorded_clicks}')
    assert not any(_in_rect(p, close_rect) for p in ctrl.recorded_clicks), (
        '采集 op 零关闭动作(开关转场归编排 op)')
    # 附属机制③:难度参考值逐位面读(三识别 node 各一次)
    assert len(calls['difficulty']) == 3, (
        f'难度参考值应逐位面读 3 次:{calls["difficulty"]}')
    # 上报写门落容器(§2.3 定死写门经 3.1 端口锁;此处锁全链贯通)
    gs = game_state_of(sess)
    assert gs.plane_bosses.value == _BOSS_NAMES and gs.plane_bosses.source == 'logic'
    assert gs.enemy_affixes.value == ['灼热轰炸'] and gs.enemy_affixes.source == 'logic'
    # 附属机制②:台账 plane_detail 源 + boss 位回填
    ledger = get_node_ledger(sess)
    assert ledger.seq_by_plane == {1: ['battle', 'reward', 'boss'],
                                   2: ['battle', 'reward', 'boss'],
                                   3: ['battle', 'reward', 'boss']}
    assert set(ledger.seq_source.values()) == {'plane_detail'}
    # 附属机制③落账侧:逐位面落账
    assert ledger.difficulty_ref == {1: 110, 2: 120, 3: 130}
    # 附属机制④:词缀效果账本登记恰一次(接管局唯一活源)
    assert register_calls == [(sess, ['灼热轰炸'])]


def test_plane_intel_sift_miss_fails_loudly(test_context, monkeypatch) -> None:
    """识别失败响亮失败锁:SIFT 恒未命中 → 识别 node 重试耗尽 → op fail;
    失败零写容器(无 None/占位/降级),点击有界(重试账收敛)。"""
    if not test_context.has_screen(*_DETAIL_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_DETAIL_FRAME[0]}/{_DETAIL_FRAME[1]}.png')

    sess = _install_session(test_context, monkeypatch)
    _stub_intel_reads(monkeypatch, sift_names=[None], affixes=[])
    ctrl = _fixture_controller(test_context, monkeypatch, [{'frame': _DETAIL_FRAME}])

    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import (
        CwScreenPlaneIntel,
    )

    class _WatchedIntel(WatchdogOperationMixin, CwScreenPlaneIntel):
        pass

    op = _WatchedIntel(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    monkeypatch.setattr(op, '_plane_no_on_detail_bar', lambda screen: 1)

    res = _run_op(test_context, op)

    assert not res.success, f'SIFT 恒未命中应响亮失败:{res!r}'
    assert 'SIFT 未命中' in (res.status or ''), f'失败状态留证:{res!r}'
    gs = game_state_of(sess)
    assert gs.plane_bosses.value is None, '失败零写容器(响亮失败,不留半真值)'
    assert gs.enemy_affixes.value == [] \
        and gs.enemy_affixes.source == 'logic_rand', \
        '失败零写容器:词缀保持开局种子空表原样(不留半真值)'
    node_bar = _rect_of(test_context, '货币战争-位面详情', '区域-节点条')
    boss_clicks = [p for p in ctrl.recorded_clicks if _in_rect(p, node_bar)]
    assert 3 <= len(boss_clicks) <= 5, (
        f'重试账应收敛(首跑+3 重试邻域):{len(boss_clicks)}')
    assert op._watchdog_round_count <= 12, (
        f'看门狗零触发(节点预算先耗尽):{op._watchdog_round_count}')


def test_plane_intel_entry_gate_wrong_screen(test_context, monkeypatch) -> None:
    """node1 入口门:非位面详情屏 = fail + 存证截图(调用时机错误,
    不进重试空转)。红 = 门丢失或误入重试账。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import (
        CwScreenPlaneIntel,
    )

    op = CwScreenPlaneIntel(test_context)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: _Area(False))
    saved: list = []
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: saved.append(1) or '')

    rs = _run_node(test_context, op, op.recognize_plane_1)

    assert rs.result == OperationRoundResultEnum.FAIL, f'错屏应直接 fail:{rs!r}'
    assert '调用时机错误' in (rs.status or ''), f'状态指认错屏:{rs!r}'
    assert saved == [1], '错屏 fail 必存证截图'


def test_plane_intel_select_plane_evidence(test_context, monkeypatch) -> None:
    """点开转移证据判据:节点编号 OCR 位面段 = 目标位面 → 已选中;
    读不出 / 位面段不符 → 未联动。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import (
        CwScreenPlaneIntel,
    )

    op = CwScreenPlaneIntel(test_context)
    ocr_batches = iter([ [SimpleNamespace(data='2-3')],
                         [SimpleNamespace(data='1-9')],
                         [] ])
    monkeypatch.setattr(cw_obs_core, '_area_rect',
                        lambda ctx, name, screen_name=None: 'rect', raising=False)
    monkeypatch.setattr(cw_obs_core, '_ocr',
                        lambda ctx, screen, rect: next(ocr_batches), raising=False)

    assert op._plane_no_on_detail_bar('屏') == 2, '「2-3」→ 位面 2'
    assert op._plane_no_on_detail_bar('屏') == 1, '位面段不符 → 未联动'
    assert op._plane_no_on_detail_bar('屏') is None, '读不出 → 未联动'


# ==================== 4. entry 编排锁 ====================


def test_entry_truth_skip_gate_zero_click(test_context, monkeypatch) -> None:
    """真值跳过门:容器已有位面真值 → 零点击直通成功(防手动调起
    白开白关详情屏)。"""
    if not test_context.has_screen(*_PREP_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_PREP_FRAME[0]}/{_PREP_FRAME[1]}.webp')

    sess = _install_session(test_context, monkeypatch)
    cw4_gs(sess, plane_bosses=['简报boss', None, None])
    ctrl = _fixture_controller(test_context, monkeypatch, [{'frame': _PREP_FRAME}])

    from sr_od.application.currency_war.operations.cw_entry.cw_entry_plane_intel import (
        CwEntryPlaneIntel,
    )

    op = CwEntryPlaneIntel(test_context)
    res = _run_op(test_context, op)

    assert res.success and res.status == CwEntryPlaneIntel.STATUS_SKIP, (
        f'真值已在应直通跳过:{res!r}')
    assert ctrl.recorded_clicks == [], f'跳过门零点击:{ctrl.recorded_clicks}'


def test_entry_gate_wrong_screen_fails(test_context, monkeypatch) -> None:
    """画面门:非对局画面(备战/位面详情都不在)= fail + 存证,零点击。"""
    sess = _install_session(test_context, monkeypatch)
    cw4_gs(sess)   # 无位面真值(门序:画面门先于真值跳过门)

    from sr_od.application.currency_war.operations.cw_entry.cw_entry_plane_intel import (
        CwEntryPlaneIntel,
    )

    op = CwEntryPlaneIntel(test_context)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: _Area(False))
    saved: list = []
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: saved.append(1) or '')

    rs = _run_node(test_context, op, op.gate)

    assert rs.result == OperationRoundResultEnum.FAIL and '不在货币战争对局画面' in (rs.status or ''), (
        f'错屏应 fail:{rs!r}')
    assert saved == [1], '错屏 fail 必存证截图'


def test_entry_full_orchestration_open_delegate_close(
        test_context, monkeypatch) -> None:
    """编排全链:备战点节点图标开详情 → 委派子 op → 点 X 关详情回备战;
    委派结果透传。红 = 编排断流 / 关闭转移证据丢失。"""
    if not test_context.has_screen(*_PREP_FRAME) or not test_context.has_screen(*_DETAIL_FRAME):
        pytest.skip('存档截图缺失:备战或位面详情 fixture 帧')

    sess = _install_session(test_context, monkeypatch)
    cw4_gs(sess)   # 无位面真值 → 全链委派
    ctrl = _fixture_controller(test_context, monkeypatch, [
        {   # 备战:点节点图标(落备战节点条)→ 详情开
            'frame': _PREP_FRAME,
            'exit': ('on_click_in', '货币战争-备战', '区域-节点条'),
        },
        {   # 详情:委派(桩)→ 点关闭钮 → 回备战
            'frame': _DETAIL_FRAME,
            'exit': ('on_click_in', '货币战争-位面详情', '按钮-关闭位面详情'),
        },
        {'frame': _PREP_FRAME},   # terminal:关闭完成门(标题消失)
    ])
    # 备战节点图标定位桩(识别域;点击落点 = 节点条原点 + 槽偏移,仍在条内)
    from sr_od.application.currency_war.obs import cw_observation as cwo
    monkeypatch.setattr(cwo, 'read_node_sequence',
                        lambda ctx, screen: [SimpleNamespace(
                            cx=40, cy=30, state='current')])
    # 委派子 op 桩(编排责任面单测;子 op 管线已单独锁)
    sub_runs: list = []

    class _FakeSub:
        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            sub_runs.append(1)
            return SimpleNamespace(success=True, status='子op成功', data=None)

    import sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel as pim
    monkeypatch.setattr(pim, 'CwScreenPlaneIntel', _FakeSub)

    from sr_od.application.currency_war.operations.cw_entry.cw_entry_plane_intel import (
        CwEntryPlaneIntel,
    )

    op = CwEntryPlaneIntel(test_context)
    res = _run_op(test_context, op)

    assert res.success and sub_runs == [1], (
        f'编排未贯通(open→委派→close):{res!r} runs={sub_runs}')
    prep_bar = _rect_of(test_context, '货币战争-备战', '区域-节点条')
    close_rect = _rect_of(test_context, '货币战争-位面详情', '按钮-关闭位面详情')
    assert any(_in_rect(p, prep_bar) for p in ctrl.recorded_clicks), (
        f'开详情应点备战节点图标:{ctrl.recorded_clicks}')
    assert any(_in_rect(p, close_rect) for p in ctrl.recorded_clicks), (
        f'关闭应点关闭钮:{ctrl.recorded_clicks}')
    assert ctrl.phase_idx == 2, (
        f'关闭后应回备战帧(转移证据):phase_idx={ctrl.phase_idx}')


# ==================== 5. prep 触发委派锁 ====================


def _make_prep(test_context, monkeypatch, sess, *, node_bar_readable: bool):
    """CwScreenPrep 构造 + 触发判据输入桩(节点条读法桩化)。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(cw_screen_prep, 'read_node_sequence',
                        lambda ctx, screen: (
                            [SimpleNamespace(state='current')]
                            if node_bar_readable else None))
    return CwScreenPrep(test_context)


def test_prep_delegate_trigger_predicate(test_context, monkeypatch) -> None:
    """prep 触发谓词:容器无位面真值 + 节点条可读 → 委派;已有真值或
    半开帧 → 不委派(None,交回主链)。"""
    sess = _install_session(test_context, monkeypatch)
    cw4_gs(sess)   # 无位面真值
    op = _make_prep(test_context, monkeypatch, sess, node_bar_readable=True)

    entry_runs: list = []

    class _FakeEntry:
        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            entry_runs.append(1)
            return SimpleNamespace(success=True, status='委派成功', data=None)

    from sr_od.application.currency_war.operations.cw_entry import (
        cw_entry_plane_intel as eim,
    )
    monkeypatch.setattr(eim, 'CwEntryPlaneIntel', _FakeEntry)

    rs = op._delegate_plane_intel_if_needed(sess)

    assert rs is not None and rs.is_success and entry_runs == [1], (
        f'无真值 + 可读帧应委派:{rs!r} runs={entry_runs}')
    # 已有真值 → 不委派
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
    )
    gs = game_state_of(sess)
    gs.write_logic(gs.plane_bosses, ['简报boss', None, None],
                   produced_by='TestSigWriter',
                   sig=ChannelSig(family='logic_action',
                                  actor='TestSigWriter', mode='compute'))
    entry_runs.clear()
    rs2 = op._delegate_plane_intel_if_needed(sess)
    assert rs2 is None and entry_runs == [], '已有真值不应委派'


def test_prep_delegate_skips_on_unreadable_frame(test_context, monkeypatch) -> None:
    """半开帧守卫:节点条不可读 → 不委派(None,等下轮免费重判,不烧失败链)。"""
    sess = _install_session(test_context, monkeypatch)
    cw4_gs(sess)
    op = _make_prep(test_context, monkeypatch, sess, node_bar_readable=False)

    rs = op._delegate_plane_intel_if_needed(sess)
    assert rs is None, f'半开帧不应委派:{rs!r}'


def test_prep_delegate_propagates_failure(test_context, monkeypatch) -> None:
    """委派结果透传:子 op 失败 → prep round_fail(交外循环失败链,不自旋)。"""
    sess = _install_session(test_context, monkeypatch)
    cw4_gs(sess)
    op = _make_prep(test_context, monkeypatch, sess, node_bar_readable=True)

    class _FakeEntry:
        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            return SimpleNamespace(success=False, status='实采失败', data=None)

    from sr_od.application.currency_war.operations.cw_entry import (
        cw_entry_plane_intel as eim,
    )
    monkeypatch.setattr(eim, 'CwEntryPlaneIntel', _FakeEntry)

    rs = op._delegate_plane_intel_if_needed(sess)
    assert rs is not None and rs.result == OperationRoundResultEnum.FAIL, (
        f'失败应透传为 round_fail:{rs!r}')
