"""统一观察架构·逐屏迁移首批锁(试点步骤 2:遭遇节点 + 盛会之星)。

设计正本 = docs/develop/currency_war/design/统一观察架构-画面op基类设计.md
(下称「架构设计」);迁移粒度依据 = 开放问题清单 B3(先迁 2 个代表屏:
遭遇 = 带刷新链最复杂、盛会之星 = 纯选卡最简 → 验证断言集模板 → 其余按族
批量);迁移手法单一源 = 试点步骤 1 先例(CwScreenPrep:装配点分流 + 五段
转录 + 实机适配器封口 + on_outcome 注册表,验收 reviews/T-189-r1.md)。

**F11/B3 sim 腿不适用例外清单(随迁移批逐屏落测试 docstring)**:

- 遭遇节点(CwScreenEncounter):sim 腿 = 不适用——T5 前 sim 引擎无遭遇
  决策段(架构设计 §7-T5/§11-R3,引擎内部采样不调 decide_encounter);
- 盛会之星(CwScreenMegastar):sim 腿 = 不适用——sim 无对应画面段
  (羁绊达标触发的 overlay,引擎即时落定,§3.2 事件浮层族行)。

两屏等价判据**主承重 = 实机在册行为锁 + 写入流对拍(实机腿)**(B3-F11:
无 sim 腿的屏禁引用 sim 域对拍)。

锁的语义(测试纪律 7 自检;出处 = 架构设计 §9.1/§6.4-R-E/B5 四件套):

- **迁移结构锁**:两 op 是 CwScreenOpBase 子类 ∧ handle 顶部装配点分流
  (两端口完整在场 → run_lifecycle;缺省 None = 生产直连旧路径,§9.1
  并存期)。红 = 迁移断线(结构退回)或分流判据破坏(生产误走新路径)。
- **发射型接线锁**(§6.4-R-E 在册成员①):encounter_refresh_used 写端
  自 handle 内联位收编为 on_outcome 注册表发射型钩子,触发点唯一
  (_emit_refresh_click 两路径共用分派点,先例 = CwScreenPrep._act_execute);
  「随点击置位不等验效」语义逐字保绿(B5-④:验效失败帧仍 +1)。
- **登记语义对拍锁**(B5-③/B2-④ 按语义逐条断言):写端值/evidence/
  produced_by/source 与现役内联位逐位一致。
- **chosen_* 豁免留守锁**(§2.2/§6.5-6:write_logic 豁免面不扩散):
  chosen_encounter 写端仍挂出口验真通过分支内联,不入注册表收编面。

驱动方式 = 真类实例(构造走 __init__,注册表在位)+ 读链/点击链桩化
(round_by_find_area/screenshot/reader 函数在模块命名空间桩化),装配点
分流桩端口 = ``_cw_helpers.install_dispatch_stub_ports`` 单一源。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_board_state import board_state_of
from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
    EncounterPick,
)
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
from sr_od.application.currency_war.operations.cw_screen.cw_screen_op_base import (
    OUTCOME_TRIGGER_EMITTED,
    CwScreenOpBase,
)
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.app.currency_war._cw_helpers import install_dispatch_stub_ports

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)


class _Area:
    """round_by_find_area 桩回执(程序化回 in_screen/in_node)。"""

    def __init__(self, ok: bool) -> None:
        self.is_success = ok


def _make_session() -> StrategySession:
    return StrategySession()


def _make_encounter(test_context, monkeypatch, *, in_screen: bool,
                    options: list[EncounterOption],
                    pick: EncounterPick,
                    cnt: tuple | None = (1, (771, 899)),
                    confirm_success: bool = True,
                    refresh_opts: list[EncounterOption] | None = None):
    """遭遇屏真类装配(生产构造走 __init__ = on_outcome 注册表在位)。

    桩面 = 画面门/截屏/读链/策略器/确认链/遥测;``_try_refresh`` 方法级桩
    (刷新机械执行面:点钮+固定等待+重读;验效双通道已拆除——用户裁定
    2026-09-10 动作 op 只管机械执行禁止验效,出处 = 清查报告
    .debug/temp/currency_war/验证违规清查-报告.md H1——本桩回传重读候选,
    空表 = 读缺失败安全形态)。返回 (op, match, session)。
    """
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter as em,
    )

    session = _make_session()
    strategy = SimpleNamespace(decide_encounter=lambda opts, st, sess, cfg,
                               refresh_used=False: pick)
    match = SimpleNamespace(strategy=strategy, session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = em.CwScreenEncounter(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_screen))
    monkeypatch.setattr(op, 'screenshot', lambda: _FRAME)
    monkeypatch.setattr(op, '_try_refresh',
                        lambda text_pt: list(refresh_opts or []))
    monkeypatch.setattr(em, 'read_encounter_options',
                        lambda ctx, scr: list(options))
    monkeypatch.setattr(em, 'read_encounter_refresh_count',
                        lambda ctx, scr: cnt)
    monkeypatch.setattr(em, 'safe_click', lambda o, pt, **k: None)
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResult,
        OperationRoundResultEnum,
    )
    _confirm_rs = OperationRoundResult(
        OperationRoundResultEnum.SUCCESS if confirm_success
        else OperationRoundResultEnum.RETRY, status='stub')
    monkeypatch.setattr(em, 'emit_overlay_confirm',
                        lambda o, **k: _confirm_rs)
    monkeypatch.setattr(em, 'record_event_choice', lambda *a, **k: None)
    import sr_od.application.currency_war.kernel.cw_bs_view as bs_view_mod
    from sr_od.application.currency_war.kernel.cw_state import GameState
    monkeypatch.setattr(bs_view_mod, 'strategy_input_state',
                        lambda sess: GameState())
    return op, match, session


def _make_megastar(test_context, monkeypatch, *, in_node: bool):
    """盛会之星真类装配(同上;动作体 _do_action 调用计数挂 returned)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_megastar as ms,
    )

    session = _make_session()
    match = SimpleNamespace(
        session=session,
        exec_state=SimpleNamespace(megastar_candidate_clicked=False))
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_node))
    calls: list[int] = []
    monkeypatch.setattr(op, '_do_action', lambda scr: calls.append(1))
    return op, match, session, calls


