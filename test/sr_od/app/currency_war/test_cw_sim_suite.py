"""test_cw_sim_suite 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- sim: test_cw_sim.py
- sim_checks_streak_income: test_cw_sim_checks_streak_income.py
- sim_ledger_checks: test_cw_sim_ledger_checks.py
- sim_levelcap_guard: test_cw_sim_levelcap_guard.py
- sim_obs_keys: test_cw_sim_obs_keys.py
- sim_segment_checks: test_cw_sim_segment_checks.py
- sim_wiring_doc: test_cw_sim_wiring_doc.py
- shop_odds: test_cw_shop_odds.py
- platt_calibration: test_cw_platt_calibration.py
- weight_search: test_cw_weight_search.py
合并期「后来者加来源前缀」的临时别名已统一回素名:pytest / Path /
math / simulate_p1 / simulate_p1_batch 全文件唯一绑定;sim.checks
下三模块正名绑定(ledger / runner→checks_runner / segments)与
sim.runner(仅在退休根红测内以 ledger_runner 显式指认)不混。
(瘦身批 F11 归位成员:test_sim_ledger_core_count_semantics ← test_cw_data_registry.py,
落 sim_ledger_checks 节。)
"""
from __future__ import annotations

# ==================== sim ====================
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import POOL_COPIES_PER_CARD
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.sim.pool import _Pool
from sr_od.application.currency_war.sim.runner import simulate_p1_batch


def test_seed_reproducible() -> None:
    """同 seed 同局(结果全字段一致)。"""
    a = simulate_p1(42, pool='fallback')
    b = simulate_p1(42, pool='fallback')
    assert a.final_hp == b.final_hp
    assert a.hp_trail == b.hp_trail
    assert a.dir_round == b.dir_round


def test_pool_conservation() -> None:
    """有限牌池守恒:draw 不减池(买了才减),take/ret 互逆。"""
    import random
    rng = random.Random(7)
    p = _Pool(rng)
    total0 = sum(p.copies.values())
    p.draw_shop(5)                       # 抽店不减池(商店只是展示)
    assert sum(p.copies.values()) == total0
    name = next(iter(p.copies))
    p.take(name)
    assert sum(p.copies.values()) == total0 - 1
    p.ret(name)
    assert sum(p.copies.values()) == total0
    assert p.copies[name] <= POOL_COPIES_PER_CARD[CHARACTERS[name].cost]


def test_pool_cap_respected() -> None:
    """ret 不超过基础副本数(卖出回池有上限)。"""
    import random
    rng = random.Random(7)
    p = _Pool(rng)
    name = next(iter(p.copies))
    cap = POOL_COPIES_PER_CARD[CHARACTERS[name].cost]
    for _ in range(cap + 5):
        p.ret(name)
    assert p.copies[name] == cap


def test_direction_matches_strategy_claim() -> None:
    """认领必以方向建立为前提:结果带认领线(locked_line)时方向轮
    dir_round 必已落地(<99);方向未建立时不得凭空认领(模拟本身
    不另立判据,与策略认领同源)。"""
    r = simulate_p1(3, pool='fallback')
    assert r.dir_round < 99 or r.locked_line is None


def test_ab_channel_refresh() -> None:
    """use_refresh=False 时刷新数为 0(A/B 通道工作)。"""
    on = simulate_p1(11, pool='fallback', use_refresh=True)
    off = simulate_p1(11, pool='fallback', use_refresh=False)
    assert off.refreshes == 0
    assert on.refreshes > 0   # 通道真发射(seed 11 固定=确定性,实测 34 次;原断言 >=0 对被测对象零判别力)


def test_batch_stats_shape() -> None:
    """批量统计口径齐全(HP≥60/方向分布/平均)。

    n=5 够锁形状(2026-09-03 合并战役降 n;断言全是范围/回显检查,与 n
    无关;更大的种子扫面归 sim A/B 批日常工作流,不靠这条测试);
    ledger=False 不落盘(测试纪律:不写真实 .debug/ 路径,账本落盘路径
    由 test_cw_sim_cli_smoke 的 tmp_path 覆盖)。
    """
    s = simulate_p1_batch(5, pool='fallback', ledger=False)
    assert s['n'] == 5
    assert 0.0 <= s['hp_ge_60'] <= 1.0
    assert 0.0 <= s['dir_by_r4'] <= 1.0
    assert 0 <= s['avg_final_hp'] <= 100


def test_node_sequence_shape() -> None:
    """节点序列(r284 固定骨架):首二 reward,slot2-3 battle,
    slot4 supply,slot5-6 变异位,末 boss(遥测 14 帧实证)。"""
    import random

    from sr_od.application.currency_war.kernel.cw_battle_calib import (
        sample_node_sequence,
    )
    for seed in (1, 2, 3):
        seq = sample_node_sequence(random.Random(seed))
        assert len(seq) == 9
        assert seq[0] == 'reward' and seq[1] == 'reward'
        assert seq[2] == 'battle' and seq[3] == 'battle'
        assert seq[4] == 'supply'
        assert seq[5] in ('battle', 'encounter')
        assert seq[-1] == 'boss'


def test_reward_node_no_damage() -> None:
    """奖励/补给节点零战力要求 → 不掉血(r260 分层)。"""
    import random

    from sr_od.application.currency_war.kernel.cw_battle_calib import node_delta
    rng = random.Random(7)
    for node in ('reward', 'supply'):
        for rn in (3, 5, 8):
            d = node_delta(node, rn, 99, rng)
            assert d > 0, f'{node} r{rn} 不应掉血,得 {d}'


def test_encounter_harder_than_battle() -> None:
    """遭遇轮结算强度 > 同期普通战斗(用户口述:遭遇可比 boss 难)。"""
    import random

    from sr_od.application.currency_war.kernel.cw_battle_calib import node_delta
    losses_enc, losses_bat = [], []
    for seed in range(50):
        rng = random.Random(seed)
        losses_enc.append(node_delta('encounter', 6, 99, rng))
        losses_bat.append(node_delta('battle', 6, 99, rng))
    avg_enc = -sum(losses_enc) / len(losses_enc)
    avg_bat = -sum(losses_bat) / len(losses_bat)
    assert avg_enc > avg_bat, \
        f'遭遇均值损 {avg_enc} 应大于战斗 {avg_bat}'


# ==================== sim_checks_streak_income ====================

from typing import Any

from sr_od.application.currency_war.kernel import cw_economy
from sr_od.application.currency_war.sim.checks import runtime as chk


def _row(rn: int, node: str, streak: int, delta: int = 0,
         base: int = 5, interest: int = 0) -> dict:
    """最小合成账本行(生产形状子集:cw_sim 收入段必带 node/income)。"""
    return {'round_num': rn,
            'sim': {'node': node, 'delta': delta,
                    'income': {'base': base, 'interest': interest,
                               'streak': streak}}}


def _good_ledger() -> list[list[dict]]:
    """好样本:胜轮按表 + 败轮金路径 + 奖励轮照发 + 补给轮零,全链零违规。

    r1 胜(进轮 streak=0→表 1);r2 败(上一轮非败态,进轮 streak=1→表 1);
    r3 败(上一轮 r2 败→LOSS_GOLD battle=2);r4 奖励(照发,进轮
    streak=0→1);r5 补给(恒 0)。
    """
    return [[_row(1, 'battle', streak=1, delta=1),
             _row(2, 'battle', streak=1, delta=-5),
             _row(3, 'battle', streak=2, delta=-3),
             _row(4, 'reward', streak=1),
             _row(5, 'supply', streak=0, base=5, interest=2)]]


# --- 1. 合成正例(双向) -------------------------------------------------

def test_income_caliber_bidirectional() -> None:
    # 坏:奖励轮多发(表值 1 账本 3)/补给轮带 streak → 必报
    bad = [[_row(1, 'reward', streak=3)],
           [_row(1, 'supply', streak=1)]]
    r = chk.check_streak_combat_only_income(bad)
    assert r['violations'] == 2, '奖励/补给轮收入断言失明'
    assert r['missing_key_rows'] == 0
    # 坏:败轮金路径断(上一轮败应发 2,账本仍发表值 1)→ 必报
    bad_loss = [[_row(1, 'battle', streak=1, delta=-5),
                 _row(2, 'battle', streak=1, delta=-3)]]
    r_loss = chk.check_streak_combat_only_income(bad_loss)
    assert r_loss['violations'] == 1, '败轮金路径断言失明'
    # 坏:战斗轮少发(胜轮应发表值 1,账本 0)→ 必报(双向)
    bad_under = [[_row(1, 'battle', streak=0, delta=1)]]
    assert chk.check_streak_combat_only_income(
        bad_under)['violations'] == 1
    # 好:全链零违规,且账本口径与精确重算对拍 delta=0
    r2 = chk.check_streak_combat_only_income(_good_ledger())
    assert r2['violations'] == 0, f'好样本误报: {r2}'
    assert r2['missing_key_rows'] == 0
    assert r2['delta'] == 0
    assert r2['loss_gold_rows'] == 1   # r3 一轮命中败轮金路径
    assert r2['supply_rows'] == 1
    assert r2['supply_issued_extra'] == 7   # 补给多发残差披露(base+利息)
    assert r2['combat_only_streak_income'] == 5   # 1+1+2+1+0


# --- 2. 键名演化变异(缺键守卫) ---------------------------------------

