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
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickEncounterParam,
    CwActionRefreshNodeOptionsParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    StrategyState,
)

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)


def _make_session() -> StrategySession:
    return StrategySession()


def _make_encounter(test_context, monkeypatch, *, in_screen: bool,
                    options: list[EncounterOption],
                    pick: object,
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
    strategy = SimpleNamespace(decide_encounter=lambda: pick)
    match = SimpleNamespace(strategy=strategy, session=session)
    # 终态契约 §B(T-4):match 桩挂载容器(gs 持有引用直用)。
    from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
    match.gs = game_state_of(session)
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
    #  encounter 模块不再引用 telemetry;(gs_view 桩同批移除——模块本体
    #  随波 5b 双删,桩对象不存在。))
    return op, match, session


def _make_megastar(test_context, monkeypatch, *, in_node: bool,
                   options: list | None = None):
    """盛会之星真类装配(两 node 形态,迭代 2026-09-18-screen-op-flat-report):
    门桩 + 候选读链桩(观察 node 读屏函数注入点)+ 动作体调用计数。
    旗标宿主 = 策略器 StrategyState(经 session.strategy_state 通道)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_megastar as ms,
    )

    session = _make_session()
    match = SimpleNamespace(session=session)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_node))
    monkeypatch.setattr(ms, 'read_megastar_options',
                        lambda ctx, scr: list(options or []))
    calls: list[int] = []
    monkeypatch.setattr(op, '_do_action', lambda: calls.append(1))
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
        pick=CwActionPickEncounterParam(idx=0, reason='stub'))
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == [], f'旧路径不得写段迹:{op._lifecycle_trace}'
    assert rs.is_success, f'旧路径确认链轮次结果照回(保形):{rs!r}'
    assert op._confirm_pending is not None, (
        '确认已发 → pending 置位(chosen 归重入裁决承载)')
    assert game_state_of(session).chosen_encounter.value is None, (
        'chosen 单调用内不写(写时机 = 重入裁决,时点后移)')


def test_encounter_observe_gate_fails_off_screen(
        test_context, monkeypatch) -> None:
    """段1 观察门:非遭遇屏 → round_fail 早退(旧 handle 首闸逐位转录)。"""
    install_dispatch_stub_ports(monkeypatch)
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=False, options=[],
        pick=CwActionPickEncounterParam(idx=0, reason='stub'))
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace[0] == 'observe'
    assert not rs.is_success and '非遭遇节点屏' in (rs.status or ''), (
        f'观察门早退语义不变:{rs!r}')


def test_megastar_observe_gate_completes_off_overlay(
        test_context, monkeypatch) -> None:
    """盛会之星观察 node 完成门(两 node 形态):门 miss = overlay 消失 /
    进了下一节点 → 节点完成,success 交还外层(完成 settle 承诺不变);
    选中标记复位副作用随 ``_in_node`` 复检保留(跨节点不保持);门早退
    不读候选不动作不写容器。红 = 完成门失效 / 复位丢失 / 早退后仍发动作。"""
    op, _match, session, calls = _make_megastar(
        test_context, monkeypatch, in_node=False, options=['哨兵'])
    session.strategy_state = StrategyState()
    session.strategy_state.megastar_clicked = True   # 预置跨节点残留态
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success and '巨星节点完成' in (rs.status or ''), (
        f'完成语义不变:{rs!r}')
    assert session.strategy_state.megastar_clicked is False, (
        '选中标记复位副作用随 _in_node 复检保留(跨节点不保持;'
        '宿主 = 策略器 StrategyState)')
    assert calls == [], '离屏早退 = 不发动作'
    assert game_state_of(session).megastar_opts.value is None, (
        '门早退不进读链,容器零写')


def test_megastar_observe_reports_and_act_acts(
        test_context, monkeypatch) -> None:
    """盛会之星在屏形态(两 node 形态):观察 node 读候选一次 → report 落
    容器 ``megastar_opts``(容器终值)+ obs 挂实例属性 → 决策动作 node 恰
    一个动作 + round_wait 推进循环(不计节点重试预算)。红 = report 断流 /
    容器终值漂移 / 动作丢失 / 循环推进回退为计预算的 retry。"""
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    op, _match, session, calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花火')])
    session.strategy_state = StrategyState()   # 未选中 → 本访问将选择(读候选)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success and game_state_of(session).megastar_opts.value == [
        MegastarOption(idx=0, char_id='花火')], (
        f'观察上报落容器(容器终值):{game_state_of(session).megastar_opts.value!r}')
    assert op._obs is not None and len(op._obs.options) == 1, (
        'obs 挂实例属性(跨 node 传递)')
    rs2 = _run_node(test_context, op, op.act)
    assert calls == [1], f'决策动作 node 恰一个动作:{calls!r}'
    assert rs2.result == OperationRoundResultEnum.WAIT, (
        f'循环推进 = round_wait(不计节点重试预算):{rs2!r}')


def test_megastar_lazy_read_skipped_on_confirm_visit(
        test_context, monkeypatch) -> None:
    """巨星懒读保真(读时机保真,迁移不增加读屏):已选中(确认访问)→
    观察 node **不读候选**(读链桩零调用)→ report 空候选不写(容器保持
    前值);决策动作 node 照发确认(动作体被消费)。红 = 确认访问重读候选
    (新增读屏)/ 容器被空值覆写。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    op, _match, session, calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花火')])
    session.strategy_state = StrategyState()
    session.strategy_state.megastar_clicked = True   # 已选中 = 确认访问
    _read_calls: list[int] = []
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar as ms
    monkeypatch.setattr(
        ms, 'read_megastar_options',
        lambda ctx, scr: _read_calls.append(1) or [])
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success and _read_calls == [], (
        f'确认访问不重读候选(懒读保真):{_read_calls!r}')
    assert game_state_of(session).megastar_opts.value is None, (
        '空候选不写(闸在 report 内),容器保持前值')
    rs2 = _run_node(test_context, op, op.act)
    assert calls == [1] and not rs2.is_success, '确认访问照发确认动作'


def test_megastar_redispatch_no_reclick_and_gate_reset(
        test_context, monkeypatch) -> None:
    """巨星防重入行为锁(旗标宿主 = 策略器 StrategyState,执行层经 kernel
    ``strategy_state_of`` None-safe 通道读写):
    - 同节点二次派发(re-dispatch 重入,门未 miss)→ 已点标记在位,不再
      点候选(防 re-click toggle 反选 → 确认无候选卡死);
    - 门 miss(离开巨星 overlay)→ 节点完成即复位,标记不跨节点保持
      (巨星一局可多次触发);
    - 状态对象缺席(裸 session,第三方策略面)→ 读退 False、写跳过,
      执行层不冷建策略器状态(禁 impl ``state_of`` 装配语义);
    - chosen_megastar = 选择点留守写端(动作事实边界,不进 report),
      首派发选中时点落容器。
    红 = 重入重点候选 / 门 miss 不复位 / 缺席态炸错或冷建 / chosen 断流。"""
    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as reg_mod
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_megastar as ms,
    )

    session = StrategySession()
    st = StrategyState()
    session.strategy_state = st
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(
            decide_megastar=lambda: SimpleNamespace(
                idx=0, reason='stub')))
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    clicks: list = []
    monkeypatch.setattr(
        test_context, 'controller',
        SimpleNamespace(mouse_move=lambda p, **k: None,
                        click=lambda p, **k: clicks.append(p)),
        raising=False)
    monkeypatch.setattr(ms, 'read_megastar_options',
                        lambda ctx, scr: [SimpleNamespace(char_id='花火')])
    monkeypatch.setattr(ms, 'area_center',
                        lambda ctx, name, screen=None: SimpleNamespace(
                            x=822, y=333))
    monkeypatch.setattr(ms.time, 'sleep', lambda *_: None)

    class _StubPickOp:
        def execute(self) -> bool:
            return True

    monkeypatch.setattr(reg_mod, 'action_op_for', lambda act, ctx, env: _StubPickOp())
    # 观察注入(观察 node 读屏函数注入点):驱动观察 node 装载 obs
    assert op.observe().is_success, '在屏观察 success'
    # ① 首派发:恰一次候选点击 + 发射即置位 + chosen 留守写端落容器
    op._do_action()
    assert len(clicks) == 1, f'首派发恰一次候选点击:{clicks!r}'
    assert st.megastar_clicked is True, '置位落策略器 StrategyState'
    assert match.gs.chosen_megastar.value == '花火', (
        'chosen_megastar = 选择点留守写端(动作事实边界不进 report)')
    # ② 同节点二次派发:标记在位 → 不再点候选
    op._do_action()
    assert len(clicks) == 1, f'二次派发不重复点候选(防反选卡死):{clicks!r}'
    # ③ 门 miss(离开巨星 overlay)→ 节点完成即复位
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    assert op._in_node(_FRAME) is False, '门 miss = 节点完成'
    assert st.megastar_clicked is False, '门 miss 复位(标记不跨节点保持)'
    # ④ 状态对象缺席:读退 False、写跳过、不冷建(裸 session 可完整跑动作)
    session2 = StrategySession()   # strategy_state 缺省 None
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session2,
                                        strategy=match.strategy,
                                        gs=_gso_match(session2)),
                        raising=False)
    op2 = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op2, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op2, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    assert op2.observe().is_success, '缺席态观察照常'
    op2._do_action()
    assert len(clicks) == 2, '缺席态读退 False → 照常点候选(无宿主防重入)'
    assert session2.strategy_state is None, '缺席态写跳过,执行层不冷建'