def _run_node(test_context, op, fn) -> object:
    """节点函数运行外壳(fast_sleep + running_state;返回轮次结果)。"""
    with fast_sleep():
        enter_running_state(test_context)
        try:
            return fn()
        finally:
            reset_running_state(test_context, op)


# ==================== 迁移结构锁(§9.1 并存期)====================


def test_migration_batch2_ops_inherit_base() -> None:
    """逐屏迁移首批(试点步骤 2):遭遇 + 盛会之星均为 CwScreenOpBase
    子类(B3 两代表屏)。红 = 迁移回退或漏迁。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter,
        cw_screen_megastar,
    )
    assert issubclass(cw_screen_encounter.CwScreenEncounter, CwScreenOpBase)
    assert issubclass(cw_screen_megastar.CwScreenMegastar, CwScreenOpBase)


def test_encounter_dispatch_routes_to_lifecycle_when_ports_installed(
        test_context, monkeypatch) -> None:
    """遭遇屏装配点分流:两端口完整在场 → handle 经五段新路径(段迹
    observe 起、on_outcome 收,无验证段——用户裁定 2026-09-10 验证段
    废除);红 = 分流判据缺失(装端口仍走旧路径=迁移无效)或验证段
    残迹回潮。"""
    install_dispatch_stub_ports(monkeypatch)
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, reason='stub'))
    _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act',
                                   'on_outcome'], (
        f'装端口须走五段新路径(恰五段,验证段已废除):{op._lifecycle_trace}')


def test_encounter_old_path_kept_without_ports(
        test_context, monkeypatch) -> None:
    """缺省 None = 生产直连旧路径(§9.1):不装端口 → 旧序列原样
    (零段迹);行为锁面(L1-11 联动改写,验证废除批)= 确认发出置
    pending、chosen 写时机归重入裁决(单调用内不写——时点后移语义,
    新旧路径同承)。
    红 = 分流判据破坏(生产误走新路径)。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, _match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, reason='stub'))
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == [], f'旧路径不得写段迹:{op._lifecycle_trace}'
    assert rs.is_success, f'旧路径确认链轮次结果照回(保形):{rs!r}'
    assert op._confirm_pending is not None, (
        '确认已发 → pending 置位(chosen 归重入裁决承载)')
    assert board_state_of(session).chosen_encounter.value is None, (
        'chosen 单调用内不写(写时机 = 重入裁决,时点后移)')


def test_encounter_observe_gate_fails_off_screen(
        test_context, monkeypatch) -> None:
    """段1 观察门:非遭遇屏 → round_fail 早退(旧 handle 首闸逐位转录)。"""
    install_dispatch_stub_ports(monkeypatch)
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=False, options=[],
        pick=EncounterPick(idx=0, reason='stub'))
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace[0] == 'observe'
    assert not rs.is_success and '非遭遇节点屏' in (rs.status or ''), (
        f'观察门早退语义不变:{rs!r}')