def test_missing_node_key_counts_as_violation() -> None:
    """模拟未来 schema 演化(node→node_type):缺键必须涌现违规。

    旧实现此处 violations==0(静默失明)——正是本锁要修的点。
    """
    evolved = [{'round_num': 1,
                'sim': {'node_type': 'reward', 'delta': 0,
                        'income': {'base': 5, 'streak': 3}}}]
    r = chk.check_streak_combat_only_income([evolved])
    assert r['violations'] >= 1, '缺 node 键静默绿=断言永久失明'
    assert r['missing_key_rows'] == 1
    # income 整段缺失同理
    no_income = [{'round_num': 1, 'sim': {'node': 'reward', 'delta': 0}}]
    r2 = chk.check_streak_combat_only_income([no_income])
    assert r2['violations'] >= 1 and r2['missing_key_rows'] == 1
    # income 在但 streak 键缺失(streak→streak_count 演化)同理
    renamed = [{'round_num': 1,
                'sim': {'node': 'reward', 'delta': 0,
                        'income': {'base': 5, 'streak_count': 3}}}]
    r3 = chk.check_streak_combat_only_income([renamed])
    assert r3['violations'] >= 1 and r3['missing_key_rows'] == 1


# --- 3. 去守卫变异推演(不必真改生产代码) -----------------------------

def _mutant_flat_table(ledgers: list[list[dict]]) -> dict:
    """退化变异:所有行一律按 streak_gold(进轮连胜)重算——
    丢掉「补给轮恒 0」与「败轮金路径」两个特殊分支。
    """
    from sr_od.application.currency_war.kernel.cw_economy import streak_gold
    violations = ledger_sum = recompute = 0
    for rows in ledgers:
        streaks = chk._combat_streak_by_round(rows)
        for row in rows:
            sim = row.get('sim') or {}
            inc_streak = (sim.get('income') or {}).get('streak', 0) or 0
            ledger_sum += inc_streak
            expect = streak_gold(streaks.get(row.get('round_num') or 0, 0))
            recompute += expect
            if inc_streak != expect:
                violations += 1
    return {'violations': violations, 'ledger_streak_income': ledger_sum,
            'combat_only_streak_income': recompute}


def test_mutation_flat_table_killed() -> None:
    """扁平表变异(丢补给零/丢败轮金)必须被本文件样本杀死。"""
    good = _good_ledger()
    real = chk.check_streak_combat_only_income(good)
    assert real['violations'] == 0
    mutant = _mutant_flat_table(good)
    # 杀死面①:补给轮——生产恒 0,扁平表按表算 1 → 变异误报
    # (r5 补给进轮 streak=0,表值 1 ≠ 账本 0)
    assert mutant['violations'] >= 1, '补给零断言杀不死扁平表变异'
    # 杀死面②:败轮金——生产发 LOSS_GOLD 2,扁平表按表算 1 → 变异误报
    bad_loss = [[_row(1, 'battle', streak=1, delta=-5),
                 _row(2, 'battle', streak=2, delta=-3)]]
    assert chk.check_streak_combat_only_income(bad_loss)['violations'] == 0
    assert _mutant_flat_table(bad_loss)['violations'] >= 1, \
        '败轮金路径杀不死扁平表变异'


def test_mutation_no_count_guard_killed(monkeypatch: Any) -> None:
    """重算链断(monkeypatch streak_gold 恒 0)→ 披露口径必须涌现差异。

    检查器函数体内 `from cw_economy import streak_gold` 每次调用现取
    → monkeypatch 源模块即生效。
    """
    good = _good_ledger()
    real = chk.check_streak_combat_only_income(good)
    assert real['combat_only_streak_income'] == 5, \
        '重算基线漂移(生产侧先红)'
    monkeypatch.setattr(cw_economy, 'streak_gold', lambda streak: 0)
    mutated = chk.check_streak_combat_only_income(good)
    assert mutated['combat_only_streak_income'] == 2, \
        'monkeypatch 未生效(只剩败轮金 2),推演无效'
    assert mutated['combat_only_streak_income'] != real[
        'combat_only_streak_income'], \
        '好样本杀不死「重算链断」变异=披露锁失效'




# ==================== sim_ledger_checks ====================

from pathlib import Path

import pytest

from sr_od.application.currency_war.sim.checks import ledger
from sr_od.application.currency_war.sim.checks import runner as checks_runner
from sr_od.application.currency_war.sim.runner import write_batch_ledger


def _sim_ledger_checks_row(round_num: int = 1, gold: int = 10, gold_before: int = 5,
         income: dict | None = None, spend: dict | None = None,
         actions: list | None = None, target_comp: str = '') -> dict:
    return {
        'ts': round_num, 'round_num': round_num, 'gold': gold,
        'target_comp': target_comp, 'actions': actions or [],
        'sim': {
            'gold_before': gold_before,
            'income': income or {'base': 5, 'interest': 0,
                                 'streak': 1, 'event': 0},
            'spend': spend or {'buys': {}, 'levelup': 0,
                               'refresh': 0, 'sell_income': 0},
        },
    }


def test_consistency_check_bidirectional() -> None:
    """守恒检查:坏账本报(金不守恒)/好账本过。"""
    bad = [_sim_ledger_checks_row(gold=99)]   # 5+6≠99
    assert ledger.check_ledger_consistency(bad), '坏账本未报警=静默失效'
    good = [_sim_ledger_checks_row(gold=11)]  # 5+6=11
    assert not ledger.check_ledger_consistency(good)
    # 卖回金计收入侧
    good2 = [_sim_ledger_checks_row(gold=13, spend={'buys': {'line': 2}, 'levelup': 0,
                                  'refresh': 0, 'sell_income': 4})]
    assert not ledger.check_ledger_consistency(good2)   # 5+6-2+4=13
    # 缺 gold_before → 报(字段契约)
    miss = [_sim_ledger_checks_row()]
    del miss[0]['sim']['gold_before']
    assert ledger.check_ledger_consistency(miss)


def test_coldstart_check_bidirectional() -> None:
    """局49 指纹(r371b 语义):开局轮 reason∈{pair,off} 必报;
    方向件/其它通道/非开局轮不报。

    ⚠ reason 空间=self-attack 修正:_want_label 的 pair 谓词分支
    返回 classify_buy **身份**——门失效的线外件 reason='pair'
    (同阵营)或 'off'(异阵营=局49 原始形态,翡翠/大丽花对空板
    A5 门)。只查 'pair' 会漏掉局49 原始形态。
    """
    # 坏:异阵营线外(reason=off)——局49 原始形态
    bad = [{'plane': 1, 'round_num': 1, 'target_comp': '',
            'actions': [{'__type__': 'BuyCard',
                         'card': {'name': '翡翠', 'cost': 1},
                         'reason': 'off', 'channel': 'off'}]}]
    v = ledger.check_coldstart_seed_squander(bad)
    assert v and '翡翠' in v[0]
    # 坏:局53 形态(系统 bench 带卡,同阵营线外)
    bad2 = [{'plane': 1, 'round_num': 2, 'target_comp': '',
             'actions': [{'__type__': 'BuyCard',
                          'card': {'name': '阿格莱雅', 'cost': 1},
                          'reason': 'pair', 'channel': 'pair'}]}]
    assert ledger.check_coldstart_seed_squander(bad2)
    # 好:pair 谓词放行的方向件(reason=身份=bridge_seed)
    good = [{'plane': 1, 'round_num': 1, 'target_comp': '',
             'actions': [{'__type__': 'BuyCard',
                          'card': {'name': '丹恒·饮月', 'cost': 1},
                          'reason': 'bridge_seed',
                          'channel': 'bridge_seed'}]}]
    assert not ledger.check_coldstart_seed_squander(good)
    # 好:其它通道(line/emergency)不辖于门
    other = [{'plane': 1, 'round_num': 1, 'target_comp': '',
              'actions': [{'__type__': 'BuyCard',
                           'card': {'name': '翡翠', 'cost': 1},
                           'reason': 'emergency', 'channel': 'off'}]}]
    assert not ledger.check_coldstart_seed_squander(other)
    # 好:非开局轮(r3+)pair 凑对恢复旧语义(r371b 回归点)
    late = [{'plane': 1, 'round_num': 3, 'target_comp': '',
             'actions': [{'__type__': 'BuyCard',
                          'card': {'name': '翡翠', 'cost': 1},
                          'reason': 'pair', 'channel': 'pair'}]}]
    assert not ledger.check_coldstart_seed_squander(late)
    # decision_v2 栈:reason 带 d2_ 前缀(+'_merge' 尾,arbiter
    # _materialize)——归一化后同指纹必报(防对新栈无声失效,
    # 2026-08-24 leader 核实观察局首验)
    d2bad = [{'plane': 1, 'round_num': 1, 'target_comp': '',
              'actions': [{'__type__': 'BuyCard',
                           'card': {'name': '翡翠', 'cost': 1},
                           'reason': 'd2_off', 'channel': 'off'}]}]
    v2 = ledger.check_coldstart_seed_squander(d2bad)
    assert v2 and '翡翠' in v2[0]
    d2bad2 = [{'plane': 1, 'round_num': 2, 'target_comp': '',
               'actions': [{'__type__': 'BuyCard',
                            'card': {'name': '阿格莱雅', 'cost': 1},
                            'reason': 'd2_pair_merge',
                            'channel': 'pair'}]}]
    assert ledger.check_coldstart_seed_squander(d2bad2)
    d2good = [{'plane': 1, 'round_num': 1, 'target_comp': '',
               'actions': [{'__type__': 'BuyCard',
                            'card': {'name': '丹恒·饮月', 'cost': 1},
                            'reason': 'd2_engine_seed',
                            'channel': 'engine_seed'}]}]
    assert not ledger.check_coldstart_seed_squander(d2good)


def test_coldstart_check_in_batch_set() -> None:
    """r371b 后局49 检查进批量集(sim 批次自动扫)。"""
    assert 'coldstart_direction' in checks_runner._BATCH_CHECKS


