"""买牌期望态对账网(期望态层·买牌通道;语义唯一源 =
docs/game/currency_war/research/merge_mechanics.md §1 买牌落点 / §2 连锁合成 /
§2.5 满栏例外与自动多买 / §3 恒成立约束;拖动通道先例 =
test_cw_w530_drag_reconcile.py 同族设计)。

测四类:①期望态计算真值表(普通买/触发合成-备战最左/场上吸收/两级连锁/
满栏自动多买 k>1/满栏连升低置信子案按暂定语义锁/身份未识别不评)②定型帧
对账判据真值表(身份未识别槽跳过;期望空槽被占=不一致;星级不符=不一致)
③接线源码锁(意图在 shop.py 买入点记录、期望在单元尾计算暂存、对账在
CwScreenPrep heavy 定型帧后仅 progressed 分支、合成落点单一源 =
cw_state._merge_bench)④台账行形态锁(surface='bench'/kind=
'buy_expect_mismatch'/reader_source='buy_expect_reconcile')。
全部纯函数/tmp_path,零触网零落盘真实路径。


出处:被其他测试文件引用(防断链保留,需后续人工归并)(2026-08-31 测试瘦身批考证补记)。"""
import json
from pathlib import Path

import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.telemetry import defects, recorder

from sr_od.application.currency_war.kernel.cw_prep_expect import BuyPurchase, compare_buy_expect, compute_buy_expect

from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import _save_buy_evidence
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def _bc(slot: int, char_id: str, star: int = 1,
        pref: str = 'back') -> BenchChar:
    return BenchChar(slot=slot, char_id=char_id, star=star, position_pref=pref)


def _bench(*chars: BenchChar) -> list[BenchChar | None]:
    """紧凑序列 → 9 槽表(测试构造辅助;chars 的 slot 为 1-based 物理槽位)。"""
    table: list[BenchChar | None] = [None] * 9
    for c in chars:
        table[c.slot - 1] = c
    return table


# ===== ① 期望态计算真值表(购买意图 → 期望态)=====

