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

CUT6 瘦身批(2026-09-09):sim 每晚全链路覆盖的 happy-path 集成/接线锁砍除
(seed 复现/批量形状/节点骨架/批检接线/文档对照/单调性族/变异推演/
权重搜索机械面等),保留核清单与逐条判据见 reports/_cluster_CUT6.md。
"""
from __future__ import annotations

# ==================== sim ====================
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import POOL_COPIES_PER_CARD
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.sim.pool import _Pool


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


# ==================== sim_checks_streak_income ====================


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


# ==================== sim_ledger_checks ====================
from pathlib import Path

import pytest

from sr_od.application.currency_war.sim.checks import ledger
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


# ==================== sim_levelcap_guard ====================

class _LevelUpSpamStub:
    """升级桩:每段恒发 3 个 LevelUp——未满级时合法执行,满级后逼出守卫。"""

    def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.kernel.cw_state import LevelUp
        return [LevelUp(cost=4) for _ in range(3)]


def test_sim_levelup_cap_guard_rejects_and_discloses() -> None:
    """满级后 LevelUp 拒付:金不扣、无 LevelUp 执行行、计数披露。"""


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


def test_sim_levelup_rejected_rows_keep_flat4_ledger_lock() -> None:
    """拒付行不破坏 flat4 台账锁(spend.levelup == 4×LevelUp 行数)。"""

    from sr_od.application.currency_war.sim.checks.ledger import (
        check_levelup_flat4_ledger_lock,
    )

    res = simulate_p1(1, pool='fallback', strategy=_LevelUpSpamStub())
    violations = check_levelup_flat4_ledger_lock(res.ledger)
    assert not violations, f'flat4 台账锁被拒付行破坏:{violations[:3]}'


# ==================== sim_obs_keys ====================


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


# ==================== sim_segment_checks ====================

from sr_od.application.currency_war.sim.checks import segments


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


# ==================== shop_odds ====================

import math

from sr_od.application.currency_war.data.cw_shop_odds import (
    expected_refreshes,
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


def test_refresh_prob_lookup() -> None:
    """refresh_prob 查表:7级3费=0.4 实测点;无数据=0。"""
    assert refresh_prob(7, 3) == pytest.approx(0.4, abs=1e-2)
    assert refresh_prob(99, 3) == 0.0, "无该等级 → 0"


# ==================== platt_calibration ====================

from sr_od.application.currency_war.telemetry.cw_win_model import (
    PlattCalibrator,
    fit_platt_scaling,
)

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


# ==================== weight_search ====================

import random

from sr_od.application.currency_war.tools.cw_weight_search import (
    WeightDim,
    WeightSpace,
    cem_search,
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


