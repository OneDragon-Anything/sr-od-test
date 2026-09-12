"""免战牌次数类余量链行为锁(授予→余额→消费全链)。

设计依据(持久锚):
- 效果语义正本 = docs/develop/sr_od/application/currency_war/game_state/effect-domain.md
  §8 免战牌条目(NODE_ENTER×WHILE_HELD×STATE,duties=track;次数余量
  唯一驱动 = 跳过执行成功回执 consume_use,达 2 移除;+30 经验 = 选牌
  当场)、§3(统一单调计数器模型)与 §4(递减余期与单调 counter 语义
  等价,表示法迁移候裁前按现行 remaining_uses 表示锁行为);
- 载体正本 = BoardState 数据结构设计(docs/develop/sr_od/application/
  currency_war/changes/2026-09-11-unified-state/details/
  BoardState-数据结构设计.md)§3.2.19(免战牌激活态与剩余跳过次数,
  正本 = effect_inventory.remaining_uses)/§5.1(登记播种与消费挂点)/
  §8.7 批次三件 5(EffectSpec 条目)与件 8(账本→字段桥三分);
- 卡文原文(效果语义出处)= data/cw_invest_data.py PlazaAugment
  id='151301'「进入战斗节点时,直接跳过战斗并进入下一个节点,可生效
  2次。获得30点经验。」

与 test_cw_board_state.py §8.7 批次三节(下称「批次三节」)的分工
(测试纪律「同层不重复」):彼节锁**单链节**(登记播种/consume_use 单元/burst 桥零额度 no-op/
spec 条目 id 面)与接线存在性烟雾(容忍档);本文件锁**行为链**两支——
①kernel 内全链流:授予(登记 + burst 桥同点采样,生产登记挂点形状)
→余额(卡文无刷新腿,两桥零注入,全链零 Field 写)→节点推进(余量
正交:次数类余量不被节点推进吞,与 remaining_nodes 两维互不排斥)→
消费(2→1→0 归零离场)→缺位保守;②生产挂点真实推进:经真实
``PrepActionExecutor._launch_attempt`` 跳过段驱动 登记→跳过→递减→
离场(桌面缝桩,先例 = test_cw_prep_dispatch_return_order._executor)。
混合清单求和段(免战牌+双手狸)证明桥活线,负断言非空转。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war import prep_actions
from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BoardState,
    apply_effect_burst_grant,
    board_state_of,
    grant_effect_node_refresh_balance,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    DutyFlags,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.prep_actions import PrepActionExecutor

_SPEC_ID: str = '151301'   # 免战牌 plaza 稳定 id(= EffectSpec.id,恒稳)


def test_skip_card_grant_balance_consume_chain() -> None:
    """授予→余额→消费 kernel 内全链(一局同流;链节单元锁在批次三节
    test_cw_board_state.py,本锁锁流;生产递减腿由本文件生产接线锁辖)。

    覆盖申报:生产登记挂点形状(登记 + burst 桥同点)/节点 tick 挂点
    形状(advance_node advanced 位闸门 + per-node 桥)/consume_use
    递减语义本体。接线存在性烟雾与链节单元断言归批次三节,不在此重复。
    """
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    seq0 = bs.write_seq

    # —— 授予段:登记播种 + burst 桥同点(免战牌零刷新腿 → 余额零注入)
    bs.effects.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=5)
    apply_effect_burst_grant(bs, STRATEGY_EFFECTS['免战牌'])
    entry = bs.effects.first(_SPEC_ID)
    assert entry is not None
    assert entry.remaining_uses == 2 and entry.remaining_nodes is None, \
        '播种双轨:次数类播 remaining_uses=2,节点维为空'
    assert bs.free_refresh_balance.value is None, \
        '免战牌卡文无免费刷新腿 → burst 桥零注入(余额维持未写)'
    assert bs.write_seq == seq0, '授予段零 Field 写'

    # —— 节点推进段:advanced 位触发 per-node 桥(生产 tick 挂点形状);
    # 免战牌无 per-node 腿 → 余额不动;次数类余量与节点推进正交
    advanced, expired = bs.effects.advance_node(6)
    assert advanced is True and expired == []
    grant_effect_node_refresh_balance(bs)
    assert bs.free_refresh_balance.value is None, 'per-node 桥零注入'
    assert bs.effects.first(_SPEC_ID).remaining_uses == 2, \
        '节点推进不吞次数余量(唯一驱动=consume_use,两维正交)'
    assert bs.write_seq == seq0, '节点段仍零 Field 写'

    # —— 桥活线证人 + 混合清单求和形状:同账本并入有腿条目(双手狸
    # on_node_enter=2)后,求和恰 = 有腿条目自身额度。免战牌零贡献
    # 由此与「桥死」的空转绿区分(正样活线锁另在批次三节 burst/per_node)
    bs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_t=5)
    advanced2, _expired2 = bs.effects.advance_node(7)
    assert advanced2 is True
    grant_effect_node_refresh_balance(bs)
    assert bs.free_refresh_balance.value == 2, \
        '混合清单求和恰 = 双手狸自身 2(免战牌零贡献,桥活线)'
    assert bs.free_refresh_balance.source == 'logic'
    assert bs.free_refresh_balance.evidence == 'effect_per_node'

    # —— 消费段:跳过执行落地 2→1→0,归零离场;消费不改写余额
    assert bs.effects.consume_use(_SPEC_ID) == 1
    assert bs.effects.first(_SPEC_ID) is not None, '尚有余量不移除'
    assert bs.effects.consume_use(_SPEC_ID) == 0
    assert bs.effects.first(_SPEC_ID) is None, '用尽 = 效果离场'
    assert bs.effects.consume_use(_SPEC_ID) is None, '缺位保守零动作'
    assert bs.free_refresh_balance.value == 2, '消费链不改写余额'


def test_skip_card_registry_semantics_gate() -> None:
    """卡文原文 ↔ 规格语义字段登记门(逐句映射)。

    id/duration_uses/xp_instant 三字段已由批次三节
    (test_cw_board_state.py)test_skip_battle_spec_entry_matches_base_registry 辖,本锁补其余
    语义面;其中「payload 零刷新腿」是两桥零注入行为的注册表前提,
    建模漂移(给免战牌误加刷新腿)在此与链锁双红。锁红 = 建模语义
    判定被改:对照卡文逐句重推后登记新语义,禁机械跟绿。
    """
    spec = STRATEGY_EFFECTS['免战牌']
    assert spec.trigger is TriggerKind.NODE_ENTER, \
        '「进入战斗节点时」= NODE_ENTER(节点推进族)'
    assert spec.duration is DurationKind.WHILE_HELD, \
        '「可生效2次」= 次数类持有期(余量用尽即离场,非固定节点数)'
    assert spec.category is EffectKind.STATE, \
        '跳过机制+自得经验归 STATE 族(经验发给自己;跳过本体由次数余量承载)'
    assert spec.duties == DutyFlags(track=True), \
        'duties=track 唯一(无预知/无姿态消费面;账本零决策消费=详设 §5.1 过渡口径)'
    payload = spec.payload
    assert payload.free_refresh_burst == 0, '无即时刷新腿(burst 桥零注入前提)'
    assert payload.free_refresh_per_node == 0, \
        '无每节点刷新腿(per-node 桥零注入前提)'
    assert payload.free_refresh_cond_gold_above == 0 \
        and payload.free_refresh_cond_gold_step == 0 \
        and payload.free_refresh_cond_cap == 0, '无条件刷新三元组'
    assert payload.xp_per_node == 0, \
        '经验腿仅选牌当场一支(xp_instant=30,批次三节已锁数值)'


def _skip_launch_executor(monkeypatch, session) -> PrepActionExecutor:
    """跳过子态桌面 executor(缝桩先例 =
    test_cw_prep_dispatch_return_order._executor):读屏/找区/等待/焦点
    全桩,真实执行器只跑控制流。找区按 area 名查表——出战缺席、跳过
    在场(免战子态)、未达上限警告缺席、备战标识缺席(=执行落地)、
    发射后拦截弹窗全缺席(POST_LAUNCH_BLOCKERS 各锚默认 False)。
    """
    ex = object.__new__(PrepActionExecutor)

    def _find(screen, screen_name, area_name, **_kw) -> SimpleNamespace:
        return SimpleNamespace(is_success=area_name == '按钮-跳过')

    ex._op = SimpleNamespace(
        screenshot=lambda: SimpleNamespace(),
        round_by_find_area=_find,
    )
    ex._ctx = SimpleNamespace(
        controller=SimpleNamespace(
            mouse_move=lambda p: None,
            click=lambda p, **_kw: None,
            game_win=SimpleNamespace(is_win_active=True, active=lambda: None),
        ),
        cw_match=SimpleNamespace(session=session),
    )
    monkeypatch.setattr(prep_actions, 'area_center',
                        lambda ctx, name, *a, **kw: None)
    monkeypatch.setattr(prep_actions.time, 'sleep', lambda s: None)
    return ex


def test_skip_decrement_production_wiring(monkeypatch) -> None:
    """生产挂点真实推进锁:登记→跳过执行落地→consume_use→余量递减→离场。

    驱动 = 真实 ``PrepActionExecutor._launch_attempt`` 跳过段(prep_actions
    「按钮-跳过」分支,详设 §3.2.19/§5.1 跳过递减挂点):成功判据 =
    备战标识消失验证通过,递减恰挂在该判定之后。锁红 = 生产递减腿
    断裂(挂点删除/短路/子态分支名漂移/会话取径漂移)——批次三节的
    substring 接线烟雾(容忍档)由本锁升级行为锁。三段断言:首跳
    2→1(尚有余量不移除)/再跳 1→0 归零离场/缺位后再跳仍出战成功
    (递减挂点与登记挂点解耦,登记面缺位的局零动作不炸发射回执)。
    """
    session = StrategySession()
    bs = board_state_of(session)
    bs.effects.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=5)
    ex = _skip_launch_executor(monkeypatch, session)

    assert ex._launch_attempt() == (True, '出战成功')
    entry = bs.effects.first(_SPEC_ID)
    assert entry is not None and entry.remaining_uses == 1, \
        '首跳递减 2→1(余量在生产调用链上真实推进)'

    assert ex._launch_attempt() == (True, '出战成功')
    assert bs.effects.first(_SPEC_ID) is None, '再跳 1→0,用尽 = 效果离场'

    assert ex._launch_attempt() == (True, '出战成功'), \
        '登记面缺位(用尽离场后)= 零动作,不炸发射回执'
