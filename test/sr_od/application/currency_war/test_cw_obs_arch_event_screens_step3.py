"""统一观察架构·逐屏迁移第二批量锁(试点步骤 3:补给 + 余事件屏按族批量)。

设计正本 = docs/develop/sr_od/application/currency_war/flow/统一观察架构-画面op基类设计.md
(下称「架构设计」);迁移粒度依据 = 开放问题清单 B3 三段走第二段(代表屏
断言集模板已立 → 「补给 + 余事件屏按族批量」)+ §9.2 迁移步骤 4 建议序
(遭遇 → 补给 → 事件屏族);迁移手法单一源 = 试点步骤 2 先例
(装配点分流 + 五段转录 + 实机适配器封口 + on_outcome 注册表;本批八屏按
其「盛会之星型」共享动作体形态落码,lifecycle_observe 消费
``_observation_port()`` 位)。

**本批屏清单(B3 族表 = 架构设计 §6.6 事件选择行十屏 − 步骤 2 已迁两屏)**:
补给 CwScreenSupplyNode / 伙伴 CwScreenPartner / 骇入策划 CwScreenPlanner /
祈愿试炼 CwScreenWishTrial / 命运卜者 CwScreenFortune / 星徽秘典
CwScreenBookcard / 装备三选一 CwScreenEquipPick / 专家邀请函
CwScreenExpertInvite。武装箱弹窗(CwScreenArmoryBox)不在本批:B4 把它点名列
入弹窗/导航类 op(非事件屏族,无选择面)。

**F11/B3 sim 腿例外清单(随迁移批逐屏落测试 docstring)**:

- 伙伴/祈愿试炼/命运卜者/骇入策划/星徽秘典/装备三选一/专家邀请函七屏:
  sim 腿 = 不适用——sim 无对应画面段/决策段(引擎事件即时落定,架构设计
  §3.2 事件浮层族行),等价判据主承重 = 实机在册行为锁 + 写入流对拍
  (实机腿),禁引用 sim 域对拍;
- 补给(CwScreenSupplyNode):sim 腿 = 引擎补给决策段**已在**(engine_p1
  直调 kernel decide_supply,T5 接口收敛挂账)但**本批未接线**(sim 接线批
  后续),本批等价判据仍以实机在册行为锁承重。

锁的语义(测试纪律 7 自检;出处 = 架构设计 §9.1/§6.4-R-E/B5;先例 =
test_cw_obs_arch_event_screens.py 断言集模板;生产端口恒 None 直连旧
路径——迁移结构锁与八屏装配点分流锁已随并存窗收口整删,行为锁单驱动
生产路径):

- **注册表零登记锁**(§6.4 收编面本批零行):八屏源无 register_outcome_
  hook / fire_emit_hooks 接线——§6.4 表登记件全不涉事件选卡屏;supply_
  refresh_used live 写端 = ``_do_action`` 刷新分支单点直写容器(渠道②
  logic_action,发射即记不等验效;注册表缺席 = 本点唯一,无双计面)。
  红 = 未经申报面擅立登记件(EMIT_TRIGGERED_DECLARED 同款纪律)。
- **共享动作体锁**:七选卡屏 post-gate 体纯移入 ``_handle_overlay``(两路径
  共用零转录,先例 = 盛会之星 ``_do_action``);supply 选定记录面
  (chosen_supply 确认即写)住 ``_do_action`` 真选分支(行为锁正本 =
  test_cw_game_state_consume 的确认即写锁)。
- **chosen_* 豁免留守锁**(§2.2/§6.5-6):chosen_* 写端仍内联于共享体
  (不收编入 on_outcome 注册表);supply 已改确认即写时点
  (选定中转暂存宿主已随执行层状态类目退役),余屏维持
  出口验真通过分支写。
- **验证段废除源面锁**(用户裁定 2026-09-10,同
  test_cw_obs_arch_event_screens.py 同名锁):八屏源无「六段」表述、无
  'verify' 段迹字面。

驱动方式 = 真类实例(构造走 __init__,适配器位在位)+ 依赖桩化
(OCR 读链/机械派发半;生产端口缺省 None = 直连旧路径,行为锁单驱动
生产形态)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickSupplyParam,
    CwActionRefreshSupplyParam,
)

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;共享体桩只验传递不断言内容)


# ==================== 迁移结构锁(§9.1 并存期)====================


# (收口整删)原 test_migration_batch3_ops_inherit_base「八 op 均为
# CwScreenOpBase 子类」(连 _BATCH3_SCREENS 常量)删:继承结构 = 静态形状,
# 红时答不出哪个运行行为坏了;结构面归 review 与代码规范。


def test_supply_chosen_written_on_confirm_pick(test_context, monkeypatch) -> None:
    """补给 chosen_supply 确认即写行为锁(选定中转暂存宿主已随执行层状态
    类目退役,写端 = 选定确认时点;口径分叉申报 = supply 直写,chosen_tome
    维持出口验真后写家族口径——差异理由 = supply 的中转暂存载体已消亡,
    直写是载体消亡后的唯一形态):
    - 真选(有选项 + 决策选列):确认分支单次逻辑写入 (角色,装备,有钻石)
      三元组,source=logic,机械派发半照发(记录面不拦截动作);
    - 刷新轮不写 = 真选守卫(兜底点卡/刷新路径与真选分支互斥)。
    OCR 读链/配置/机械派发半桩化,只锁记录面。
    (原 test_supply_chosen_staging_lifecycle 暂存生命周期锁随暂存载体退役;
    consuming 侧 stash 写法锁
    test_supply_chosen_written_from_stash_after_exit_only 同批删除,
    断言语义由本锁承重。)"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_action_registry,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    # ① 真选:确认即写
    session = StrategySession()
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(decide_supply=lambda: CwActionPickSupplyParam(idx=0, reason='test')))
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=True)
    monkeypatch.setattr(sn, 'read_supply_options',
                        lambda ctx, screen: [(opt, SimpleNamespace(x=900, y=550))])
    dispatched: list = []

    class _StubPickOp:
        def execute(self, env) -> bool:
            dispatched.append(env)
            return True

    monkeypatch.setattr(cw_action_registry, 'action_op_for',
                        lambda act: _StubPickOp())
    op._do_action(_FRAME)
    gs = game_state_of(session)
    assert gs.chosen_supply.value == ('希儿', '星币收集器', True), (
        f'确认即写:容器持选定三元组,实得 {gs.chosen_supply.value!r}')
    assert gs.chosen_supply.source == 'logic', '单次逻辑写入(source=logic)'
    assert len(dispatched) == 1, '机械派发半照发(记录面不拦截动作链)'
    # ② 刷新轮不写(真选守卫;锚读缺零点击在册语义)
    session2 = StrategySession()
    match2 = SimpleNamespace(
        session=session2,
        strategy=SimpleNamespace(decide_supply=lambda: CwActionRefreshSupplyParam(reason='test')))
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match2,
    )
    match2.gs = _gso_match2(match2.session)
    monkeypatch.setattr(test_context, 'cw_match', match2, raising=False)
    op2 = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op2, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op2, '_read_refresh_anchor', lambda screen: None)
    op2._do_action(_FRAME)
    assert game_state_of(session2).chosen_supply.value is None, \
        '刷新轮不写 = 真选守卫'


