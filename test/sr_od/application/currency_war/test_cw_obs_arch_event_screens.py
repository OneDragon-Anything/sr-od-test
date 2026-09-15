"""统一观察架构·逐屏迁移首批锁(试点步骤 2:遭遇节点 + 盛会之星)。

设计正本 = docs/develop/sr_od/application/currency_war/flow/统一观察架构-画面op基类设计.md
(下称「架构设计」);迁移粒度依据 = 开放问题清单 B3(先迁 2 个代表屏:
遭遇 = 带刷新链最复杂、盛会之星 = 纯选卡最简 → 验证断言集模板 → 其余按族
批量);迁移手法单一源 = 试点步骤 1 先例(CwScreenPrep:装配点分流 + 五段
转录 + 实机适配器封口 + on_outcome 注册表)。

**F11/B3 sim 腿不适用例外清单(随迁移批逐屏落测试 docstring)**:

- 遭遇节点(CwScreenEncounter):sim 腿 = 不适用——T5 前 sim 引擎无遭遇
  决策段(架构设计 §7-T5/§11-R3,引擎内部采样不调 decide_encounter);
- 盛会之星(CwScreenMegastar):sim 腿 = 不适用——sim 无对应画面段
  (羁绊达标触发的 overlay,引擎即时落定,§3.2 事件浮层族行)。

两屏等价判据**主承重 = 实机在册行为锁 + 写入流对拍(实机腿)**(B3-F11:
无 sim 腿的屏禁引用 sim 域对拍)。

锁的语义(测试纪律 7 自检;出处 = 架构设计 §9.1/§6.4-R-E/B5 四件套;
生产端口恒 None 直连旧路径,五段新路径 = 测试驱动形态——迁移结构锁/
装配点分流锁已随并存窗收口整删,行为锁单驱动生产路径):

- **发射型接线锁**(§6.4-R-E 在册成员①):encounter_refresh_used 写端
  自 handle 内联位收编为 on_outcome 注册表发射型钩子,触发点唯一
  (_emit_refresh_click 两路径共用分派点,先例 = CwScreenPrep._act_execute);
  「随点击置位不等验效」语义逐字保绿(B5-④;发射计数/守卫旗标/刷后
  重读重决策三面并锁 = 遭遇刷新语义,单驱动生产路径)。
- **登记语义对拍锁**(B5-③/B2-④ 按语义逐条断言):写端值/evidence/
  produced_by/source 与现役内联位逐位一致。
- **chosen_* 豁免留守锁**(§2.2/§6.5-6:write_logic 豁免面不扩散):
  chosen_encounter 写端仍挂出口验真通过分支内联,不入注册表收编面。

驱动方式 = 真类实例(构造走 __init__,注册表在位)+ 读链/点击链桩化
(round_by_find_area/screenshot/reader 函数在模块命名空间桩化),装配点
分流桩端口 = ``_cw_helpers.install_dispatch_stub_ports`` 单一源。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    install_dispatch_stub_ports,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
    EncounterPick,
)
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_game_state import board_state_of
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)


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
    2026-09-10 动作 op 只管机械执行禁止验效——本桩回传重读候选,
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
    # 统一动作工厂批4:遭遇确认链体迁 pick op 模块——safe_click/
    # emit_overlay_confirm 桩随体迁移(替身跟随被迁体;桩语义不变:
    # 机械点击空操作、确认链回指定轮次结果)。
    import sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action as pick_mod
    monkeypatch.setattr(pick_mod, 'safe_click', lambda o, pt, **k: None)
    # (三审便宜化)encounter op 入口有画面稳定期 time.sleep(2.0s,
    # 真机等帧用)——mock 画面瞬时切换,等待纯属空睡;桩置空后单条
    # 2.8-5.6s → 亚秒(先例 = _make_strategy 桩 ism.time.sleep)。
    monkeypatch.setattr(em.time, 'sleep', lambda *_: None)
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResult,
        OperationRoundResultEnum,
    )
    _confirm_rs = OperationRoundResult(
        OperationRoundResultEnum.SUCCESS if confirm_success
        else OperationRoundResultEnum.RETRY, status='stub')
    monkeypatch.setattr(pick_mod, 'emit_overlay_confirm',
                        lambda o, **k: _confirm_rs)
    # (record_event_choice 替身桩已随删除波 1 移除——exogenous 写入端退役,
    #  encounter 模块不再引用 telemetry;(bs_view 桩同批移除——模块本体
    #  随波 5b 双删,桩对象不存在。))
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


# ==================== 迁移结构锁(§9.1 并存期)====================


# (原 test_migration_batch2_ops_inherit_base「遭遇 + 盛会之星均为
#  CwScreenOpBase 子类」与 test_encounter_dispatch_routes_to_lifecycle_
#  when_ports_installed「装端口 → 五段段迹」删:继承结构 = 静态形状、
#  装端口分流 = 测试驱动形态(生产端口恒 None),红时答不出哪个运行行为
#  坏了;结构/分流面归 review 与代码规范,行为锁单驱动生产路径。)


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


# (三审整删)原 test_event_screens_source_free_of_verify_segment
# 「验证段废除·源面锁」(getsource 断言两屏源无「六段」表述与 'verify'
# 字面)——源码扫描形态(README 禁止清单,红时是注释/字面变了,答不出
# 哪个运行行为坏了);验证段废除语义 = 装配点分流后无残迹可断,行为面归
# 既有双向行为锁(旧路径腿)承重。
# (收口整删)原 test_megastar_in_node_lifecycle_single_action_retry
# 「盛会之星五段在屏形态(迹到 act 为止)」删:装端口驱动的段迹面随并存
# 窗收口退役;在屏单动作语义由 test_megastar_dispatch_both_ways 旧路径
# 腿承重。


# (原 test_encounter_refresh_emission_wired_to_registry 删:注册表取证型
#  断言——登记件缺席时发射行为半必红,取证面零独立判别力,登记形状重构
#  = 误红源。同批判:phase strategy wired / step3 supply_no_outcome。)


def test_encounter_refresh_semantics(test_context, monkeypatch) -> None:
    """遭遇刷新语义(refresh 幸存三锁并一:发射计数/守卫旗标/刷后重读
    重决策;单驱动生产旧路径——发射点 ``_emit_refresh_click`` 与刷后重
    决策住共享分支链,生产形态承重):
    - 建议刷新 → 有次数未用 → 发射即置位(+1 带 refresh_click 证据),
      卡面未变帧(原「验效失败」形态)仍 +1;防重入旗标(执行侧载体)
      同步置位;验效双通道拆除后(用户裁定 2026-09-10 动作 op 禁验效):
      点钮+固定等待→无条件重读→带 refresh_used=True 自然重决策(恰两次
      决策);本访问交回不写 chosen(写时点 = 重入裁决,由
      test_encounter_old_path_kept_without_ports 承重);
    - 发射前置闸逐位:本局已用 / 无剩余次数 → 不发射不计数。
    (并锁依据 = 三锁断言面同住一条刷新分支链:原
    emission_counts_and_reread_redecide_new_path(装端口驱动,段迹面随
    并存窗收口退役)/ emission_counts_on_old_path_too / guarded_by_
    session_flag_and_count。红 = 发射断流 / 前置闸失守 / 重决策丢失。)"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    # ① 发射即置位 + 刷后重读重决策(重读 = 原卡面未变形态)
    op, match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, refresh=True, reason='stub'),
        refresh_opts=opts)
    _decide_calls: list[tuple[list, bool]] = []
    _orig_decide = match.strategy.decide_encounter

    def _counting(opts_, st, sess, cfg, refresh_used=False):
        _decide_calls.append((list(opts_), refresh_used))
        return _orig_decide(opts_, st, sess, cfg, refresh_used=refresh_used)

    match.strategy.decide_encounter = _counting
    _run_node(test_context, op, op.handle)
    bs = board_state_of(session)
    assert bs.encounter_refresh_used.value == 1, (
        f'卡面未变帧仍 +1(随点击置位不等验效,§6.5-4):'
        f'{bs.encounter_refresh_used.value}')
    assert bs.encounter_refresh_used.evidence == 'refresh_click', (
        f'发射证据逐位一致:{bs.encounter_refresh_used.evidence!r}')
    assert exec_state_of(session)._encounter_refresh_used is True, (
        '防重入旗标(执行侧载体)发射点同步置位')
    assert len(_decide_calls) == 2 and _decide_calls[1][1] is True, (
        f'刷后无条件重读+自然重决策(恰两次决策,重决策带 refresh_used=True):'
        f'{_decide_calls!r}')
    # ② 本局已用 → 不发射不计数
    op2, _m2, s2 = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, refresh=True, reason='stub'))
    exec_state_of(s2)._encounter_refresh_used = True
    _run_node(test_context, op2, op2.handle)
    assert board_state_of(s2).encounter_refresh_used.value is None, (
        '本局已用 → 不发射不计数')
    # ③ 无剩余次数 → 不发射不计数、不置防重入旗标
    op3, _m3, s3 = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=EncounterPick(idx=0, refresh=True, reason='stub'), cnt=None)
    _run_node(test_context, op3, op3.handle)
    assert board_state_of(s3).encounter_refresh_used.value is None, (
        '无次数 → 不发射不计数')
    assert exec_state_of(s3)._encounter_refresh_used is False, (
        '未发射不置防重入旗标')


def test_encounter_chosen_inline_not_registry_collected(
        test_context, monkeypatch) -> None:
    """chosen_encounter 确认门锁:确认未落地(验关失败)= 不写 chosen
    ——幻影 chosen(验关前落账)= 真实故障形态。
    (原「豁免留守/不入注册表收编面」半边已随批摘除,docstring 收窄到
    现断言面。)"""
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
    # (三审拆半:原尾部 getsource「chosen_* 不入注册表收编面」
    # 字面不在场断言删,豁免面纪律归 review 与代码规范。)