def test_megastar_dispatch_both_ways(test_context, monkeypatch) -> None:
    """盛会之星装配点分流双向:装端口 → 五段(离屏 = observe 段早退
    成功交还,带完成 settle 语义);不装端口 → 旧路径零段迹。"""
    # 装端口 + 离屏:observe 段早退 = 节点完成(旧 handle 首闸语义)
    install_dispatch_stub_ports(monkeypatch)
    op, match, _session, calls = _make_megastar(
        test_context, monkeypatch, in_node=False)
    match.exec_state.megastar_candidate_clicked = True
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == ['observe'], (
        f'装端口须走五段新路径;离屏早退 = 后续段不执行(仅 observe 段迹):'
        f'{op._lifecycle_trace}')
    assert calls == [], '离屏早退 = 不发动作'
    assert '巨星节点完成' in (rs.status or ''), f'完成语义不变:{rs!r}'
    assert match.exec_state.megastar_candidate_clicked is False, (
        '选中标记复位副作用随 _in_node 复检保留(跨节点不保持)')
    # 不装端口:旧路径零段迹 + 仍在屏内 = 一个动作 + retry
    from sr_od.application.currency_war import cw_game_ports as _ports_mod
    monkeypatch.setattr(_ports_mod, '_INSTALLED', (None, None))   # 卸载复位
    op2, _match2, _s2, calls2 = _make_megastar(
        test_context, monkeypatch, in_node=True)
    rs2 = _run_node(test_context, op2, op2.handle)
    assert op2._lifecycle_trace == [], f'旧路径不得写段迹:{op2._lifecycle_trace}'
    assert calls2 == [1] and not rs2.is_success, (
        '旧路径在屏内 = 一个动作 + retry(保形)')


def test_megastar_in_node_lifecycle_single_action_retry(
        test_context, monkeypatch) -> None:
    """盛会之星五段在屏形态:decide+act 内聚于 _do_action 单动作
    (committed-but-verifying;节点完成判定 = 下一轮 observe 门,非生命
    周期验证段——用户裁定 2026-09-10 验证段废除,迹到 act 为止)。"""
    install_dispatch_stub_ports(monkeypatch)
    op, _match, _session, calls = _make_megastar(
        test_context, monkeypatch, in_node=True)
    _run_node(test_context, op, op.handle)
    assert calls == [1], f'每轮恰一个动作:{calls!r}'
    assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act'], (
        f'盛会之星段迹 = observe/reconcile/decide/act(节点完成判定归下一轮'
        f' observe 门,无验证段):{op._lifecycle_trace}')


def test_event_screens_source_free_of_verify_segment() -> None:
    """验证段废除·源面锁(用户裁定 2026-09-10:动作 op 只管机械执行,
    禁止在画面 op 做验证):两屏源无「六段」表述、无 'verify' 段迹字面;
    落地判定归动作适配器回执(§6.2),非生命周期段。红 = 验证段残面
    回潮。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter as em,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_megastar as ms,
    )
    for name, mod in (('encounter', em), ('megastar', ms)):
        src = inspect.getsource(mod)
        assert '六段' not in src, f'{name} 源面残留「六段」表述(验证段已废除)'
        assert "'verify'" not in src, f'{name} 源面残留 verify 段迹字面(验证段已废除)'


# ==================== 发射型接线锁(§6.4-R-E 在册①;B5 四件套)====================


def test_encounter_refresh_emission_wired_to_registry(test_context,
                                                      monkeypatch) -> None:
    """发射型接线形态(B5-② 登记调用点形态,断言面限定接线点):
    ①注册表在 __init__ 按 EncounterPick 登记发射型钩子
    (name=encounter_refresh_used,已入申报面);②fire_emit_hooks 全模块
    恰一处(= _emit_refresh_click 两路径共用分派点,触发唯一性);③写端
    (write_logic encounter_refresh_used)住钩子体内联位零残留。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter as em,
    )
    src = inspect.getsource(em)
    assert src.count('fire_emit_hooks') == 1, (
        '发射触发点须唯一(_emit_refresh_click 分派面)')
    assert '_emit_refresh_click' in src and 'encounter_refresh_used' in src
    hook_src = inspect.getsource(em.CwScreenEncounter._on_refresh_emitted)
    assert 'write_logic' in hook_src and "evidence='refresh_click'" in hook_src, (
        '登记件写端须住发射型钩子体(B5-②:内联登记调用点零残留)')
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, reason='stub'))
    specs = op._outcome_hooks.get(type(EncounterPick(idx=0)), [])
    assert any(s.name == 'encounter_refresh_used'
               and s.trigger == OUTCOME_TRIGGER_EMITTED for s in specs), (
        f'发射型登记件须在 __init__ 入注册表:{specs!r}')