# (三审整删)原 test_event_screens_source_free_of_verify_segment
# 「验证段废除·源面锁」(getsource 断言两屏源无「六段」表述与 'verify'
# 字面)——源码扫描形态(README 禁止清单,红时是注释/字面变了,答不出
# 哪个运行行为坏了);验证段废除语义 = 装配点分流后无残迹可断,行为面归
# 既有双向行为锁(旧路径腿)承重。
# (收口整删)原 test_megastar_in_node_lifecycle_single_action_retry
# 「盛会之星五段在屏形态(迹到 act 为止)」删:装端口驱动的段迹面随并存
# 窗收口退役;在屏单动作语义由盛会之星两 node 形态锁
# (test_megastar_observe_reports_and_act_acts)承重。


# (原 test_encounter_refresh_emission_wired_to_registry 删:注册表取证型
#  断言——登记件缺席时发射行为半必红,取证面零独立判别力,登记形状重构
#  = 误红源。同批判:phase strategy wired / step3 supply_no_outcome。)


def test_encounter_refresh_semantics(test_context, monkeypatch) -> None:
    """遭遇刷新语义(refresh 幸存三锁并一:发射计数/守卫计数闸/刷后重读
    重决策;单驱动生产旧路径——发射点 ``_emit_refresh_click`` 与刷后重
    决策住共享分支链,生产形态承重):
    - 建议刷新 → 有次数未用 → 发射即容器计数 +1(带 refresh_click 证据),
      卡面未变帧(原「验效失败」形态)仍 +1;验效双通道拆除后(用户裁定
      2026-09-10 动作 op 禁验效):点钮+固定等待→无条件重读→带
      refresh_used=True 自然重决策(恰两次决策);本访问交回不写 chosen
      (写时点 = 重入裁决,由 test_encounter_old_path_kept_without_ports
      承重);
    - 发射前置闸逐位:容器计数在位(本局已用)/ 无剩余次数 → 不发射不计数。
    (并锁依据 = 三锁断言面同住一条刷新分支链:原
    emission_counts_and_reread_redecide_new_path(装端口驱动,段迹面随
    并存窗收口退役)/ emission_counts_on_old_path_too / guarded_by_
    session_flag_and_count。红 = 发射断流 / 前置闸失守 / 重决策丢失。)"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    # ① 发射即计数 + 刷后重读重决策(重读 = 原卡面未变形态)
    op, match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionRefreshNodeOptionsParam(reason='stub'),
        refresh_opts=opts)
    _decide_calls: list[tuple[list, bool]] = []
    _orig_decide = match.strategy.decide_encounter

    def _counting():
        _decide_calls.append((list(opts), None))
        return _orig_decide()

    match.strategy.decide_encounter = _counting
    _run_node(test_context, op, op.handle)
    gs = game_state_of(session)
    assert gs.encounter_refresh_used.value == 1, (
        f'卡面未变帧仍 +1(随点击置位不等验效,§6.5-4):'
        f'{gs.encounter_refresh_used.value}')
    assert gs.encounter_refresh_used.evidence == 'refresh_click', (
        f'发射证据逐位一致:{gs.encounter_refresh_used.evidence!r}')
    assert len(_decide_calls) == 2, (
        f'刷后无条件重读+自然重决策(恰两次决策):'
        f'{_decide_calls!r}')
    # (终态契约 §2.2:refresh_used 布尔位退役——刷新建议 = CwActionRefreshNodeOptionsParam
    #  动作,已用证据 = 容器计数,上方断言承载。)
    # ② 本局已用(容器计数在位)→ 不发射不计数
    op2, _m2, s2 = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionRefreshNodeOptionsParam(reason='stub'))
    _gs2 = game_state_of(s2)
    _gs2.write_logic(_gs2.encounter_refresh_used, 1,
                     produced_by='CwScreenEncounter',
                     sig=ChannelSig(family='logic_action',
                                    actor='CwScreenEncounter',
                                    mode='compute'))
    _run_node(test_context, op2, op2.handle)
    assert _gs2.encounter_refresh_used.value == 1, (
        '本局已用(容器计数 >0)→ 不发射不计数')
    # ③ 无剩余次数 → 不发射不计数
    op3, _m3, s3 = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionRefreshNodeOptionsParam(reason='stub'), cnt=None)
    _run_node(test_context, op3, op3.handle)
    assert game_state_of(s3).encounter_refresh_used.value is None, (
        '无次数 → 不发射不计数')


def test_encounter_refresh_counts_once_no_double(
        test_context, monkeypatch) -> None:
    """encounter 单次刷新恰 +1 无双计(容器 encounter_refresh_used 为唯一
    「已用」账,执行层不再设侧标):
    - 一次刷新流程 → 容器计数恰 1(发射链若存在第二容器写点即 ≥2,
      双计即计数毒化);
    - 真实发射后的重入(re-dispatch 再建议刷新)→ 容器计数闸拦,
      不再发射,计数不变。
    红 = 单次刷新双计 / 重入重复发射。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, _match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionRefreshNodeOptionsParam(reason='stub'),
        refresh_opts=opts)
    _run_node(test_context, op, op.handle)
    gs = game_state_of(session)
    assert gs.encounter_refresh_used.value == 1, (
        f'单次刷新恰 +1(无双计):{gs.encounter_refresh_used.value!r}')
    # 重入:同一 op 再跑一轮节点(确认重入裁决放行后仍建议刷新)
    _run_node(test_context, op, op.handle)
    assert gs.encounter_refresh_used.value == 1, (
        f'已用重入不再发射(容器计数闸):{gs.encounter_refresh_used.value!r}')


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
        pick=CwActionPickEncounterParam(idx=1, reason='stub'), confirm_success=False)
    rs = _run_node(test_context, op, op.handle)
    assert not rs.is_success and game_state_of(
        session).chosen_encounter.value is None, '验关失败 → chosen 不写'
    # (三审拆半:原尾部 getsource「chosen_* 不入注册表收编面」
    # 字面不在场断言删,豁免面纪律归 review 与代码规范。)