def test_expect_plain_buy_appends_bench():
    """普通买(§1 正常情况):期望 = 备战栏追加一张,不触发合成。"""
    exp = compute_buy_expect(
        [BuyPurchase(name='景元', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿')), [])
    assert exp is not None
    assert exp.bench_after[0].char_id == '希儿'
    assert exp.bench_after[1].char_id == '景元' and exp.bench_after[1].star == 1
    assert exp.changed_bench == [2]
    assert exp.changed_deployed == []
    assert exp.total_cost == 3 and not exp.low_confidence


def test_expect_merge_lands_bench_leftmost():
    """触发合成·三张全备战(§1 优先级 2):产物落在最左那张位置,其余腾槽。"""
    exp = compute_buy_expect(
        [BuyPurchase(name='希儿', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿'), _bc(4, '希儿')), [])
    assert exp is not None
    assert exp.bench_after[0] is not None and exp.bench_after[0].star == 2
    assert exp.bench_after[3] is None
    assert sorted(exp.changed_bench) == [1, 4]


def test_expect_merge_absorbs_deployed():
    """触发合成·场上有同名(§1 优先级 1):场上吸收,产物留在场上位置。"""
    dep = [_bc(1, '希儿', pref='front')] + [None] * 9
    exp = compute_buy_expect(
        [BuyPurchase(name='希儿', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿')), dep)
    assert exp is not None
    # 场上那张升 2★(deployed 下标 0 = 前排槽 1);备战那张腾槽
    assert exp.deployed_after[0] is not None and exp.deployed_after[0].star == 2
    assert exp.bench_after[0] is None
    assert sorted(exp.changed_bench) == [1]   # 买的槽 2 合并后回到空,无净变化
    assert exp.changed_deployed == [0]


def test_expect_chain_two_levels():
    """连锁合成(§2):备战 2×1星 + 备战 1×2星 + 场上 1×2星,买 1×1星
    → 1★ 合成 2★(落备战最左)→ 与两份 2★ 连锁 → 3★ 落场上位置。"""
    dep = [_bc(1, '希儿', 2, 'front')] + [None] * 9
    exp = compute_buy_expect(
        [BuyPurchase(name='希儿', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿'), _bc(2, '希儿'), _bc(3, '希儿', 2)), dep)
    assert exp is not None
    assert exp.deployed_after[0].star == 3          # 场上吸收到 3★
    assert all(exp.bench_after[i] is None for i in range(3))
    assert sorted(exp.changed_bench) == [1, 2, 3]
    assert exp.changed_deployed == [0]


def test_expect_bench_full_multi_buy():
    """满栏自动多买(§2.5,k=min(店内张数,3−已有数 mod 3) 由调用方算好
    传入;此处锁纯函数侧 k 张逐张入表+合并腾槽):备战栏满 9 槽含 1×希儿,
    买 count=2 → 合成后原位 2★,散牌不留(本例 k 恰好凑满)。"""
    full = _bench(_bc(1, '希儿'), *[_bc(i + 2, f'其他{i}') for i in range(8)])
    exp = compute_buy_expect(
        [BuyPurchase(name='希儿', star=1, count=2, unit_cost=3)],
        full, [])
    assert exp is not None
    assert exp.bench_after[0] is not None and exp.bench_after[0].star == 2
    assert exp.low_confidence is True               # k>1 = §2.5 低置信子案
    assert exp.total_cost == 6                      # 无折扣:k×单价


def test_expect_bench_full_chain_low_confidence():
    """满栏连升(§2.5【置信:低】,按说法实现锁暂定语义):备战满含 2×2星,
    买 3×1星(count=3)→ 1★ 合成 2★ → 与备战 2★ 连锁 → 3★ 落备战。"""
    full = _bench(_bc(1, '希儿', 2), _bc(2, '希儿', 2),
                  *[_bc(i + 3, f'其他{i}') for i in range(7)])
    exp = compute_buy_expect(
        [BuyPurchase(name='希儿', star=1, count=3, unit_cost=1)],
        full, [])
    assert exp is not None
    stars = [(c.char_id, c.star) for c in exp.bench_after[:2] if c is not None]
    assert stars == [('希儿', 3)]                   # 左侧 2★ 作载体升 3★
    assert exp.low_confidence is True
    assert exp.total_cost == 3


def test_expect_unidentified_purchase_is_none():
    """身份未识别(OCR 空名)→ 期望不可建返 None(宁缺勿造)。"""
    assert compute_buy_expect(
        [BuyPurchase(name='', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿')), []) is None


# ===== ①b 证据裁片随期望态携带 =====

def test_expect_carries_crops():
    """带裁片的意图 → crops 随期望态携带(像素级「买了什么」证据源);
    无裁片 → crops=None(证据通道缺省不占内存)。"""
    exp = compute_buy_expect(
        [BuyPurchase(name='景元', star=1, count=1, unit_cost=3, crop='IMG1'),
         BuyPurchase(name='希儿', star=1, count=1, unit_cost=2, crop='IMG2')],
        _bench(), [])
    assert exp is not None
    assert exp.crops == [('景元', 'IMG1'), ('希儿', 'IMG2')]
    exp2 = compute_buy_expect(
        [BuyPurchase(name='景元', star=1, count=1, unit_cost=3)],
        _bench(), [])
    assert exp2 is not None and exp2.crops is None


def test_save_buy_evidence_writes_crops_and_settle(tmp_path: Path):
    """不一致留证:买前裁片 + 定型帧不一致备战槽裁片都落盘;无裁片只落
    定型帧裁片;全 best-effort(坏裁片跳过不抛)。"""
    exp = compute_buy_expect(
        [BuyPurchase(name='景元', star=1, count=1, unit_cost=3,
                     crop=np.zeros((4, 4, 3), dtype=np.uint8))],
        _bench(_bc(1, '希儿')), [])
    mism = [{'domain': 'bench', 'slot': '2', 'expected': '景元/1星',
             'observed': '花火/1星'}]
    frame = np.zeros((30, 30, 3), dtype=np.uint8)
    slots = [(2, Rect(5, 5, 15, 15))]
    paths = _save_buy_evidence(str(tmp_path), 'p1-r1', exp, mism,
                               frame, slots)
    assert len(paths) == 2 and all(Path(p).exists() for p in paths)
    assert any('buy_景元' in p for p in paths)
    assert any('settle_bench2' in p for p in paths)
    # 无裁片:只落定型帧裁片;坏裁片对象:best-effort 跳过不抛
    exp2 = compute_buy_expect(
        [BuyPurchase(name='景元', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿')), [])
    paths2 = _save_buy_evidence(str(tmp_path), 'p1-r2', exp2, mism,
                                frame, slots)
    assert len(paths2) == 1
    assert _save_buy_evidence(str(tmp_path), 'p1-r3', exp, [], frame, slots) != []


# ===== ② 定型帧对账判据真值表 =====

def test_compare_buy_expect_truth_table():
    """判据:增量槽身份+星级全符=一致;身份/星级不符或期望空槽被占=不一致;
    实读无条目(未识别)=不评跳过。"""
    exp = compute_buy_expect(
        [BuyPurchase(name='景元', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿')), [])
    # 一致:槽 2 出现景元 1★
    assert compare_buy_expect(exp, [_bc(1, '希儿'), _bc(2, '景元')], []) == []
    # 身份不符
    m = compare_buy_expect(exp, [_bc(1, '希儿'), _bc(2, '花火')], [])
    assert len(m) == 1 and m[0]['domain'] == 'bench' and m[0]['slot'] == '2'
    # 星级不符(合成预判错/2★直出漏识别的证据形态)
    m2 = compare_buy_expect(exp, [_bc(1, '希儿'), _bc(2, '景元', 2)], [])
    assert len(m2) == 1
    # 未识别槽不评
    assert compare_buy_expect(exp, [], []) == []


def test_compare_expected_empty_slot_occupied():
    """期望腾槽(合成消耗)而实读仍占 = 不一致(合成未发生证据形态)。"""
    exp = compute_buy_expect(
        [BuyPurchase(name='希儿', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿'), _bc(4, '希儿')), [])
    # 一致:槽 4 已腾空(实读无该槽条目)
    got = [exp.bench_after[0]]
    assert compare_buy_expect(exp, got, []) == []
    # 不一致:槽 4 仍是希儿(合成未发生)
    m = compare_buy_expect(exp, [exp.bench_after[0], _bc(4, '希儿')], [])
    assert any(x['slot'] == '4' and '空' in x['expected'] for x in m)


def test_compare_deployed_landing():
    """场上吸收落点对账:deployed 增量槽按(排,排内槽)比对。"""
    dep = [_bc(1, '希儿', pref='front')] + [None] * 9
    exp = compute_buy_expect(
        [BuyPurchase(name='希儿', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿')), dep)
    assert exp.changed_deployed == [0]
    read = [_bc(1, '希儿', 2, 'front')]
    assert compare_buy_expect(exp, [], read) == []
    bad = [_bc(1, '希儿', 1, 'front')]
    m = compare_buy_expect(exp, [], bad)
    assert len(m) == 1 and m[0]['domain'] == 'deployed.front'


def test_compare_snapshot_stale_landing_downgraded():
    """真实空槽优先降级(DD-005;安灯 p2r2 停线同形态回归,局1):购买前
    tracked 快照缺某槽占用(模型:槽1-8 占、槽9 空)→ 期望把新牌落槽9;
    实读槽9=快照缺读的旧牌、新牌在槽1-8 的真实空槽 → 期望实体在别处
    出现 = 快照空槽表过期 → 降级不评,不再误判不一致。"""
    # 模型视角:槽1-8 占用、槽9 空(快照缺「那刻夏@9」的形态)
    pre = _bench(*[_bc(i, f'旧牌{i}') for i in range(1, 9)])
    exp = compute_buy_expect(
        [BuyPurchase(name='卡芙卡', star=1, count=1, unit_cost=2)],
        pre, [])
    assert exp.changed_bench == [9]              # 模型落点 = 槽9(首空槽)
    # 定型帧实读:槽9=那刻夏(真实被占)、卡芙卡在槽5(真实空槽)
    read = [_bc(i, f'旧牌{i}') for i in range(1, 9)]
    read[4] = _bc(5, '卡芙卡')
    read.append(_bc(9, '那刻夏'))
    assert compare_buy_expect(exp, read, []) == []
    # 对照:新牌全场缺席(真丢失)不降级,不一致照落(真阳性保留)
    read_lost = [_bc(i, f'旧牌{i}') for i in range(1, 9)]
    read_lost.append(_bc(9, '那刻夏'))
    m = compare_buy_expect(exp, read_lost, [])
    assert len(m) == 1 and m[0]['slot'] == '9' and '卡芙卡' in m[0]['expected']


def test_compare_merge_not_happened_not_downgraded():
    """降级不吞「合成腾槽未发生」证据:期望空槽实读=同名 1★(原始购买名,
    非终态新实体)→ 不降级,照旧落不一致(DD-005 边界②的锁)。"""
    exp = compute_buy_expect(
        [BuyPurchase(name='希儿', star=1, count=1, unit_cost=3)],
        _bench(_bc(1, '希儿'), _bc(4, '希儿')), [])
    # slot1 终态实体 = 希儿/2★;slot4 期望空,实读仍是希儿/1(非终态实体)
    m = compare_buy_expect(exp, [exp.bench_after[0], _bc(4, '希儿')], [])
    assert any(x['slot'] == '4' and '空' in x['expected'] for x in m)


# ===== ③ 接线守卫余量(2026-09-03 瘦身批收敛)=====

def test_w536_single_source_and_tombstone():
    """原 test_w536_wiring_locks 的形状锁群(index 序位/缩进字面/chr(39)
    注解字面/crop 链字面)按纪律 8 删除,保留两角:
    ①墓碑——cw_strategy 不得残留 pending_buy_expect 旧字段声明(期 0b 已迁
    kernel/cw_strategy_session;否定式+退役背书=合法墓碑,动态属性回流防线);
    ②依赖方向——compute_buy_expect 落点必须委托 cw_merge_bench 单一源,
    不自造第二套落点规则。对账时序/消费即清的行为面由 ①② 行为测辖定。"""
    strat_src = Path(
        'src/sr_od/application/currency_war/decision/cw_strategy.py'
    ).read_text(encoding='utf-8')
    assert 'pending_buy_expect: BuyExpect | None = None' not in strat_src, (
        '期 0b 锁改判:字段声明已迁 kernel/cw_strategy_session,'
        'cw_strategy 不得残留旧声明(动态属性回流防线)')
    expect_src = Path(
        'src/sr_od/application/currency_war/kernel/cw_prep_expect.py'
    ).read_text(encoding='utf-8')
    compute_body = expect_src[expect_src.index('def compute_buy_expect'):]
    compute_body = compute_body[:compute_body.index('\n\ndef ') + 1] \
        if '\n\ndef ' in compute_body else compute_body
    assert 'cw_merge_bench(' in compute_body       # 落点单一源委托


# ===== ④ 台账行形态锁 =====

def test_buy_defect_row_shape(tmp_path: Path, monkeypatch):
    """不一致行落 defect_ledger:surface='bench'/kind='buy_expect_mismatch'/
    reader_source='buy_expect_reconcile' 形态;分级语义由既有分级锁覆盖。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True,
                                                       replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    defects.record_defect(
        'bench', 'buy_expect_mismatch',
        expected='buy 景元/1星×1@3 总价3',
        observed='bench槽2 期望[景元/1星] 实读[花火/1星]',
        plane=1, round_num=3, gap_large=True,
        reader_source='buy_expect_reconcile')
    rows = [ln for ln in
            (tmp_path / 'defect_ledger.jsonl').read_text(encoding='utf-8')
            .splitlines() if ln.strip()]
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row['surface'] == 'bench'
    assert row['kind'] == 'buy_expect_mismatch'
    assert row['reader_source'] == 'buy_expect_reconcile'


from sr_od.application.currency_war.telemetry import state