def test_encounter_refresh_emission_counts_and_reread_redecide_new_path(
        test_context, monkeypatch) -> None:
    """B5-④ 发射型断言(新路径):建议刷新 → 有次数未用 → 发射即置位
    (+1 带 refresh_click 证据),卡面未变帧(原「验效失败」形态)仍 +1;
    落地回执点不重复计数(发射型不混触落地门,§6.4);防重入旗标(执行
    侧载体)同步置位。验效双通道拆除后(用户裁定 2026-09-10 动作 op 禁
    验效,清查报告 H1):点钮+固定等待→无条件重读→带 refresh_used=True
    自然重决策(恰两次决策;不要求与原 pick 等价)。"""
    install_dispatch_stub_ports(monkeypatch)
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, refresh=True, reason='stub'),
        refresh_opts=opts)   # 重读=原卡面(未变形态)
    _decide_calls: list[tuple[list, bool]] = []
    _orig_decide = match.strategy.decide_encounter

    def _counting(opts_, st, sess, cfg, refresh_used=False):
        _decide_calls.append((list(opts_), refresh_used))
        return _orig_decide(opts_, st, sess, cfg, refresh_used=refresh_used)

    match.strategy.decide_encounter = _counting
    _run_node(test_context, op, op.handle)
    bs = board_state_of(session)
    assert bs.encounter_refresh_used.value == 1, (
        f'卡面未变帧仍 +1(随点击置位不等验效,§6.5-4):{bs.encounter_refresh_used.value}')
    assert bs.encounter_refresh_used.evidence == 'refresh_click', (
        f'发射证据逐位一致:{bs.encounter_refresh_used.evidence!r}')
    assert exec_state_of(session)._encounter_refresh_used is True, (
        '防重入旗标(执行侧载体)发射点同步置位')
    assert len(_decide_calls) == 2 and _decide_calls[1][1] is True, (
        f'刷后无条件重读+自然重决策(恰两次决策,重决策带 refresh_used=True):'
        f'{_decide_calls!r}')
    assert bs.chosen_encounter.value == (1, '金币×2'), (
        '刷后重决策照常选卡,出口验真通过 → chosen 照写')


def test_encounter_refresh_emission_counts_on_old_path_too(
        test_context, monkeypatch) -> None:
    """位置迁移语义不变(旧路径同享注册表,先例 = CwScreenPrep 经
    _act_execute 同享经验账本):不装端口(生产形态)走旧路径,发射点
    (_emit_refresh_click 共用)照触发注册表 → +1。红 = 旧路径登记断流
    (生产计数丢失)。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, _match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, refresh=True, reason='stub'),
        refresh_opts=[])
    _run_node(test_context, op, op.handle)
    bs = board_state_of(session)
    assert bs.encounter_refresh_used.value == 1, (
        f'生产旧路径发射点照触发注册表:{bs.encounter_refresh_used.value}')
    assert bs.encounter_refresh_used.evidence == 'refresh_click'


def test_encounter_refresh_guarded_by_session_flag_and_count(
        test_context, monkeypatch) -> None:
    """发射前置闸逐位保留:本局已用 / 无剩余次数 → 不发射(计数不动,
    失败安全按原评分选);dd-004 单次尝试语义与执行侧旗标同点。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    # ①本局已用
    op, match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, refresh=True, reason='stub'))
    exec_state_of(session)._encounter_refresh_used = True
    _run_node(test_context, op, op.handle)
    assert board_state_of(session).encounter_refresh_used.value is None, (
        '本局已用 → 不发射不计数')
    # ②无剩余次数
    op2, _m2, s2 = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, refresh=True, reason='stub'), cnt=None)
    _run_node(test_context, op2, op2.handle)
    assert board_state_of(s2).encounter_refresh_used.value is None, (
        '无次数 → 不发射不计数')
    assert exec_state_of(s2)._encounter_refresh_used is False, (
        '未发射不置防重入旗标')


def test_encounter_chosen_inline_not_registry_collected(
        test_context, monkeypatch) -> None:
    """chosen_* 豁免留守锁(§2.2/§6.5-6):chosen_encounter 写端仍挂
    出口验真通过分支内联(不入 on_outcome 注册表收编面);确认未落地
    (验关失败)= 不写。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
            EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])]
    # 新路径 + 确认失败 → chosen 不写
    install_dispatch_stub_ports(monkeypatch)
    op, _match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=1, reason='stub'), confirm_success=False)
    rs = _run_node(test_context, op, op.handle)
    assert not rs.is_success and board_state_of(
        session).chosen_encounter.value is None, '验关失败 → chosen 不写'
    # 源形态:chosen 写端在 _record_chosen(出口验真通过分支调用),
    # 不在发射型钩子体
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter as em,
    )
    hook_src = inspect.getsource(em.CwScreenEncounter._on_refresh_emitted)
    assert 'chosen_encounter' not in hook_src, (
        'chosen_* 不入注册表收编面(豁免面不扩散)')
