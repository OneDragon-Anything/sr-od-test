"""合成 3 星事件条件金发放类效果条目测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_star_merge_gold;分方法拆目录规范落位,文件镜像超限纪律 =
新函数落拆目录新文件,先例 = 同目录 check_strategy_* 族镜像)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-135-xingxing-
xiangyin.md(定稿)§4 锁 1 + REVIEW-T135 §四 ④(卡面官方原文:「每次合成
3星角色时，获得5金币。立刻获得1个【员工投影仪】。」):

- 主锁:持卡局 gain_character 2★×3 同名 → gold 恰 +5(观察笔一笔,
  evidence 带 sim:engine: 命名空间前缀,sim 侧策略金币效果条目家族统一形态);
- 级联计数:1→2→3 一次调用只 +5(to_star==3 单事件计数,级联中间档
  非 3 星合成);一次调用双 3 星合并 → +10(每次合成逐事件计);
- 负锁:非持卡局零写 / live 门控(未装配 sim)零写 / gold 未读宁缺勿造;
- 隔离互证:同触发异载体双向鸭子缺省——武力刷新条目在本效果条目零发放 ∧
  本卡条目在 T-109 刷新效果条目零发放(与 test_invest_strategy 的 T-109
  注册锁互补,两条效果条目字段判别双向隔离的回归基准)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    apply_on_merge_refresh_grant,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_star_merge_gold,
    gain_character,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_SIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_EV_PREFIX = 'sim:engine:strategy_star_merge_gold:'

_CARD = '星星相印'


class _SimPresenceStub:
    """装配占位后端(仅令 ``sim_backend_installed()`` 为真;本效果条目不触后端
    任何口,触即 AssertionError 响亮——被测门控只读装配槽非 None;
    test_refresh_shop 同名先例)。"""

    def screen_identity(self) -> str:
        raise AssertionError('合成金币效果条目不触后端读口')

    def observe(self, screen_name: str) -> object:
        raise AssertionError('合成金币效果条目不触后端观察')

    def visible(self, screen_name: str, area_name: str) -> bool:
        raise AssertionError('合成金币效果条目不触后端门问询')

    def click_answer(self, op: object, screen_name: str, area_name: str,
                     until_find_all: object, until_not_find_all: object):
        raise AssertionError('合成金币效果条目不触后端点击')

    def advance(self, decl: object) -> None:
        raise AssertionError('合成金币效果条目不触后端推进')


@pytest.fixture
def sim_installed():
    """sim 形态:装配占位后端;teardown 必卸(模块槽进程全局)。"""
    cw_sim_ports.install_sim_backend(_SimPresenceStub())
    yield
    cw_sim_ports.uninstall_sim_backend()


def _gs(*, card: str | None = _CARD, gold: int | None = 30) -> GameState:
    """直构状态容器(card=None = 账本零命中;gold=None = 未读)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=ChannelSig(family='obs',
                                                 actor='test-seed'))
    if card is not None:
        gs.effects.register_strategy(STRATEGY_EFFECTS[card], (1, 2))
    return gs


def test_direct_single_star3_event_grants_five(sim_installed) -> None:
    """函数单元主锁:持卡 + 单条 3 星事件 → 恰 +5(观察笔一笔,值/来源/
    证据串三面钉死;证据串带 sim:engine: 命名空间——调用点金位可为 logic
    来源,覆盖须落失配抑制分支,禁入真失配告警)。"""
    gs = _gs()
    seq0 = gs.write_seq
    check_strategy_star_merge_gold(gs, (('甲', 3),), sig=_SIG,
                                   producer='TestProducer')
    assert gs.gold.value == 35, '单 3 星事件 +5'
    assert gs.gold.source == 'observation', '观察通道(sim 状态副本数值面)'
    assert gs.gold.evidence == 'sim:engine:strategy_star_merge_gold:1', \
        '证据串 = 命名空间前缀 + 写点 tag + 事件计数'
    assert gs.write_seq == seq0 + 1, '恰一次观察笔'


