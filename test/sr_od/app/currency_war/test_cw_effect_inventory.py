"""效果账本机制主题锁(effect inventory 写入归属·板面重写桥)。

设计出处(持久索引):
- 写入归属两行单一源 = BoardState 数据结构设计 §5「全员晋升/人力重组」两行
  (docs/develop/sr_od/application/currency_war/changes/2026-09-11-unified-state/
  details/BoardState-数据结构设计.md,迭代期详设;持久正本 =
  docs/develop/currency_war/game_state/effect-domain.md §8 同名条);
- 实现单一源 = kernel/cw_effect_inventory.py(BOARD_REWRITE_* 语义词表 +
  apply_board_rewrite 桥);
- 归属判据 = §5.3(确定性可算 → 逻辑写;含随机 → 零逻辑写端,观察收口)。

辖域 = 板面重写两形态行为锁:整场上阵替换(全员晋升,随机面 = 负写端)/
全场出售+再发牌(人力重组,出售面 = 逻辑写、发牌面 = 不造单位)+ 词表锚 +
边界(从未观察字段/出售域部分读退款零写入/零退款金翻标禁令/未知语义/
非重写条目)。
同族桥(burst/每节点/容量投影)行为锁在 test_cw_board_state.py(§8.7 批次三节)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    BoardState,
    ChannelSig,
    Unit,
    register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    BOARD_REWRITE_SELL_ALL,
    BOARD_REWRITE_UPGRADE_ALL,
    BoardRewriteReport,
    apply_board_rewrite,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_state import sell_refund

register_sig_actors('TestSigWriter')


def _sig() -> ChannelSig:
    """渠道①签名(obs 族;观察构造 BoardState 前置态)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _char_by_cost(cost: int) -> str:
    """从角色注册表按费用取一个稳定代表名(数据在仓,断言可复现)。"""
    names = sorted(n for n, c in CHARACTERS.items() if c.cost == cost)
    assert names, f'注册表缺 cost={cost} 角色(数据面漂移,换锚并同步本注释)'
    return names[0]


def _unit(cost: int, star: int, slot: int) -> Unit:
    return Unit(char_id=_char_by_cost(cost), star=star, slot=slot)


