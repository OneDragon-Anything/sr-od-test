"""分解万物(id 331801)登记形态锁(镜像 src = kernel/cw_investments.py
STRATEGY_EFFECTS 分解万物条目 + kernel/cw_effect_inventory.py
BattlefieldEffect.equips_transform 字段与 EQUIPS_TRANSFORM_ADVANCED_MATTER
词表;按被测方法拆目录规范落位——test_gain_chain.py 超线冻结禁追加,
登记区新锁落本拆目录,先例 = 同目录 test_gain_invest_strategy_* 镜像文件;
锁形承同域先例公司军火更新·银登记形态两锁)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-376-fenjie-
wanwu.md(定稿)§4 锁 3(REVIEW-T376 §5④ 编排者定形案甲:pending=True +
保守支 notes,断言联动 pending is True):
- 变换腿登记形态(session 选入 → 账本条目四元组 + payload 词表值 +
  duties.track 置位 + pending 冻结;锁登记形态与词表值,防裸串漂移与
  载体误配);
- 三桥 no-op 负断言哨(限定当前 spec 形态 = PLANE_START / WHILE_HELD /
  BATTLEFIELD + equips_transform-only payload;桥 no-op 本质 = 桥
  docstring 契约——payload 无对应字段或缺省零;后继批若合法给
  equips_transform 接执行桥,须随批改哨)。

效果条目1 发放链(「获得一个物质分解液」选卡落地入栏)由
test_gain_invest_strategy_fenjie_wanwu_pick.py 承载(两注册面分域);
效果条目3 追伤/减伤数值面战力类零建模无链锁(零执行端,登记 notes 申报)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EQUIPS_TRANSFORM_ADVANCED_MATTER,
    DurationKind,
    EffectKind,
    TriggerKind,
    apply_board_rewrite,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    apply_effect_burst_grant,
    grant_effect_node_refresh_balance,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


def _make_gs() -> GameState:
    """观测面空装配(bench/equips 两域观察为空集;镜像
    test_gain_invest_strategy_equips_reroll._make_gs 同名形态,本卡登记面
    只涉账本与注册两域)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    return gs


def test_gain_invest_strategy_fenjie_wanwu_register_shape() -> None:
    """分解万物 变换腿登记形态锁:session 选入 → 账本条目形态 =
    PLANE_START(占位)/ WHILE_HELD / BATTLEFIELD + payload.equips_transform
    词表值(防裸串漂移与载体误配)+ duties.track 置位 + pending 冻结。
    发放腿(选卡落地物质分解液入栏)不属本锁辖域,由发放腿链锁承载。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '分解万物', rand=False, sig=_LSIG)
    assert gs.active_strategies.value == ['分解万物'], '注册入表'
    entry = gs.effects.first('331801')
    assert entry is not None, '账本登记非空'
    spec = entry.spec
    assert spec.trigger == TriggerKind.PLANE_START, (
        '触发 = 位面开始(占位:变换面系游戏侧自动改写非本端动作,'
        '零行为差纯键面惯例)')
    assert spec.duration == DurationKind.WHILE_HELD, '持续期 = 持有绑定'
    assert spec.category == EffectKind.BATTLEFIELD, '类别 = 战场改变'
    assert spec.payload.equips_transform == EQUIPS_TRANSFORM_ADVANCED_MATTER, \
        '词表值单一源(禁裸串漂移)'
    assert spec.duties.track, 'duties.track 置位'
    assert not spec.duties.predict and not spec.duties.respond, \
        'predict/respond 不设(现役读链无预知/姿态消费面)'
    assert spec.pending is True, (
        'pending 冻结(案甲:辖域二义——持续含后续获得件 vs 拿卡拍存量'
        '一次性,保守支 notes 承载,实采 verdict 回填通道留)')


def test_gain_invest_strategy_fenjie_wanwu_bridges_noop() -> None:
    """分解万物 变换面零执行端负断言哨(限定当前 spec 形态 = PLANE_START /
    WHILE_HELD / BATTLEFIELD + equips_transform-only payload):三桥逐一调
    全 no-op——burst 桥零 Field 行 / 板面重写桥返回 None / 节点边界桥免费
    余额零增。桥 no-op 本质 = 桥 docstring 契约(payload 无对应字段或缺省
    零),本锁增量 = 本条目形态哨;变换面零逻辑写端(游戏侧自动改写,bot
    备战帧 equips 整表观察收真值),后继批若合法接执行桥须随批改本锁。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '分解万物', rand=False, sig=_LSIG)
    spec = gs.effects.first('331801').spec
    seq_after_gain = gs.write_seq
    apply_effect_burst_grant(gs, spec)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, 'burst 桥 no-op(零 Field 行)'
    assert apply_board_rewrite(gs, spec) is None, '板面重写桥 no-op'
    assert gs.write_seq == seq_after_gain, '板面重写桥零写'
    grant_effect_node_refresh_balance(gs)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, '节点边界桥零授予(免费余额零增)'