def test_cascade_counts_single_star3_event(sim_installed) -> None:
    """级联计数锁:一次调用内 1→2→3 级联(facts = 中间档 + 3 星档)只
    +5——「每次合成3星」按合成结果事件计,级联中间档 2 星合成非 3 星
    合成(设计 §2.1 发放量口径)。"""
    gs = _gs()
    seq0 = gs.write_seq
    check_strategy_star_merge_gold(gs, (('甲', 2), ('甲', 3)), sig=_SIG,
                                   producer='TestProducer')
    assert gs.gold.value == 35, '级联一次调用只计一个 3 星事件 +5'
    assert gs.gold.evidence == 'sim:engine:strategy_star_merge_gold:1'
    assert gs.write_seq == seq0 + 1, '恰一次观察笔'


def test_two_star3_events_grant_each(sim_installed) -> None:
    """多事件逐件计:一次调用两条 3 星事件(不同名各自凑三)→ +10,
    证据串计数 = 2(「每次合成3星」逐事件,与刷新出对单笔语义分域)。"""
    gs = _gs()
    check_strategy_star_merge_gold(gs, (('甲', 3), ('乙', 3)), sig=_SIG,
                                   producer='TestProducer')
    assert gs.gold.value == 40, '双 3 星事件 +10(逐事件计)'
    assert gs.gold.evidence == 'sim:engine:strategy_star_merge_gold:2', \
        '证据串计数 = 3 星事件数(判读可辨)'


def test_non_star3_events_zero_grant(sim_installed) -> None:
    """升星非 3 星档:仅 1→2 事件 → 零动作(值/来源保持,零写)。"""
    gs = _gs()
    seq0 = gs.write_seq
    check_strategy_star_merge_gold(gs, (('甲', 2),), sig=_SIG,
                                   producer='TestProducer')
    assert gs.gold.value == 30 and gs.gold.source == 'observation', \
        '非 3 星档零发放'
    assert gs.write_seq == seq0, '零观察行'


def test_no_card_zero_grant(sim_installed) -> None:
    """非持卡局零写(账本零命中 = 条目缺位);表外卡同路(白名单表外禁
    自动猜装,只登记不写状态的实现分支未收录名不分派)。"""
    for card in (None, '躺平'):
        gs = _gs(card=card)
        seq0 = gs.write_seq
        check_strategy_star_merge_gold(gs, (('甲', 3),), sig=_SIG,
                                       producer='TestProducer')
        assert gs.gold.value == 30 and gs.write_seq == seq0, \
            f'{card}: 零命中保守零动作'


def test_live_form_zero_write() -> None:
    """live 门控负锁(核心):未装配 sim(纯实机态)→ 持卡 + 3 星事件
    仍零写——防门控失效退化成猜测写金(金面禁猜测直写,真值 = 观察
    覆盖兜底)。"""
    cw_sim_ports.uninstall_sim_backend()
    gs = _gs()
    seq0 = gs.write_seq
    check_strategy_star_merge_gold(gs, (('甲', 3),), sig=_SIG,
                                   producer='TestProducer')
    assert gs.gold.value == 30 and gs.gold.source == 'observation', \
        'live 门控:零金写'
    assert gs.write_seq == seq0, '零写(live 形态)'


def test_gold_unread_skips_defensively(sim_installed) -> None:
    """gold 现值 None(未观察)→ 宁缺勿造跳过(持卡 + 事件在场仍零写;
    事件携带事实无 done 一次性标志位,下个合成事件自动重查)。"""
    gs = _gs(gold=None)
    seq0 = gs.write_seq
    check_strategy_star_merge_gold(gs, (('甲', 3),), sig=_SIG,
                                   producer='TestProducer')
    assert gs.gold.value is None, '未读保持未读(禁造)'
    assert gs.write_seq == seq0, '零写'