def _make_bs(front: list[Unit] | None, back: list[Unit] | None,
             bench_slots: list[BenchSlot] | None, gold: int | None,
             capacity: int = 9) -> BoardState:
    """构造带前置观察态的 BoardState(None = 该字段从未观察)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    if front is not None:
        bs.observe(bs.front_row, front, sig=_sig())
    if back is not None:
        bs.observe(bs.back_row, back, sig=_sig())
    if bench_slots is not None:
        bs.observe(bs.bench, BenchView(slots=bench_slots, capacity=capacity),
                   sig=_sig())
    if gold is not None:
        bs.observe(bs.gold, gold, sig=_sig())
    return bs


def _populated_bs(gold: int | None = 20) -> BoardState:
    """标准出售局面前置:前排 2 单位 + 后排 1 单位 + 备战席 1 单位 1 箱。"""
    return _make_bs(
        front=[_unit(1, 1, 1), _unit(4, 2, 2)],
        back=[_unit(2, 2, 1)],
        bench_slots=[BenchSlot(kind='unit', unit=_unit(1, 1, 1)),
                     BenchSlot(kind='supply_box')]
        + [BenchSlot(kind='empty')] * 7,
        gold=gold)


# ============================================================ 语义词表锚


def test_registry_entries_use_semantic_wordlist() -> None:
    """注册表 board_rewrite 值 = 语义词表(单一词表防散落字符串漂移);
    词表两值本身锁设计 §5 记载的字面量(桥的分支判据 = 消费端契约)。"""
    assert BOARD_REWRITE_UPGRADE_ALL == 'upgrade_all_cost+1'
    assert BOARD_REWRITE_SELL_ALL == 'sell_all'
    assert STRATEGY_EFFECTS['全员晋升'].payload.board_rewrite \
        == BOARD_REWRITE_UPGRADE_ALL
    assert STRATEGY_EFFECTS['人力重组'].payload.board_rewrite \
        == BOARD_REWRITE_SELL_ALL


# ============================================================ 形态一:整场上阵替换


def test_upgrade_all_random_face_writes_nothing() -> None:
    """全员晋升形态(§5 归属行一):替换面 = 高 1 费随机角色,不可准确算
    → 零逻辑写端、观察收口——桥对任何字段零写入(负写端锁),报告仅留证。
    随机面若被「补」上逻辑写,本锁红(该写端会与观察覆盖打架进缺陷台账)。"""
    bs = _populated_bs()
    seq0 = bs.write_seq
    rep = apply_board_rewrite(bs, STRATEGY_EFFECTS['全员晋升'])
    assert bs.write_seq == seq0, '随机替换面禁任何逻辑写入(设计 §5 全员晋升行)'
    assert bs.front_row.source == 'observation' \
        and len(bs.front_row.value) == 2, '前排原样(未被替换/清空)'
    assert bs.gold.value == 20 and bs.gold.source == 'observation', '金原样'
    assert rep == BoardRewriteReport(rewrite=BOARD_REWRITE_UPGRADE_ALL,
                                     refund_gold=0, sold_units=0)


# ============================================================ 形态二:全场出售+再发牌


def test_sell_all_clears_units_and_refunds_gold() -> None:
    """人力重组出售面(§5 归属行二·确定性分支):前台/后台/备战席逻辑清空
    (source=logic)+ 退款按卖价公式入金(单一源 = cw_state.sell_refund 推导
    期望);发牌面(2★3费×1+2★2费×2+2★1费×2)= 随机 → 桥禁造任何单位,
    清空后全槽 empty,补位真值走下一备战帧观察。"""
    bs = _populated_bs()
    seq0 = bs.write_seq
    rep = apply_board_rewrite(bs, STRATEGY_EFFECTS['人力重组'], frame='p1-r3')
    # 出售面退款 = Σ sell_refund(star, cost)(单一源推导):1★1费+2★4费+
    # 2★2费+1★1费。
    expected_refund = (sell_refund(1, 1) + sell_refund(2, 4)
                       + sell_refund(2, 2) + sell_refund(1, 1))
    assert bs.write_seq == seq0 + 4, '恰四次写入(前排/后排/备战席/金)'
    assert bs.front_row.value == [] and bs.front_row.source == 'logic', \
        '前排逻辑清空'
    assert bs.back_row.value == [] and bs.back_row.source == 'logic', \
        '后排逻辑清空'
    bench = bs.bench.value
    assert bench.capacity == 9, '备战席容量保留(容量辖域 = 容量投影桥)'
    assert len(bench.slots) == 9 \
        and all(s.kind == 'empty' for s in bench.slots), \
        '槽位表原位清空且零造单位(发牌面观察收口)'
    assert bs.bench.source == 'logic'
    assert bs.gold.value == 20 + expected_refund, '退款按卖价公式入金'
    assert bs.gold.source == 'logic'
    for f in (bs.front_row, bs.back_row, bs.bench, bs.gold):
        assert (f.evidence or '').startswith('effect_board_rewrite'), \
            '写入 evidence 带板面重写标记(留证)'
    assert rep == BoardRewriteReport(
        rewrite=BOARD_REWRITE_SELL_ALL, refund_gold=expected_refund,
        sold_units=4, cleared_fields=('front_row', 'back_row', 'bench'),
        partial_read=False)


def test_sell_all_unknown_char_cost_falls_back_mid() -> None:
    """未知 char_id 单位按中费 3 保守估(cw_state.bench_char_cost 兜底口径),
    退款推导随兜底价走,不炸不跳过;bench 从未观察 = 出售域未全读 → 退款
    零写入留证(effect-domain.md §6.3:输入不完整不满足确定性分支前提,
    禁部分退款翻标 logic 权威值)。"""
    bs = _make_bs(front=[Unit(char_id='不存在角色xx', star=2, slot=1)],
                  back=[], bench_slots=None, gold=10)
    rep = apply_board_rewrite(bs, STRATEGY_EFFECTS['人力重组'])
    assert rep is not None and rep.sold_units == 1
    assert rep.refund_gold == sell_refund(2, 3), '兜底中费 3 进退款推导(留证)'
    assert rep.partial_read is True, 'bench 从未观察 = 出售域未全读'
    assert bs.gold.value == 10 and bs.gold.source == 'observation', \
        '部分读 → 退款零写入(禁部分退款写成 logic 权威值)'
    assert bs.front_row.value == [], '识别不出名字不影响出售清空事实'


def test_sell_all_preserves_active_bench_capacity() -> None:
    """容量时限效果激活期(如节省工位 capacity=3)与人力重组并存:清空
    保留现容量 3 与槽数,禁顺手回写默认 9(容量辖域 = 容量投影桥)。"""
    bs = _make_bs(
        front=[], back=[],
        bench_slots=[BenchSlot(kind='unit', unit=_unit(3, 1, 1)),
                     BenchSlot(kind='unit', unit=_unit(2, 1, 2)),
                     BenchSlot(kind='empty')],
        gold=5, capacity=3)
    rep = apply_board_rewrite(bs, STRATEGY_EFFECTS['人力重组'])
    bench = bs.bench.value
    assert bench.capacity == 3 and len(bench.slots) == 3 \
        and all(s.kind == 'empty' for s in bench.slots)
    assert bs.gold.value == 5 + sell_refund(1, 3) + sell_refund(1, 2)
    assert rep.sold_units == 2


# ============================================================ 边界(禁造帧/禁翻标/禁猜)


def test_sell_all_partial_read_withholds_refund() -> None:
    """部分读回归锁(出售域全读判据):front_row/back_row/bench 任一从未
    观察 = 退款公式输入不完整(未读域实际卖数未知)→ 不满足归属判据
    确定性分支「确定性公式+已知输入」前提(effect-domain.md §6.3)→
    退款零写入,金字段保持观察来源——禁把部分退款以 logic 标写成权威值
    (观察帧覆盖前记录层留错误金);已读子域清空照常落,已读面退款在
    报告 refund_gold × partial_read 留证等观察收口。"""
    # 子域 A:bench 从未观察(接管局/观察缺口典型)——已读前排+后排照常清空
    bs = _make_bs(front=[_unit(1, 1, 1), _unit(4, 2, 2)],
                  back=[_unit(2, 2, 1)], bench_slots=None, gold=20)
    seq0 = bs.write_seq
    rep = apply_board_rewrite(bs, STRATEGY_EFFECTS['人力重组'])
    read_face_refund = (sell_refund(1, 1) + sell_refund(2, 4)
                        + sell_refund(2, 2))
    assert bs.write_seq == seq0 + 2, '只清空已读两行,金零写入'
    assert bs.front_row.value == [] and bs.back_row.value == []
    assert bs.bench.value is None, '未读子域不造帧'
    assert bs.gold.value == 20 and bs.gold.source == 'observation', \
        '部分退款禁翻标金字段(禁留错误权威值)'
    assert rep.partial_read is True and rep.refund_gold == read_face_refund \
        and rep.sold_units == 3, '已读面退款留证在报告(标记部分读)'
    assert rep.cleared_fields == ('front_row', 'back_row')
    # 子域 B:front 从未观察——判据对三个子域对称,同门拒金写
    bs2 = _make_bs(front=None, back=[_unit(2, 2, 1)],
                   bench_slots=[BenchSlot(kind='unit', unit=_unit(1, 1, 1))]
                   + [BenchSlot(kind='empty')] * 8, gold=7)
    seq1 = bs2.write_seq
    rep2 = apply_board_rewrite(bs2, STRATEGY_EFFECTS['人力重组'])
    assert bs2.write_seq == seq1 + 2, '后排+备战席清空,金零写入'
    assert bs2.gold.value == 7 and bs2.gold.source == 'observation'
    assert rep2.partial_read is True \
        and rep2.refund_gold == sell_refund(2, 2) + sell_refund(1, 1) \
        and rep2.sold_units == 2


def test_sell_all_skips_never_observed_fields() -> None:
    """从未观察字段(value=None)= 无容器可写,跳过(同族先例 =
    project_effect_capacity):不造空阵帧,真值由下一备战帧观察到达;
    出售域全未读 → 退款 0 → 金不写(禁把观察金翻标成 logic),报告
    partial_read=True 标记出售域未全读。"""
    bs = _make_bs(front=None, back=None, bench_slots=None, gold=20)
    seq0 = bs.write_seq
    rep = apply_board_rewrite(bs, STRATEGY_EFFECTS['人力重组'])
    assert bs.write_seq == seq0, '全未读 = 零写入(不造帧)'
    assert bs.front_row.value is None and bs.back_row.value is None \
        and bs.bench.value is None
    assert bs.gold.value == 20 and bs.gold.source == 'observation', \
        '零退款禁翻标金字段来源'
    assert rep == BoardRewriteReport(rewrite=BOARD_REWRITE_SELL_ALL,
                                     refund_gold=0, sold_units=0,
                                     partial_read=True)


def test_sell_all_gold_unread_keeps_none() -> None:
    """gold 未读(None)= 无累加基座,金跳过(禁把退款当余额);出售清空
    照常落(清空事实独立于金可读性),退款额在报告留证。"""
    bs = _populated_bs(gold=None)
    rep = apply_board_rewrite(bs, STRATEGY_EFFECTS['人力重组'])
    assert bs.gold.value is None, '金未读保持 None(§3.2.9 None=不可读)'
    assert bs.front_row.value == [] and bs.bench.value is not None
    assert rep.refund_gold > 0 and 'gold' not in rep.cleared_fields
    assert rep.partial_read is False, \
        '出售域全读;金跳过是基座缺位而非部分读'


def test_noop_for_non_rewrite_entry_and_unknown_semantics() -> None:
    """非板面重写条目(payload 无 board_rewrite)→ None 零动作;未知语义值
    → 保守 no-op + 留证(禁猜——新语义入册须同步扩桥分支,注册表声明了
    语义而写端静默丢 = 本锁红)。"""
    bs = _populated_bs()
    seq0 = bs.write_seq
    assert apply_board_rewrite(bs, STRATEGY_EFFECTS['淘金客']) is None, \
        '非重写条目零动作'
    stub = SimpleNamespace(
        payload=SimpleNamespace(board_rewrite='future_semantics'),
        name='未知语义桩')
    assert apply_board_rewrite(bs, stub) is None, '未知语义保守 no-op(禁猜)'
    assert bs.write_seq == seq0, '两种 no-op 均零写入'