# (原 test_supply_no_outcome_registry_item 删:负向注册表取证断言——
#  「不得私设登记件」红时答不出哪个运行行为坏了,架构申报纪律归 review
#  与代码规范;supply 行为面由同文件 chosen 暂存/重入弃陈旧两锁承重。)


def test_supply_refresh_emission_counts_container(
        test_context, monkeypatch) -> None:
    """supply live 刷新写端锁(执行侧旗标已随执行层状态类目退役,live
    写端接容器 ``supply_refresh_used`` 计数——渠道② 单点,发射即记不等
    验效,含锚读缺零点击路径):
    - 刷新发射 → 容器计数恰 +1(evidence=refresh_click;无双计面——
      本点 = 唯一容器写点);
    - 计数在位(>0 = 已用)重入 → 不再发射不计数。
    OCR 读链/锚读/机械派发桩化,只锁记录面与闸面。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_action_registry,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    session = StrategySession()
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(
            decide_supply=lambda: CwActionRefreshSupplyParam(reason='test')))
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, '_read_refresh_anchor', lambda screen: None)
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=True)
    monkeypatch.setattr(sn, 'read_supply_options',
                        lambda ctx, screen: [(opt,
                                              SimpleNamespace(x=900, y=550))])

    class _StubPickOp:
        def execute(self, env) -> bool:
            return True

    monkeypatch.setattr(cw_action_registry, 'action_op_for',
                        lambda act: _StubPickOp())
    # ① 刷新发射(锚读缺零点击路径)→ 容器 +1
    op._do_action(_FRAME)
    gs = game_state_of(session)
    assert gs.supply_refresh_used.value == 1, (
        f'刷新发射即计数恰 +1(发射即记不等验效):'
        f'{gs.supply_refresh_used.value!r}')
    assert gs.supply_refresh_used.evidence == 'refresh_click', (
        f'发射证据逐位一致:{gs.supply_refresh_used.evidence!r}')
    # ② 计数在位重入 → 不再发射不计数
    op._do_action(_FRAME)
    assert gs.supply_refresh_used.value == 1, (
        f'已用重入不发射(容器计数闸):{gs.supply_refresh_used.value!r}')


# ==================== 七选卡屏(收口整删)====================


# (收口整删)原 test_gated_screens_dispatch_both_ways /
# test_gateless_screens_dispatch_both_ways / test_expert_choose_dispatch_
# both_ways(带门/无门/专家邀请函三组选卡屏的装端口五段分流锁,连唯一
# 消费者 _make_op helper)删:装端口驱动的段迹/分流面随并存窗收口退役
# (生产端口恒 None);旧路径在屏单动作语义已由 supply 同族锁同形承重,
# 七屏体为纯转录、无域写入面,无独立行为锁可立——覆盖缺口归总纲收口
# 申报,不再以分流锁占位。

# (三审整删)原 test_expert_open_card_node_stays_legacy「纯导航留旧
# 路径申报面」(getsource 方法体断言无 run_lifecycle/observation_source)——
# 源码扫描形态(README 禁止清单);开卡节点路由面归 review 与代码规范。
# (三审整删)原 test_batch3_no_outcome_registry_wiring「注册表零登记
# 锁」与 test_batch3_sources_free_of_verify_segment「验证段废除·源面锁」
# (八屏 getsource 字面在场/不在场断言)——源码扫描形态;注册表收编纪律
# 归 review 与代码规范,验证段废除语义 = 分流后无残迹可断。