def test_run_checks_report_shape() -> None:
    """批量检查报告形:violations 计数 + 局索引(供 seed 重放)。"""
    ledgers = [[_sim_ledger_checks_row(gold=11)], [_sim_ledger_checks_row(gold=99)], [_sim_ledger_checks_row(gold=11)]]
    rep = checks_runner.run_checks_on_ledgers(ledgers)
    assert rep['ledger_consistency']['violations'] == 1
    assert rep['ledger_consistency']['games'] == [1]


def test_write_batch_ledger_guard() -> None:
    """写入器守卫:sim 账本禁写生产 live 流目录(自中毒防线)。

    禁写对象 = 生产流根(kernel/cw_observe.DEFAULT_REPLAY_DIR,单一源直调;
    曾硬抄旧路径字面量——根常量迁移即假绿,现随单一源走)。
    """
    from sr_od.application.currency_war.kernel.cw_observe import DEFAULT_REPLAY_DIR
    with pytest.raises(RuntimeError):
        write_batch_ledger([], DEFAULT_REPLAY_DIR)


def test_write_batch_ledger_guard_retired_roots(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """写入器守卫补充面:退役旧根(sim 批根/旧流根)同样禁写(红测)。

    出处 = 2026-09-07 22:20:52 空批以旧 replay 根为 out_dir 把历史三流
    整份截断的事故(ADR-0586「单一源与守卫」节载同一事故):
    旧守卫只锚当前生产根,根切换过渡窗口内旧根失保护。修法裁决 =
    守卫同时锁退役根字面量(kernel/cw_observe.RETIRED_* 单一源),
    不选「out_dir 限定 SIM_ROOT 子树」——A/B 对照等合法调用方写显式
    独立目录(docstring 契约「或显式独立目录」),子树限定会破契约。
    安全网 = 检测网,非复原网(2026-09-08 最近改动三审 M4 申报修正:
    原文「finally 复原/不得烧掉封存物」与实现不符——实现只有登记与
    事后断言,无任何备份-回写代码,故按实申报):被测对象是守卫不是
    清理,`_prune_sim_runs` 桩化 no-op;事前登记旧根流文件的存在/字节,
    守卫失守时 'w' 截断会真实发生,本测试的职责是让失守在事后断言处
    现形(红),不是阻止它。现旧根流已全部迁移(ADR-0586),失守的
    实际危害 = 旧根新建空文件污染,无封存物可烧。
    """
    from sr_od.application.currency_war.kernel.cw_observe import (  # noqa: I001  (函数内分组导入,保持 kernel/sim 两簇)
        RETIRED_SIM_ROOT,
        RETIRED_STREAMS_ROOT,
    )
    # 模块级 `runner` 名绑 sim.checks.runner,而清理函数在 sim.runner——
    # 两个同名生产模块,归属显式指认防桩错对象
    from sr_od.application.currency_war.sim import runner as ledger_runner  # noqa: I001

    monkeypatch.setattr(ledger_runner, '_prune_sim_runs', lambda: None)
    _stream_names = ('decisions.jsonl', 'outcomes.jsonl',
                     'shop_snapshots.jsonl', 'manifest.json')

    class _Restore:
        """out_dir 内受 'w' 威胁的文件:事前登记,事后断言未被写。"""

        def __init__(self, root: Path) -> None:
            self.root = root
            self.before: dict[str, bytes | None] = {
                n: (root / n).read_bytes() if (root / n).exists() else None
                for n in _stream_names}

        def verify(self) -> None:
            """守卫生效判据 = 所有受威胁文件未被创建/未被改动。"""
            for name, old in self.before.items():
                p = self.root / name
                now = p.read_bytes() if p.exists() else None
                assert now == old, f'守卫失守,{name} 被截断模式写(旧根)'

    for retired_root in (RETIRED_STREAMS_ROOT, RETIRED_SIM_ROOT):
        restore = _Restore(retired_root)
        try:
            with pytest.raises(RuntimeError):
                write_batch_ledger([], retired_root)
        finally:
            restore.verify()


def test_sim_ledger_core_count_semantics() -> None:
    """sim 账本 core_count 语义标记(core_routed;含 None 序列化)。

    (瘦身批 F11 自 test_cw_data_registry.py 归位本文件:机制=sim 账本契约,
    属 sim_ledger_checks 主题;断言零改动。)
    """
    import contextlib
    import io
    import json
    import tempfile

    with contextlib.redirect_stderr(io.StringIO()), tempfile.TemporaryDirectory() as td:
        rep = simulate_p1_batch(3, pool='snapshot',
                                ledger=Path(td) / 'sem')
        mf = json.loads((Path(rep['ledger_dir'])
                         / 'manifest.json').read_text(encoding='utf-8'))
        assert mf['ledger_semantics'] == 'core_routed'


def test_checks_module_does_not_import_sim() -> None:
    """依赖方向:checks 不 import cw_sim(二轮#7;调用方传账本)。

    r405 修订:原断言 `'from sr_od' not in src` 过宽——新检查
    (no_component_equipped_p1)合法 lazy-import cw_synthesis.
    RESERVED_COMPONENTS(叶子模块,单一源纪律;压测经济批规格),
    非循环依赖。锁收窄到本意:不 import cw_sim(AST 级判,免疫
    docstring 字样)。
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(checks_runner))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or '']
        else:
            continue
        for n in names:
            assert 'cw_sim' not in n, f'checks 不得 import cw_sim: {n}'




# ==================== sim_levelcap_guard ====================

class _LevelUpSpamStub:
    """升级桩:每段恒发 3 个 LevelUp——未满级时合法执行,满级后逼出守卫。"""

    def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.kernel.cw_state import LevelUp
        return [LevelUp(cost=4) for _ in range(3)]


def test_sim_levelup_cap_guard_rejects_and_discloses() -> None:
    """满级后 LevelUp 拒付:金不扣、无 LevelUp 执行行、计数披露。"""

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

    res = simulate_p1(1, pool='fallback', strategy=_LevelUpSpamStub())
    rows = res.ledger
    assert rows, '账本为空:运行异常'

    # 守卫确实介入:有轮记录了拒付计数
    rejected_total = sum((r.get('sim') or {}).get('level_cap_rejects', 0)
                         for r in rows)
    assert rejected_total > 0, '满级桩未逼出守卫:level_cap_rejects 全 0'

    # 满级判定:某轮末 state.level 已达上限 → 该轮**之后**的轮不再有
    # LevelUp 执行行(拒付行 LevelUpRejected 不算执行)。
    cap_seen = False
    for r in rows:
        if cap_seen:
            st = r.get('state') or {}
            assert st.get('level', 0) >= 9, '满级后等级回退:状态链坏'
            lv_rows = [a for a in (r.get('actions') or [])
                       if a.get('__type__') == 'LevelUp']
            assert not lv_rows, (
                f"r{r.get('round_num')} 满级后仍有 LevelUp 执行行:"
                f'{len(lv_rows)}(cap 守卫回归)')
            assert (r.get('sim') or {}).get('spend', {}).get('levelup', 0) == 0, \
                f"r{r.get('round_num')} 满级后仍扣升级金(白烧回归)"
            rej_rows = [a for a in (r.get('actions') or [])
                        if a.get('__type__') == 'LevelUpRejected']
            assert rej_rows, (
                f"r{r.get('round_num')} 满级拒付未记 LevelUpRejected 账本行"
                '(台账断链)')
        cap_seen = cap_seen or (r.get('state') or {}).get('level', 0) >= 9


def test_sim_levelup_pre_cap_regression() -> None:
    """回归:未满级时 LevelUp 行为不变——照常执行、照常扣 4 金/击。"""

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

    res = simulate_p1(1, pool='fallback', strategy=_LevelUpSpamStub())
    pre_cap = [r for r in res.ledger
               if (r.get('state') or {}).get('level', 0) < 9
               and (r.get('sim') or {}).get('spend', {}).get('levelup', 0) > 0]
    assert pre_cap, '未满级轮无升级执行:回归(合法升级被误拦)'
    for r in pre_cap:
        acts = r.get('actions') or []
        n_lv = sum(1 for a in acts if a.get('__type__') == 'LevelUp')
        spent = (r.get('sim') or {}).get('spend', {}).get('levelup', 0)
        assert spent == 4 * n_lv, (
            f"r{r.get('round_num')} 未满级支出 {spent} ≠ 4×{n_lv}(flat4 回归)")


def test_sim_levelup_rejected_rows_keep_flat4_ledger_lock() -> None:
    """拒付行不破坏 flat4 台账锁(spend.levelup == 4×LevelUp 行数)。"""

    from sr_od.application.currency_war.sim.checks.ledger import (
        check_levelup_flat4_ledger_lock,
    )
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

    res = simulate_p1(1, pool='fallback', strategy=_LevelUpSpamStub())
    violations = check_levelup_flat4_ledger_lock(res.ledger)
    assert not violations, f'flat4 台账锁被拒付行破坏:{violations[:3]}'


def test_sim_batch_cap_rejects_by_plane_consistent_with_total() -> None:
    """按 plane 分解披露:键值合法、与总量键和恒等、plane 单调可读。

    为什么按 plane:lv≥9 态在实机只见 P2/P3(实机 P1 等级上限 7),
    总量把 P1 等级虚高噪声与 P2/P3 语义分歧混桶,分解后才能为
    LEVEL_CAP 放开批提供干净读数。兼容判据:总量键保留不删,分解值
    求和必须等于总量——不等即聚合端分组与总量口径漂移。

    合并墓碑:原 test_sim_batch_aggregate_discloses_level_cap_rejects
    (同参批只断言 level_cap_rejects 键存在且 ≥0)退役并入本测试——
    键缺失在此 KeyError,负值被「分解和=总量」恒等排除(跨层合并战役)。
    """

    from sr_od.application.currency_war.sim.runner import simulate_p1_batch

    rep = simulate_p1_batch(6, pool='fallback', seed_base=600,
                            ledger=False, checks=False)
    by_plane = rep['level_cap_rejects_by_plane']
    assert isinstance(by_plane, dict)
    for plane, cnt in by_plane.items():
        assert plane in (1, 2, 3), f'非法 plane 键:{plane}'
        assert isinstance(cnt, int) and cnt > 0
    assert sum(by_plane.values()) == rep['level_cap_rejects'], (
        f"分解和 {sum(by_plane.values())} ≠ 总量 "
        f"{rep['level_cap_rejects']}(聚合口径漂移)")


# ==================== sim_obs_keys ====================

from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.sim.engine_p1 import _board_next_tier_of

_SEEDS = (0, 7, 42)


# ---------- 检查器 bidirectional(锁防锁) ----------

def _good_row() -> dict:
    return {
        'plane': 1, 'round_num': 3,
        'state': {'bench_full_flag': False, 'board_next_tier': {'仙舟': 3},
                  'refresh_probs': {2: 0.5, 3: 0.3}},
        'sim': {'alloc_frame': {'active': False, 'reason': 'out_of_scope'},
                'alloc_active_any': False},
    }


def test_observation_keys_check_bad_rows_report() -> None:
    """坏账本必报:缺键/类型错/域非法/自洽破,五形态各报一条。"""
    import copy
    base = _good_row()
    cases: list[tuple[str, dict]] = []
    r = copy.deepcopy(base)
    del r['state']['bench_full_flag']
    cases.append(('缺bench_full_flag', r))
    r = copy.deepcopy(base)
    r['state']['bench_full_flag'] = None
    cases.append(('flag为None', r))
    r = copy.deepcopy(base)
    r['state']['board_next_tier'] = {'仙舟': 99}
    cases.append(('下档越域', r))
    r = copy.deepcopy(base)
    r['sim']['alloc_frame'] = {'active': True, 'domain': '???'}
    cases.append(('分配域非法', r))
    r = copy.deepcopy(base)
    del r['sim']['alloc_frame']
    r['sim']['alloc_active_any'] = True
    cases.append(('OR聚合但帧位缺', r))
    r = copy.deepcopy(base)
    # (缺降格触发面 case 已随 p1_downgrade_active 账本位退役删除——统一迁移批 ②。)
    del r['state']['refresh_probs']
    cases.append(('缺轮岗概率条', r))
    for label, row in cases:
        v = ledger.check_observation_keys_live([row])
        assert v, f'{label}: 坏行未报=检查静默失效'
    # P2 行不辖(键族只承诺 P1 段)
    p2 = copy.deepcopy(base)
    p2['plane'] = 2
    assert not ledger.check_observation_keys_live([p2])


def test_observation_keys_check_good_row_passes() -> None:
    """好账本必过(防误报);active 帧位(接管态)同样过。"""
    assert not ledger.check_observation_keys_live([_good_row()])
    takeover = _good_row()
    takeover['sim']['alloc_frame'] = {
        'active': True, 'domain': 'death', 'reason': 'pipeline_spent',
        'gold': 30}
    takeover['sim']['alloc_active_any'] = True
    assert not ledger.check_observation_keys_live([takeover])


def test_observation_keys_check_registered() -> None:
    """哨兵入批检注册表(随批自动扫,不入=死检查)。"""
    assert 'observation_keys_live' in checks_runner._BATCH_CHECKS


# ---------- 引擎侧真实性(值语义 + 非恒值分布) ----------

@pytest.mark.parametrize('seed', _SEEDS)
def test_obs_keys_shape_on_real_game(seed: int) -> None:
    """真局每行 P1 账本:三键齐且形状合法;检查器对真局零违规。"""
    res = simulate_p1(seed, pool='fallback')
    p1 = [r for r in res.ledger if (r.get('plane') or 1) == 1]
    assert p1, 'P1 账本为空'
    for row in p1:
        st = row['state']
        assert isinstance(st['bench_full_flag'], bool)
        rp = st['refresh_probs']
        assert rp is None or isinstance(rp, dict)
        bnt = st['board_next_tier']
        assert isinstance(bnt, dict)
        for f, v in bnt.items():
            assert v in FACTIONS[f].tiers, f'{f} 下档 {v} 不在注册表 tier 表'
            assert v >= 2
        assert row['sim']['alloc_active_any'] is False or \
            row['sim']['alloc_frame'] is not None
    assert not ledger.check_observation_keys_live(p1)


def test_board_next_tier_helper_semantics() -> None:
    """单源推导式:取 >count 的最小 tier,无更高档不计(与生产 obs
    computed 支同一式)。阵营取注册表实键(不点名,防表键漂移)。"""
    fname = next(iter(FACTIONS))
    tiers = FACTIONS[fname].tiers
    mid = tiers[len(tiers) // 2]
    below = mid - 1
    assert _board_next_tier_of({fname: below}) == {fname: mid}
    # 已达最高档 → 不计(键省略)
    top = max(tiers)
    assert _board_next_tier_of({fname: top}) == {}
    # 注册表外阵营(理论上不出现)→ 安全省略
    assert _board_next_tier_of({'不存在阵营': 1}) == {}


def test_bench_full_flag_and_alloc_frame_not_degenerate() -> None:
    """观测键形状对偶门(统一迁移批 ② 锁语义重推):alloc 半部(帧位/
    接管域)已随 v2 分配器死链退役——engine 仍恒写键(None/False),
    恒值分布对账与 bench_full_flag 点亮面随 sim 重锚批重探(w614 同批);
    本锁现辖 = 真局行三键形状 + checker 零违规(batch 链路另有专测)。"""
    rows = [r for seed in (9, 11) for r in simulate_p1(
        seed, pool='fallback').ledger if (r.get('plane') or 1) == 1]
    assert len(rows) >= 2 * 5, '局数行数异常'
    for r in rows:
        assert isinstance(r['state']['bench_full_flag'], bool)
        af = r['sim']['alloc_frame']
        assert af is None or (isinstance(af, dict) and 'active' in af)
        assert isinstance(r['sim']['alloc_active_any'], bool)


def test_batch_check_reports_observation_keys_zero_violation() -> None:
    """批检链路闭合:observation_keys_live 随批自动扫且真批零违规。"""
    rep = simulate_p1_batch(5, pool='fallback', ledger=False, checks=True)
    ck = rep['checks_violations']['observation_keys_live']
    assert ck['violations'] == 0, f"games={ck.get('games')}"


def test_sess_active_env_disclosed() -> None:
    """投资环境名入账本(invest 注入写;空串=未注入机制性缺省)。"""
    from sr_od.application.currency_war.sim.cw_sim_invest import SimInvestProfile
    prof = SimInvestProfile(active_env='昼之半神概念股', picks=())
    r = simulate_p1(0, pool='fallback', invest=prof)
    assert r.ledger, '账本为空'
    assert all(row.get('sess_active_env') == '昼之半神概念股'
               for row in r.ledger)
    r_plain = simulate_p1(0, pool='fallback')
    assert all(row.get('sess_active_env') == ''
               for row in r_plain.ledger)


def test_write_batch_ledger_carries_new_keys() -> None:
    """落盘链闭合:新键经 write_batch_ledger 落 jsonl 后可读回(判读
    CLI 消费面;向后兼容——旧账本无新键不炸)。"""
    import json
    import tempfile
    from pathlib import Path

    from sr_od.application.currency_war.sim.runner import write_batch_ledger
    results = [simulate_p1(s, pool='fallback') for s in (0, 7)]
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        write_batch_ledger(results, out)
        manifest = json.loads((out / 'manifest.json').read_text('utf-8'))
        assert manifest['rounds_rows'] == sum(len(r.ledger) for r in results)
        lines = (out / 'decisions.jsonl').read_text('utf-8').splitlines()
        assert lines
        row = json.loads(lines[0])
        assert isinstance(row['state']['bench_full_flag'], bool)
        assert isinstance(row['state']['board_next_tier'], dict)
        assert 'alloc_frame' in row['sim']
        assert 'sess_active_env' in row


def test_write_batch_ledger_outcomes_boss_names_slot() -> None:
    """T-179 件②构造锁:outcomes 行带 boss_names 槽位(恒 None=未建模)。

    键名与生产 OutcomeRecord 同键同构;sim 未建模简报面 → 「未建模」
    显式缺省,须与旧数据「键缺失」可辨(消费端按键在/值 None 分型)。
    boss 伤害双峰按敌型混合重标定的实采数据源 = 生产 outcomes
    (单一源 = cw_registry.handoff_boss_e_damage 注)。
    """
    import json
    import tempfile

    result = simulate_p1(0, pool='fallback')
    with tempfile.TemporaryDirectory() as td:
        out = write_batch_ledger([result], Path(td))
        rows = [json.loads(line)
                for line in (out / 'outcomes.jsonl').open(encoding='utf-8')
                if line.strip()]
    assert rows, 'outcomes 流为空'
    assert all('boss_names' in row for row in rows), 'boss_names 槽位缺失'
    assert all(row['boss_names'] is None for row in rows)


# ==================== sim_segment_checks ====================

from sr_od.application.currency_war.sim.checks import segments
from sr_od.application.currency_war.sim.runner import (
    simulate_p1_batch as simulate_p1_batch,
)


def _sim_segment_checks_row(round_num: int = 1, *, plane: int = 1, gold: int = 30,
         node: str = 'battle', waves_gold: int | None = None,
         cards: list[dict] | None = None, actions: list | None = None,
         state: dict | None = None, formed_stop: bool = False,
         bench_full_skipped_buys: int = 0, hp: int = 60) -> dict:
    """合成账本行(形状对齐真 ledger;shop_waves 单波)。"""
    return {
        'plane': plane, 'round_num': round_num, 'gold': gold,
        'hp': hp, 'formed_stop': formed_stop,
        'state': state or {'board_factions': {}, 'deployed': [],
                           'bench': [], 'cap': 3, 'level': 4},
        'target_comp': '',
        'actions': actions or [],
        'sim': {'node': node,
                'income': {'base': 5, 'interest': 0, 'streak': 0,
                           'event': 1},
                'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                          'sell_income': 0},
                'bench_full_skipped_buys': bench_full_skipped_buys,
                'shop_waves': [{'event': 'offer',
                                'gold': gold if waves_gold is None
                                else waves_gold,
                                'cards': cards or []}]},
    }


def _buy(name: str = '甲', cost: int = 1, channel: str = 'engine') -> dict:
    return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': cost},
            'reason': f'd2_{channel}', 'channel': channel}


def _formed_state(level: int = 5) -> dict:
    """成型态 board_factions:仙舟3+列车2 = 两体系达成(engines≥2)。"""
    return {'board_factions': {'仙舟': 3, '列车同行': 2},
            'deployed': [{'char_id': '藿藿'}], 'bench': [],
            'cap': level, 'level': level}


# ---------------------------------------------------------------- [17]
def test_seg_overflow_idle_spend_bidirectional() -> None:
    """[17] 溢余即花:金>50 零花未成型必报;自洽停手/bench 满豁免。

    T-153 迁移(C5/ADR-0593)改锁重推:原第 4 断言「formed_stop 行 →
    豁免」钉的是自报短路旧语义——迁移后豁免 = 自算成型复核通过
    (engines≥2,即 formed 行那条断言,保留面不变);自报停手∧自算
    未成型 = 成型谎报,不豁免且事件带 ``suspect`` 标记。原断言按新
    语义改写为谎报显形断言,另补自洽停手(自报+自算双真)豁免照旧
    断言(兼容面)。
    """
    bad = [_sim_segment_checks_row(gold=55, waves_gold=55, node='battle')]
    evs = segments.seg_check_overflow_idle_spend(bad)
    assert evs and evs[0]['gold_before'] == 55
    # 有花费 → 过
    spent = [_sim_segment_checks_row(gold=48, waves_gold=55, actions=[_buy()])]
    assert not segments.seg_check_overflow_idle_spend(spent)
    # 成型(engines≥2)→ 攒息合法面
    formed = [_sim_segment_checks_row(gold=70, waves_gold=70, state=_formed_state())]
    assert not segments.seg_check_overflow_idle_spend(formed)
    # 自报停手 ∧ 自算未成型(engines=0) = 成型谎报 → 不豁免+suspect 标记
    # (T-153/ADR-0593:旧「自报即豁免」语义已退役——谎报恰是迁移要显形的形态)
    lie = [_sim_segment_checks_row(gold=70, waves_gold=70, formed_stop=True)]
    lie_evs = segments.seg_check_overflow_idle_spend(lie)
    assert lie_evs and lie_evs[0].get('suspect'), \
        '成型谎报未显形(C5 迁移回归)'
    # 自洽停手(自报停手 ∧ 自算成型)→ 豁免照旧(兼容面)
    honest = [_sim_segment_checks_row(gold=70, waves_gold=70,
                                      state=_formed_state(), formed_stop=True)]
    assert not segments.seg_check_overflow_idle_spend(honest)
    # bench 满守卫拦截轮 → 想买买不了,豁免
    guard = [_sim_segment_checks_row(gold=55, waves_gold=55, bench_full_skipped_buys=2)]
    assert not segments.seg_check_overflow_idle_spend(guard)
    # 息线邻近容忍带(ADR-0478):g0=51/52 浮动态不报;≥53 仍报
    near1 = [_sim_segment_checks_row(gold=51, waves_gold=51, node='battle')]
    near2 = [_sim_segment_checks_row(gold=52, waves_gold=52, node='battle')]
    assert not segments.seg_check_overflow_idle_spend(near1)
    assert not segments.seg_check_overflow_idle_spend(near2)
    evs_far = segments.seg_check_overflow_idle_spend(
        [_sim_segment_checks_row(gold=53, waves_gold=53, node='battle')])
    assert evs_far and evs_far[0]['gold_before'] == 53


# ------------------------------------------------- [17] P2 位面延伸
def test_seg_p2_bleed_gold_stack_bidirectional() -> None:
    """P2 血线下降段金堆积(ADR-0479):hp 掉∧金未泄∧溢余,≥2 连必报;
    血线稳定/金在泄/单轮/P1 段/容忍带内均不报。"""
    # 坏形态:局2/局3 型(P2 金逐轮堆积,hp 逐轮连败;首轮无上轮只
    # 立基,第 2 连轮起报)
    bad = [_sim_segment_checks_row(1, plane=2, gold=55, hp=50),
           _sim_segment_checks_row(2, plane=2, gold=65, hp=40),
           _sim_segment_checks_row(3, plane=2, gold=75, hp=25)]
    evs = segments.seg_check_p2_bleed_gold_stack(bad)
    assert evs and evs[0]['streak'] == 2 and evs[0]['round_num'] == 3
    # 血线稳定(胜局攒息合法面)→ 不报
    stable = [_sim_segment_checks_row(1, plane=2, gold=60, hp=50),
              _sim_segment_checks_row(2, plane=2, gold=70, hp=50)]
    assert not segments.seg_check_p2_bleed_gold_stack(stable)
    # 金在泄(买入盖过收入,溢余在消化)→ 不报
    draining = [_sim_segment_checks_row(1, plane=2, gold=70, hp=50),
                _sim_segment_checks_row(2, plane=2, gold=60, hp=35)]
    assert not segments.seg_check_p2_bleed_gold_stack(draining)
    # 单轮堆积即被非溢余轮打断(灰区)→ 不报
    single = [_sim_segment_checks_row(1, plane=2, gold=70, hp=50),
              _sim_segment_checks_row(2, plane=2, gold=75, hp=45),
              _sim_segment_checks_row(3, plane=2, gold=50, hp=40)]
    assert not segments.seg_check_p2_bleed_gold_stack(single)
    # P1 行不辖([17] P1 面归 seg_overflow_idle_spend)
    p1 = [_sim_segment_checks_row(1, plane=1, gold=60, hp=50),
          _sim_segment_checks_row(2, plane=1, gold=70, hp=35)]
    assert not segments.seg_check_p2_bleed_gold_stack(p1)
    # 息线邻近容忍带内(g≤52,ADR-0478 同带宽)→ 不报
    band = [_sim_segment_checks_row(1, plane=2, gold=50, hp=50),
            _sim_segment_checks_row(2, plane=2, gold=52, hp=35)]
    assert not segments.seg_check_p2_bleed_gold_stack(band)
    # 金不可读帧断链(不可信金不猜)
    broken = [_sim_segment_checks_row(1, plane=2, gold=60, hp=50),
              _sim_segment_checks_row(2, plane=2, gold=None, hp=35),
              _sim_segment_checks_row(3, plane=2, gold=70, hp=20)]
    assert not segments.seg_check_p2_bleed_gold_stack(broken)
    # 新检查已入段级表(sim 批顺路扫,回灌纪律①)
    assert 'seg_p2_bleed_gold_stack' in segments._SEGMENT_CHECKS


# ([11] 无损购买段检已随 press 带判据死链退役删除——统一迁移批 ② MAP B 类;
#  检查器 seg_check_lossless_buy_missed 与注册表条目同件删除。)

# ------------------------------------------------------------ [6]/[19]
def test_seg_break_interest_exception_bidirectional() -> None:
    """破息记账:无依据破息必报;例面(店全想要/连胜保/授权通道
    花费/boss 窗地板)放行;奖励帧 LevelUp 由授权通道口径豁免(ADR-0580)。"""
    # 违规:破息买 1 笔 off、无连胜、战斗节点
    bad = [_sim_segment_checks_row(gold=40, waves_gold=55, node='battle',
                actions=[_buy('杂件', channel='off')]),
           ]
    bad[0]['sim']['spend']['buys'] = {'d2_off': 15}
    evs = segments.seg_check_break_interest_exception(bad)
    assert evs and evs[0]['gold_before'] == 55 \
        and evs[0]['buys'][0]['channel'] == 'off' \
        and isinstance(evs[0]['final_shop_panel'], list)
    # 例外①店全想要(≥2 笔无一 off)
    store_all = [_sim_segment_checks_row(gold=40, waves_gold=55, node='battle',
                      actions=[_buy('引擎件'), _buy('凑对件', channel='pair')])]
    assert not segments.seg_check_break_interest_exception(store_all)
    # 例外②连胜保([19]):进轮重算连胜 ≥2(前两轮战斗胜 delta≥0)
    streak_rows = [
        _sim_segment_checks_row(1, gold=52, waves_gold=52, node='battle'),
        _sim_segment_checks_row(2, gold=54, waves_gold=54, node='battle'),
        _sim_segment_checks_row(3, gold=40, waves_gold=58, node='battle',
             actions=[_buy('保连件', channel='pair')]),
    ]
    assert not segments.seg_check_break_interest_exception(streak_rows)
    # 奖励帧 LevelUp 支出仍豁免(T-115 对齐:原节点型例外③已退役,
    # 豁免依据 = ④ levelup_spend 通道口径,ADR-0471/ADR-0580)
    reward_lv = [{**_sim_segment_checks_row(gold=45, waves_gold=52, node='reward'),
                  'actions': [{'__type__': 'LevelUp', 'cost': 4}]}]
    reward_lv[0]['sim']['spend']['levelup'] = 4
    assert not segments.seg_check_break_interest_exception(reward_lv)
    # 不破息(gold_end≥50 或起点<50)不管(买后仍 ≥50)
    calm = [_sim_segment_checks_row(gold=51, waves_gold=52, actions=[_buy()])]
    assert not segments.seg_check_break_interest_exception(calm)
    # 例外⑥boss 窗地板授权(ADR-0478):boss 节点破息但花后 ≥ boss_floor(10)
    # → 豁免;跌破地板 → 越权仍报(detail 带越权标注)
    boss_ok = [_sim_segment_checks_row(gold=48, waves_gold=51, node='boss',
                    actions=[_buy('线核件', cost=3, channel='engine')])]
    boss_ok[0]['sim']['spend']['buys'] = {'d2_line_carry': 3}
    assert not segments.seg_check_break_interest_exception(boss_ok)
    boss_breach = [_sim_segment_checks_row(gold=6, waves_gold=51, node='boss',
                        actions=[_buy('线核件', cost=45, channel='engine')])]
    boss_breach[0]['sim']['spend']['buys'] = {'d2_line_carry': 45}
    evs_boss = segments.seg_check_break_interest_exception(boss_breach)
    assert evs_boss and '越权' in evs_boss[0]['detail']


# --------------------------------------------------------------- [13]
def test_seg_formed_still_buying_transition_bidirectional() -> None:
    """[13] 成型停手:成型后新增过渡填充件必报;目标件/同名副本豁免。"""
    base = {'state': _formed_state()}
    bad = [_sim_segment_checks_row(1, **dict(base)),
           _sim_segment_checks_row(2, gold=30, waves_gold=30, actions=[
               _buy('散装过渡件', channel='engine')], state=_formed_state()),
           ]
    evs = segments.seg_check_formed_still_buying_transition(bad)
    assert evs and evs[0]['round_num'] == 2 \
        and evs[0]['bought'] == '散装过渡件'
    # 未成型阶段的同类买入 → 不报
    early = [_sim_segment_checks_row(1, gold=30, waves_gold=30, actions=[_buy('散装过渡件')],
                  state={'board_factions': {}, 'deployed': [],
                         'bench': [], 'cap': 3, 'level': 3})]
    assert not segments.seg_check_formed_still_buying_transition(early)
    # 同名在场再买 = 升星副本路径([4]/[28]) → 豁免
    dup_state = _formed_state()
    dup_state['deployed'] = [{'char_id': '散装过渡件'}]
    dup = [_sim_segment_checks_row(1, **base), _sim_segment_checks_row(2, gold=30, waves_gold=30,
                                 state=dup_state,
                                 actions=[_buy('散装过渡件')])]
    assert not segments.seg_check_formed_still_buying_transition(dup)
    # 目标件买入(bridge 名册内身份/目标 comp 名册)→ 豁免:用真实
    # bridge_pool 组件名查一个名单成员
    from sr_od.application.currency_war.kernel.cw_line_defs import BRIDGE_POOL
    bridge_member = next(iter({n for combo in BRIDGE_POOL
                               for n in (*combo.fixed, *combo.core)}))
    target = [_sim_segment_checks_row(1, **base),
              _sim_segment_checks_row(2, gold=30, waves_gold=30, state=_formed_state(),
                   actions=[_buy(bridge_member, channel='engine')])]
    assert not segments.seg_check_formed_still_buying_transition(target)


def test_seg_formed_still_buying_transition_release_arm() -> None:
    """[13] ④ 放行臂例外(两形态构造帧锁):成型后经 ④ 转线前瞻放行臂
    (买因 ``transition_component_buy``)买入 TRANSITION_PACK carry/partial
    成员**不报**(未定型期转型前瞻例外;出处 = 策略文档
    12_line_and_intention.md §2,用户裁定 2026-09-07;ADR-0580 §3 规则④
    + §7 检查器对齐申报);纯过渡件仍报,两形态:
    - drop 档带 ④ 买因(写侧误挂形态)照报 = 放行集成员资格闸——
      drop 档在 transition_release_names 数据源处即不入集,负空间
      排除,无需独立 drop 判定;
    - 放行集成员不经 ④ 买因(常规通道买入)照报 = 买因闸——例外
      只辖 ④ 臂买入,不经该臂的过渡件买入仍在 [13] 辖域。
    夹具选名(亲核注册表):姬子·启行 = carry 档、非 BRIDGE_POOL、
    列车同行阵营(engine 身份档);卡芙卡 = drop 档、非 BRIDGE_POOL、
    engine 身份档——都避开桥池/目标名册既有豁免,防既有豁免先行
    吞掉新分支(锁假绿)。
    """
    formed_r2 = {'gold': 30, 'waves_gold': 30, 'state': _formed_state()}

    def _frame(buy: dict) -> list[dict]:
        return [_sim_segment_checks_row(1, state=_formed_state()),
                _sim_segment_checks_row(2, **formed_r2, actions=[buy])]

    def _buy4(name: str) -> dict:
        return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': 3},
                'reason': 'transition_component_buy', 'channel': 'engine'}

    # ④ 件放行:carry 成员 + ④ 买因 → 不报
    assert not segments.seg_check_formed_still_buying_transition(
        _frame(_buy4('姬子·启行')))
    # drop 档 + ④ 买因(误挂形态)→ 仍报,事件点名声与买因
    evs_drop = segments.seg_check_formed_still_buying_transition(
        _frame(_buy4('卡芙卡')))
    assert evs_drop and evs_drop[0]['bought'] == '卡芙卡' \
        and evs_drop[0]['reason'] == 'transition_component_buy'
    # 放行集成员非 ④ 买因(常规 engine 通道)→ 仍报
    evs_non4 = segments.seg_check_formed_still_buying_transition(
        _frame(_buy('姬子·启行', cost=3, channel='engine')))
    assert evs_non4 and evs_non4[0]['bought'] == '姬子·启行' \
        and evs_non4[0]['reason'] == 'd2_engine'


# ---------------------------------------------------------- [12]/[33]
def test_seg_unjustified_levelup_bidirectional() -> None:
    """凭空追级:lv≥5 金<50 无授权必报;pop_slot/dp/static_ev 放行。
    T-115 对齐(ADR-0580;锁重推):奖励节点节点型豁免已随 [16]② 删除
    退役——奖励节点 = 升级抑制对象,无授权升级在奖励帧 = 违规可见
    (授权判定回归 ADR-0471 节点无关通道分类)。"""
    pre = {'board_factions': {}, 'deployed': [], 'bench': [],
           'cap': 5, 'level': 5}
    post = {**pre, 'level': 6}
    bad = [_sim_segment_checks_row(1, state=pre),
           _sim_segment_checks_row(2, gold=28, waves_gold=28, node='battle', state=post,
                actions=[{'__type__': 'LevelUp', 'cost': 4, 'auth': ''}])]
    evs = segments.seg_check_unjustified_levelup(bad)
    assert evs and evs[0]['level_before'] == 5 and evs[0]['gold_before'] == 28
    # 授权白名单(pop_slot=[33] 人口位)→ 放行
    ok_auth = [bad[0], {**bad[1],
                        'actions': [{'__type__': 'LevelUp', 'cost': 4,
                                     'auth': 'pop_slot'}]}]
    assert not segments.seg_check_unjustified_levelup(ok_auth)
    # 奖励帧无授权升级 → 违规可见(T-115 对齐:原「[16]② 放行」语义退役)
    reward_unauth = [bad[0], {**bad[1], 'sim':
                              {**bad[1]['sim'], 'node': 'reward'}}]
    evs_r = segments.seg_check_unjustified_levelup(reward_unauth)
    assert len(evs_r) == 1 and evs_r[0]['round_num'] == 2
    # 奖励帧带白名单授权(扑满环境帧经 M3 闸链形态)→ 放行
    reward_auth = [bad[0], {**bad[1], 'sim':
                            {**bad[1]['sim'], 'node': 'reward'},
                            'actions': [{'__type__': 'LevelUp', 'cost': 4,
                                         'auth': 'm3_batch:arm1'}]}]
    assert not segments.seg_check_unjustified_levelup(reward_auth)


# ------------------------------------------------------------ 恒等式
def test_seg_gold_identity_bidirectional() -> None:
    """链式金恒等式:改一行末金必报;守恒账本零事件。"""
    good = [_sim_segment_checks_row(1, gold=6), _sim_segment_checks_row(2, gold=12)]
    assert not segments.seg_check_gold_identity(good)
    bad = [_sim_segment_checks_row(1, gold=6), _sim_segment_checks_row(2, gold=99)]
    evs = segments.seg_check_gold_identity(bad)
    assert evs and '99' in evs[0]['detail']


def test_seg_must_spend_observation_aggregates() -> None:
    """必花域观测三键聚合(20 号稿 §6):zone/zero 合计 + 零消费帧定位
    + 层命中分布;无键行跳过不造零;零 zone ⇒ 零事件。"""
    rows = [
        {'plane': 1, 'round_num': 1, 'gold': 60,
         'obs': {'must_spend_zone_frames': 2,
                 'must_spend_zero_consume': 1,
                 'must_spend_layer_hit': {'L1': 1, 'L3': 1}}},
        {'plane': 1, 'round_num': 2, 'gold': 70,
         'obs': {'must_spend_zone_frames': 1,
                 'must_spend_zero_consume': 0,
                 'must_spend_layer_hit': {'L2': 1}}},
        {'plane': 1, 'round_num': 3, 'gold': 70},   # 无键行:跳过
    ]
    evs = segments.seg_check_must_spend_observation(rows)
    assert len(evs) == 1
    ev = evs[0]
    assert ev['zone_frames'] == 3
    assert ev['zero_consume'] == 1
    assert ev['zero_consume_rounds'] == [1]
    assert ev['layer_hit'] == {'L1': 1, 'L3': 1, 'L2': 1}
    # 零 zone ⇒ 零事件(无必花域帧不造摘要)
    assert segments.seg_check_must_spend_observation(
        [{'plane': 1, 'round_num': 1, 'gold': 10}]) == []
    # 已入段级检查表(批报告管线自动收账)
    assert 'seg_must_spend_observation' in segments._SEGMENT_CHECKS


# ------------------------------------------------------- 批入口/接线
def test_run_segment_counts_and_caps() -> None:
    """批量入口:计数=真值、events 截断披露、seed 定位字段齐。"""
    ledgers = [[_sim_segment_checks_row(1, gold=55, waves_gold=55)]
               for _ in range(segments._SEGMENT_EVENTS_CAP + 3)]
    rep = segments.run_segment_checks(ledgers, seed_base=100)
    seg = rep['seg_overflow_idle_spend']
    assert seg['count'] == len(ledgers)   # 全部触发
    assert len(seg['events']) == segments._SEGMENT_EVENTS_CAP
    assert seg['truncated'] is True
    assert seg['events'][0]['seed'] == 100 and \
        seg['events'][0]['game_idx'] == 0


@pytest.mark.parametrize('max_rounds', [None, 4])
def test_batch_wiring_window(max_rounds: int | None) -> None:
    """batch 内嵌接线(最小 n;n 小不是统计口径,只验管线):
    segment_checks 键在(独立于 checks 开关)、max_rounds 披露、
    窗口语义=前缀切片(全量跑的前 K 轮金轨迹 ≡ 窗口口径下应为
    同段——这里间接锁 max_rounds=None 时键仍存在且为 None)。"""
    rep = simulate_p1_batch(2, pool='snapshot', ledger=False,
                            checks=False, seed_base=3100,
                            max_rounds=max_rounds)
    assert rep['max_rounds'] == max_rounds
    sc = rep['segment_checks']
    assert set(sc) >= set(segments._SEGMENT_CHECKS) | {'_summary'}
    for row in sc.get('seg_gold_identity', {}).get('events', []):
        assert row['round_num'] <= (max_rounds or 99)


def test_batch_zero_drift_when_no_window(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """零漂移门:不传窗口参数时,checks_violations 与 headline 键集
    与改动前的契约一致(增量键=max_rounds/segment_checks 只增不改)。

    逐字节对拍的基线快照在开发机 .debug/temp(不入仓);测试仓
    锁的是**结构**:既有 top-level 键仍在且 checks_violations 各项
    形状不变(sim-testing checklist 步骤②的机读版)。
    """
    rep = simulate_p1_batch(2, pool='snapshot', ledger=False,
                            seed_base=3200)
    for k in ('n', 'pool_fingerprint', 'pool_source', 'hp_ge_60',
              'avg_final_hp', 'battle_losses_le_2', 'dir_by_r2',
              'avg_refreshes'):
        assert k in rep, f'headline 键缺失: {k}'
    assert rep['max_rounds'] is None
    cv = rep['checks_violations']
    for name, r in cv.items():
        assert 'violations' in r and 'seed_base' in r, f'{name}: {r}'




# ==================== sim_wiring_doc ====================

import re
from dataclasses import fields

from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.sim import engine_p1 as cw_sim

_DOC = (Path(cw_sim.__file__).resolve().parents[5]
        / 'docs' / 'develop' / 'currency_war' / 'sim' / 'sim-wiring.md')


def _tier_rows() -> dict[str, list[str]]:
    """解析文档四个二级节的数据表:节名 → 字段名列表。"""
    text = _DOC.read_text(encoding='utf-8')
    sections = re.split(r'^## ', text, flags=re.M)[1:]
    out: dict[str, list[str]] = {}
    for sec in sections:
        title = sec.splitlines()[0]
        names = re.findall(r'^\| ([a-z_]\w*) \|', sec, flags=re.M)
        out[title] = names
    return out


def test_doc_covers_all_gamestate_fields() -> None:
    """对照表覆盖 GameState 全部字段,一字段一行不重不漏。"""
    rows = _tier_rows()
    all_names = [n for names in rows.values() for n in names]
    expect = [f.name for f in fields(GameState)]
    assert sorted(all_names) == sorted(expect), (
        f'对照表与 GameState 字段不一致:'
        f'缺 {sorted(set(expect) - set(all_names))},'
        f'多 {sorted(set(all_names) - set(expect))}')
    assert len(all_names) == len(set(all_names)), '字段重复出现'


def test_tier_counts_match_declared_reconciliation() -> None:
    """三档计数与文档头对账声明一致(18+12+6=36;ADR-0286 +deploy_cap;批㉖ F1 +enemy_difficulty_live、契约包 C1 步2 +action_log、ADR-0428 +hp_trusted、M2 obs 修复 +level_readable;2026-09-08 死字段清理删 5 个恒缺省「结构未建」占位字段 → 41→36,该档撤档)。"""
    rows = _tier_rows()
    counts = {k: len(v) for k, v in rows.items()}
    assert sum(counts.values()) == len(fields(GameState)) == 36
    assert any('已接线' in k for k in counts) and counts[
        next(k for k in counts if '已接线' in k)] == 18
    assert counts[next(k for k in counts if '必须接线' in k)] == 12
    assert counts[next(k for k in counts if '观测冗余' in k)] == 6
    # 「结构未建」档已撤(2026-09-08 死字段清理):文档不再有该节;
    # 复现需求随依赖结构建设时按新字段流程重立,届时此锁随批加档。


# ==================== shop_odds ====================

import math

from sr_od.application.currency_war.data.cw_shop_odds import (
    SHOP_SLOTS,
    expected_refreshes,
    expected_refreshes_for_card,
    refresh_prob,
)

# —— 边界 ——


def test_zero_p_returns_zero() -> None:
    """p≤0 → 0(该等级不出该费用,刷不到)。"""
    assert expected_refreshes(0.0, 13, 18, 0, 3, 0) == 0.0


def test_owned_meets_target_returns_zero() -> None:
    """j≥k → 0(已凑齐,无需再刷)。"""
    assert expected_refreshes(0.4, 13, 18, 0, 3, 3) == 0.0
    assert expected_refreshes(0.4, 13, 18, 0, 9, 10) == 0.0


# —— 单调性 ——


def test_higher_p_fewer_refreshes() -> None:
    """刷新概率越高,凑齐所需刷新次数越少。"""
    e_low = expected_refreshes(0.3, 13, 18, 0, 3, 0)
    e_mid = expected_refreshes(0.6, 13, 18, 0, 3, 0)
    e_high = expected_refreshes(1.0, 13, 18, 0, 3, 0)
    assert e_low > e_mid, "p=0.3 期望 > p=0.6"
    assert e_mid > e_high, "p=0.6 期望 > p=1.0"
    assert e_high > 0


def test_more_owned_fewer_refreshes() -> None:
    """手上已有越多目标牌,凑齐所需刷新越少(2星 k=3)。"""
    e0 = expected_refreshes(0.4, 13, 18, 0, 3, 0)
    e1 = expected_refreshes(0.4, 13, 18, 0, 3, 1)
    e2 = expected_refreshes(0.4, 13, 18, 0, 3, 2)
    assert e0 > e1, "j=0 期望 > j=1"
    assert e1 > e2, "j=1 期望 > j=2"


def test_pool_manipulation_reduces_refreshes() -> None:
    """买走同费非目标牌(c↑)→ 目标在剩余池里更密 → 期望刷新↓(牌池操纵有效)。"""
    e_c0 = expected_refreshes(0.4, 13, 18, 0, 3, 0)
    e_c10 = expected_refreshes(0.4, 13, 18, 10, 3, 0)
    e_c30 = expected_refreshes(0.4, 13, 18, 30, 3, 0)
    assert e_c0 > e_c10, "c=0 期望 > c=10"
    assert e_c10 > e_c30, "c↑ 期望继续↓"


# —— sanity ——


def test_v44_example_finite_positive() -> None:
    """V4.4 实测参数(77124902 例):7级(p=0.4)找2星3费(v=13,a=18),手上1张 → 有限正数。"""
    e = expected_refreshes(0.4, 13, 18, 0, 3, 1)
    assert e > 0
    assert not math.isinf(e), "期望应为有限值"


def test_three_star_needs_more_than_two_star() -> None:
    """3星(k=9)比 2星(k=3)需要更多刷新(凑齐更多张)。"""
    e_2star = expected_refreshes(0.4, 13, 18, 0, 3, 0)
    e_3star = expected_refreshes(0.4, 13, 18, 0, 9, 0)
    assert e_3star > e_2star, "3星(9张)期望 > 2星(3张)"


# —— 便捷查询 ——


def test_refresh_prob_lookup() -> None:
    """refresh_prob 查表:7级3费=0.4 实测点;无数据=0。"""
    assert refresh_prob(7, 3) == pytest.approx(0.4, abs=1e-2)
    assert refresh_prob(99, 3) == 0.0, "无该等级 → 0"


def test_expected_refreshes_for_card() -> None:
    """便捷查询:7级 D 3费到 2星 → 有限正;已有2张 → 更少。"""
    e = expected_refreshes_for_card(level=7, cost=3, target_star=2, owned=0)
    assert e > 0
    e_owned = expected_refreshes_for_card(level=7, cost=3, target_star=2, owned=2)
    assert e_owned < e, "已有2张 → 期望更少"


def test_shop_slots_is_5() -> None:
    """每次刷新 5 格(机制常量)。"""
    assert SHOP_SLOTS == 5


# ==================== platt_calibration ====================

from sr_od.application.currency_war.telemetry.cw_win_model import (
    PlattCalibrator,
    fit_platt_scaling,
)


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


# --- 恒等默认零漂移锁 --------------------------------------------------------

def test_identity_default_is_zero_drift() -> None:
    """默认参数 a=1, b=0 = 恒等映射:任意合法 p 逐位不变(校准层关闭态)。"""
    assert PlattCalibrator().a == 1.0 and PlattCalibrator().b == 0.0
    for p in (0.0, 1e-9, 0.01, 0.2, 0.5, 0.7321, 0.99, 1.0 - 1e-9, 1.0):
        assert PlattCalibrator().apply(p) == p, p


def test_out_of_range_input_passthrough() -> None:
    """越界/非有限输入原样返回(防御口径:不静默修正也不抛)。"""
    cal = PlattCalibrator(a=2.0, b=-1.0)
    assert cal.apply(-0.1) == -0.1 and cal.apply(1.1) == 1.1
    assert math.isnan(cal.apply(float('nan')))
    assert cal.apply(float('inf')) == float('inf')


# --- 拟合纯函数锁 ------------------------------------------------------------

def test_fit_recovers_known_linear_logit_transform() -> None:
    """可识别性锁:标签按 ``y ~ Bernoulli(sigmoid(a·logit(p)+b))`` 采样
    (真随机噪声标签 → 数据不可分,LR 极大似然一致),拟合应恢复 (a, b)
    (有限样本估计误差,量级锁 ±40%)。注:近可分数据(标签近乎确定性)
    会使无正则 LR 斜率发散,是 Platt 已知边界——故必须用伯努利采样标签。"""
    a_true, b_true = 1.8, -1.2
    n = 4000
    ys: list[int] = []
    ps: list[float] = []
    # 确定性伪随机(lcg),保持纯函数测试零随机依赖
    s = 12345
    for i in range(n):
        z = -3.0 + 6.0 * i / n
        p = _sigmoid(z)
        q = _sigmoid(a_true * z + b_true)  # logit(p) == z,真后验即 Platt 模型
        s = (s * 1103515245 + 12345) % (1 << 31)
        ys.append(1 if s / (1 << 31) < q else 0)
        ps.append(p)
    cal = fit_platt_scaling(ys, ps)
    assert cal.a == pytest.approx(a_true, rel=0.4)
    assert cal.b == pytest.approx(b_true, abs=0.8)


def test_fit_is_pure_and_deterministic() -> None:
    """纯函数锁:同入参两次拟合结果逐一相同(零随机/零 IO 的可观测面)。"""
    ys = [1, 0, 1, 1, 0, 0, 1, 0] * 5
    ps = [0.9, 0.1, 0.8, 0.7, 0.2, 0.3, 0.6, 0.4] * 5
    c1 = fit_platt_scaling(ys, ps)
    c2 = fit_platt_scaling(ys, ps)
    assert c1 == c2 and (c1.a, c1.b) != (1.0, 0.0)


def test_fit_degenerate_inputs_fall_back_identity() -> None:
    """退化输入(空/单类/全非法概率)→ 恒等降级(校准层自动关闭,不抛):
    单类锚定不了偏移与尺度,硬拟合会把校准面扭曲成常数——宁可不校准。"""
    ident = PlattCalibrator()
    assert fit_platt_scaling([], []) == ident
    assert fit_platt_scaling([1, 1, 1], [0.2, 0.5, 0.9]) == ident
    assert fit_platt_scaling([0, 0, 0], [0.2, 0.5, 0.9]) == ident
    assert fit_platt_scaling([1, 0], [float('nan'), 0.5]) == ident
    # 部分行非法:合法行仍参与拟合(剔除而非整批作废)
    c = fit_platt_scaling([1, 0, 1, 0], [1.5, 0.1, 0.9, 0.2])
    assert c.a > 0  # 正常学出正斜率


def test_fit_reduces_systematic_undershoot() -> None:
    """语义锁(锁的是校准意图,不是 LR 数值):构造「排序好但概率整体
    下压」的锚(欠冲形态,出处=W495 影子对拍顶桶偏差 −0.30),
    拟合后的校准应把桶均值偏差显著收窄。"""
    # n 1500→600(2026-09-03 瘦身批,纪律 12):锁的是「欠冲收窄」方向,
    # 非 LR 数值;种子固定 LCG,600 点方向判定稳定。主恢复锁
    # (test_fit_recovers, n=4000)保持全量。
    n = 600
    ys: list[int] = []
    ps: list[float] = []
    s = 777
    for i in range(n):
        z = -3.0 + 6.0 * i / n
        s = (s * 1103515245 + 12345) % (1 << 31)
        noise = s / (1 << 31) - 0.5
        ys.append(1 if z + noise > 0 else 0)
        ps.append(_sigmoid(0.35 * z - 0.6))  # 压缩 + 下压 → 高分段欠冲
    cal = fit_platt_scaling(ys, ps)
    bias_before = sum(ps) / n - sum(ys) / n
    ps_cal = [cal.apply(p) for p in ps]
    bias_after = sum(ps_cal) / n - sum(ys) / n
    assert abs(bias_after) < abs(bias_before)
    # 顶桶(原分数最高段)欠冲收敛方向
    k = n // 4
    top = sorted(range(n), key=lambda i: ps[i])[-k:]
    bias_top_before = sum(ps[i] for i in top) / k - sum(ys[i] for i in top) / k
    bias_top_after = (sum(ps_cal[i] for i in top) / k
                      - sum(ys[i] for i in top) / k)
    assert abs(bias_top_after) < abs(bias_top_before)


# ==================== weight_search ====================

import random
from sr_od.application.currency_war.tools.cw_weight_search import (
    WeightDim,
    WeightSpace,
    cem_search,
    evaluate_weights,
)


def _synthetic_fitness(xs, seed, optimum=None, trap=None):
    """合成适应度:朝 optimum 的碗形 + 可选「陷阱维度」(sim 偏差虚高)。"""
    rng = random.Random(seed)
    opt = optimum or [3.0, 1.0]
    v = -sum((x - o) ** 2 for x, o in zip(xs, opt, strict=False))
    v += rng.gauss(0, 0.05)   # 观测噪声
    if trap is not None:
        # 陷阱:把权重大幅推离先验可获 sim 虚高(reward hacking 的合成形态)
        v += 0.8 * max(0.0, xs[0] - opt[0]) * 2
    return v


def test_j1_cem_converges_toward_optimum() -> None:
    """J1:已知更优点(远离先验中心)→ CEM 收敛方向正确(最优适应度显著高于先验点)。"""
    space = WeightSpace((WeightDim('w1', 1.0), WeightDim('w2', 0.5)))
    seeds = list(range(20))
    r = cem_search(space, lambda xs, s: _synthetic_fitness(xs, s, optimum=[3.0, 1.0]),
                   seed_bank=seeds, n_gen=10)
    prior_fit = evaluate_weights(space.prior_vector(),
                                 lambda xs, s: _synthetic_fitness(xs, s, optimum=[3.0, 1.0]),
                                 seeds, l2_coeff=0.05, center=space.prior_vector())
    assert r['best_fitness'] > prior_fit + 0.5, (
        f"收敛不足: best={r['best_fitness']} vs prior={prior_fit}")
    assert r['best'][0] > 2.0   # 朝 optimum=3 方向移动


def test_j2_regularization_bounds_reward_hacking() -> None:
    """J2 护栏自证:注入 sim 偏差陷阱 → 无正则冠军把 w1 推到上限拿虚高分;
    带正则冠军 w1 受界(离先验更近)——护栏真在防,不是装饰。"""
    space = WeightSpace((WeightDim('w1', 1.0, hi=10.0), WeightDim('w2', 0.5)))
    seeds = list(range(15))
    trap = object()
    no_reg = cem_search(space, lambda xs, s: _synthetic_fitness(xs, s, trap=trap),
                        seed_bank=seeds, n_gen=8, l2_coeff=0.0)
    with_reg = cem_search(space, lambda xs, s: _synthetic_fitness(xs, s, trap=trap),
                          seed_bank=seeds, n_gen=8, l2_coeff=0.3)
    assert no_reg['best'][0] > with_reg['best'][0], (
        f"正则未约束 hacking: no_reg={no_reg['best']} reg={with_reg['best']}")
    assert with_reg['best'][0] < no_reg['best'][0]


def test_prior_anchor_monotone() -> None:
    """中心保留锚:任何代的最优不劣于先验起点(搜索不倒退)。"""
    space = WeightSpace((WeightDim('w1', 1.0),))
    r = cem_search(space, lambda xs, s: _synthetic_fitness(xs, s),
                   seed_bank=list(range(8)), n_gen=5)
    assert r['best_fitness'] >= r['history'][0]['best_fit'] - 1e-9


def test_l2_penalty_semantics() -> None:
    """L2 语义:同适应度下离先验远者罚重。"""
    f = lambda xs, s: 1.0
    near = evaluate_weights([1.2], f, [1], l2_coeff=1.0, center=[1.0])
    far = evaluate_weights([3.0], f, [1], l2_coeff=1.0, center=[1.0])
    assert far < near
    assert math.isclose(near, 1.0 - 0.04, abs_tol=1e-9)