def test_gain_chain_three_two_star_merge_pays_five(sim_installed) -> None:
    """获得链集成主锁(设计 §4 锁 1 主条):持卡局 gain_character 2★×3
    同名 → gold 恰 +5、观察笔一笔(链内采集 facts → 顶层收尾发火,
    T-26 同区时序)。"""
    gs = cw4_gs(gold=30, node_fill=False, shop_screen='off',
                bench=[_bc('花火', 2), _bc('花火', 2)])
    gs.effects.register_strategy(STRATEGY_EFFECTS[_CARD], (1, 2))
    gold_before = int(gs.gold.value or 0)
    gain_character(gs, '花火', 2, rand=False, sig=_SIG, evidence='t:chain',
                   producer='TestChain')
    assert gs.gold.value == gold_before + 5, '2★×3 合成 3★ → +5'
    assert gs.gold.source == 'observation', '观察通道'
    assert gs.gold.evidence == 'sim:engine:strategy_star_merge_gold:1', \
        '证据串 = 本效果条目写点(链顶层发火一笔)'
    units = [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
             if s is not None and s.kind == 'unit' and s.unit is not None]
    assert ('花火', 3) in units, '合成产物 3★ 在席(链主分支照常)'


def test_gain_chain_cascade_single_grant(sim_installed) -> None:
    """获得链级联锁:一次 gain_character 调用内 1→2→3 级联只 +5
    (facts 含级联中间档,函数按 to_star==3 单事件计数)。"""
    gs = cw4_gs(gold=30, node_fill=False, shop_screen='off',
                bench=[_bc('花火', 1), _bc('花火', 1),
                       _bc('花火', 2), _bc('花火', 2)])
    gs.effects.register_strategy(STRATEGY_EFFECTS[_CARD], (1, 2))
    gain_character(gs, '花火', 1, rand=False, sig=_SIG, evidence='t:casc',
                   producer='TestChain')
    assert gs.gold.value == 35, '级联一次调用只 +5(非 +10)'
    assert gs.gold.evidence == 'sim:engine:strategy_star_merge_gold:1'


def test_gain_chain_no_card_zero_write() -> None:
    """获得链非持卡局零写:同操作(2★×3 合成 3★ 照常发生)金位零写
    (账本零命中,函数级零动作经链调用点传导)。"""
    gs = cw4_gs(gold=30, node_fill=False, shop_screen='off',
                bench=[_bc('花火', 2), _bc('花火', 2)])
    gold_before = int(gs.gold.value or 0)
    gain_character(gs, '花火', 2, rand=False, sig=_SIG, evidence='t:nocard',
                   producer='TestChain')
    assert gs.gold.value == gold_before and gs.gold.source == 'observation', \
        '非持卡局零金写'


def test_duck_default_isolation_both_directions(sim_installed) -> None:
    """同触发异载体双向鸭子缺省隔离(与 T-109 互证):
    ① 武力刷新条目在本效果条目零发放(payload 无 gold_per_3star_merge 字段,
    ON_MERGE ∧ ECONOMY 双过滤命中但鸭子缺省 0);
    ② 本卡条目在 T-109 刷新效果条目零发放(payload 无 refresh_per_compose
    字段,名单集零命中同判)——两条效果条目字段判别双向隔离回归基准。"""
    gs = _gs(card='武力刷新')
    seq0 = gs.write_seq
    check_strategy_star_merge_gold(gs, (('甲', 3),), sig=_SIG,
                                   producer='TestProducer')
    assert gs.gold.value == 30 and gs.write_seq == seq0, \
        '武力刷新:本效果条目鸭子缺省 0 零发放'

    gs2 = _gs(card=_CARD)
    seq1 = gs2.write_seq
    apply_on_merge_refresh_grant(gs2, merges=2)
    assert gs2.free_refresh_left.value in (None, 0) \
        and gs2.write_seq == seq1, '星星相印:刷新效果条目零命中零发放'
