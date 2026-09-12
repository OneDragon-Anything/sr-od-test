"""test_cw_sim_smoke 主题锁——sim 基建 smoke + 裁判 fail-closed 代表。

覆盖面(承重件):
- 入口 smoke:有限牌池守恒(sim.infra 基础不变量,draw 不减池/take-ret 互逆);
- 金钱不变量:账本守恒裁判(坏账本必报/好账本过/卖回金计收入侧/缺字段报);
- fail-closed 代表:裁判缺键守卫(schema 演化缺 node/income 键必须涌现违规,
  静默绿 = 断言永久失明)+ sim 账本写入器禁写生产 live 流目录(自中毒防线);
- 退役锁回补家(T-197,自 test_cw_sim_suite.py 各节原名回补,利于
  git -S 追溯):连胜金收入口径双向 / 冷启动种子浪费双向 / 写入器退役
  旧根禁写 / 满级拒付守卫(flat4 台账不破)/ 观测硬依赖键哨兵;
  T-198 续补:ret 越限削顶(pool cap,T-197 报告边界发现①)。

来源指针(2026-09-09 目标形态重建批,断言零改动迁移):
- test_cw_sim_suite.py(sim 段/账本检查段/写入器守卫段)。
其余历史锁已退役(git 可复活);sim 每晚全链路(行为层安全网)不在 pytest 面。

出处:被测模块本体 sim/pool.py、sim/checks/(runtime/ledger)、sim/runner.py、
sim/engine_p1.py;写入器守卫事故出处 = 2026-09-07 空批旧根截断事故
(ADR-0586「单一源与守卫」节)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import POOL_COPIES_PER_CARD
from sr_od.application.currency_war.sim.checks import ledger
from sr_od.application.currency_war.sim.checks import runtime as chk
from sr_od.application.currency_war.sim.pool import _Pool
from sr_od.application.currency_war.sim.runner import write_batch_ledger

# ==================== sim infra smoke(自 test_cw_sim_suite.py sim 段迁入) ====================

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
    """ret 越限削顶:重复卖出回池,copies 不超过该卡基础副本数。

    前身 = test_cw_sim_suite.py sim 段同名锁(f799914 退役,T-198 回补):
    同文件迁入的 test_pool_conservation 只断单帧 `copies ≤ cap`,不辖
    连续 ret 越限后的削顶行为(pool.py::ret 的 min(base, ·) 守卫)。
    cap 从 POOL_COPIES_PER_CARD 单一源现算,不抄常数。
    """
    import random
    rng = random.Random(7)
    p = _Pool(rng)
    name = next(iter(p.copies))
    cap = POOL_COPIES_PER_CARD[CHARACTERS[name].cost]
    for _ in range(cap + 5):
        p.ret(name)
    assert p.copies[name] == cap, 'ret 越限未削顶:回池超过基础副本数'


# ==================== 裁判:键名演化变异缺键守卫(自 sim_checks_streak_income 段迁入) ====================

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


# ==================== 裁判:金守恒账本检查(自 sim_ledger_checks 段迁入) ====================

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


# ==================== 写入器守卫:禁写生产流根(自 sim_ledger_checks 段迁入) ====================

def test_write_batch_ledger_guard() -> None:
    """写入器守卫:sim 账本禁写生产 live 流目录(自中毒防线)。

    禁写对象 = 生产流根(kernel/cw_observe.DEFAULT_REPLAY_DIR,单一源直调;
    曾硬抄旧路径字面量——根常量迁移即假绿,现随单一源走)。
    """
    from sr_od.application.currency_war.kernel.cw_observe import DEFAULT_REPLAY_DIR
    with pytest.raises(RuntimeError):
        write_batch_ledger([], DEFAULT_REPLAY_DIR)


# ==================== 退役锁回补(T-197,自 test_cw_sim_suite.py 各节,原名回补) ====================

# --- 连胜金收入口径(runtime.check_streak_combat_only_income) ----------

def _income_row(rn: int, node: str, streak: int, delta: int = 0,
                base: int = 5, interest: int = 0) -> dict:
    """最小合成账本行(生产形状子集:cw_sim 收入段必带 node/income)。"""
    return {'round_num': rn,
            'sim': {'node': node, 'delta': delta,
                    'income': {'base': base, 'interest': interest,
                               'streak': streak}}}


def test_income_caliber_bidirectional() -> None:
    """连胜金收入口径双向锁(原名回补;前身 test_cw_sim_suite.py
    sim_checks_streak_income 节,退役 commit f799914)。

    语义按现行 runtime.check_streak_combat_only_income 重推(精确重算锁,
    胜判据 = delta>0 镜像 cw_sim 结算段):奖励轮照发表值 / 补给轮恒 0 /
    败轮金路径 / 少发同报(双向);期望值全部从 kernel.cw_economy 单一源
    现算(streak_gold/LOSS_GOLD_BY_NODE),不手抄常数(README 第 9 条)。
    姊妹锁(缺键守卫)= 本文件 test_missing_node_key_counts_as_violation。
    """
    from sr_od.application.currency_war.kernel.cw_economy import (
        LOSS_GOLD_BY_NODE,
        streak_gold,
    )
    # 坏:奖励轮多发(进轮连胜 0 → 表值 streak_gold(0),账本 3)必报
    r = chk.check_streak_combat_only_income(
        [[_income_row(1, 'reward', streak=3)]])
    assert r['violations'] == 1, '奖励轮收入断言失明'
    assert r['missing_key_rows'] == 0
    # 坏:补给轮带 streak(补给恒 0,账本 1)必报
    r_s = chk.check_streak_combat_only_income(
        [[_income_row(1, 'supply', streak=1)]])
    assert r_s['violations'] == 1, '补给轮带 streak 未报'
    # 坏:败轮金路径断(r1 战斗败 → r2 须发 LOSS_GOLD_BY_NODE['battle'],
    # 账本仍发表值 streak_gold(1))必报
    r_l = chk.check_streak_combat_only_income([
        [_income_row(1, 'battle', streak=1, delta=-5),
         _income_row(2, 'battle', streak=1, delta=-3)]])
    assert r_l['violations'] == 1, '败轮金路径断言失明'
    assert r_l['loss_gold_rows'] == 1
    # 坏:战斗轮少发(胜轮表值 streak_gold(0),账本 0)→ 双向
    r_u = chk.check_streak_combat_only_income(
        [[_income_row(1, 'battle', streak=0, delta=1)]])
    assert r_u['violations'] == 1, '战斗轮少发未报(双向失明)'
    # 好:全链零违规,且披露面与精确重算对拍
    # (r1 胜进轮 0;r2 败进轮 1 表值照发;r3 进轮 0 + 上轮败 → 败轮金;
    #  r4 奖励进轮 0 照发;r5 补给恒 0)
    good = [[_income_row(1, 'battle', streak=1, delta=1),
             _income_row(2, 'battle', streak=1, delta=-5),
             _income_row(3, 'battle', streak=2, delta=-3),
             _income_row(4, 'reward', streak=1),
             _income_row(5, 'supply', streak=0, base=5, interest=2)]]
    r2 = chk.check_streak_combat_only_income(good)
    assert r2['violations'] == 0, f'好样本误报: {r2}'
    assert r2['missing_key_rows'] == 0
    assert r2['delta'] == 0
    assert r2['loss_gold_rows'] == 1   # r3 = 败轮金路径唯一命中
    assert r2['supply_rows'] == 1
    assert r2['supply_issued_extra'] == 7   # 补给多发残差 = base 5 + 利息 2
    assert r2['combat_only_streak_income'] == (
        streak_gold(0) + streak_gold(1) + LOSS_GOLD_BY_NODE['battle']
        + streak_gold(0) + 0)


# --- 冷启动种子浪费(ledger.check_coldstart_seed_squander) -------------

def _coldstart_buy(rn: int, name: str, reason: str, channel: str) -> dict:
    """开局轮买入合成行(channel 键 = 引擎 classify_buy 执行点转录)。"""
    return {'plane': 1, 'round_num': rn, 'target_comp': '',
            'actions': [{'__type__': 'BuyCard',
                         'card': {'name': name, 'cost': 1},
                         'reason': reason, 'channel': channel}]}


def test_coldstart_check_bidirectional() -> None:
    """冷启动种子浪费双向锁(原名回补;前身 test_cw_sim_suite.py
    sim_ledger_checks 节,退役 commit f799914;局49/局53 指纹,
    ADR-0240+r371b)。

    语义按现行 ledger.check_coldstart_seed_squander 重推(T-153 C1 迁移
    后):pair/off 开局轮(r≤2)必报主臂 + d2_ 前缀(可再带 _merge 尾)
    归一化防对新栈无声失效 + 窗外/其它通道豁免。身份自述复核面
    (bridge_seed/engine 失配 → 可疑项)由 test_cw_suspect_review.py::
    test_c1_coldstart_identity_review 辖;生产 checks 路径接线面
    (off 必报/engine_seed 放行)由 test_cw_telemetry_archive.py::
    test_v2_stack_runs_coldstart 辖——本锁不重复断言这两面
    (README 第 7 条重复断言纪律)。
    """
    # 坏:局53 形态(系统 bench 带卡,同阵营线外 pair,r2 窗内)必报
    v = ledger.check_coldstart_seed_squander(
        [_coldstart_buy(2, '阿格莱雅', 'pair', 'pair')])
    assert v and '阿格莱雅' in v[0], f'局53 形态未报: {v}'
    # 好:开局窗外(r3+)pair 凑对恢复合法(r371b 回归点)
    assert not ledger.check_coldstart_seed_squander(
        [_coldstart_buy(3, '翡翠', 'pair', 'pair')])
    # 好:其它通道(emergency/line 等)各有语义,门不越权
    assert not ledger.check_coldstart_seed_squander(
        [_coldstart_buy(1, '翡翠', 'emergency', 'off')])
    # 坏:decision_v2 栈 reason 带 d2_ 前缀(可再带 _merge 尾)——
    # 归一化后同指纹必报(归一化单一源 = _normalize_buy_reason)
    v2 = ledger.check_coldstart_seed_squander(
        [_coldstart_buy(1, '翡翠', 'd2_off', 'off')])
    assert v2 and '翡翠' in v2[0], f'd2_off 归一化失明: {v2}'
    v3 = ledger.check_coldstart_seed_squander(
        [_coldstart_buy(2, '阿格莱雅', 'd2_pair_merge', 'pair')])
    assert v3 and '阿格莱雅' in v3[0], f'd2_pair_merge 归一化失明: {v3}'


# --- 写入器守卫补充面:退役旧根禁写 ------------------------------------

def test_write_batch_ledger_guard_retired_roots(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """写入器守卫补充面:退役旧根(sim 批根/旧流根)同样禁写(原名回补;
    前身 test_cw_sim_suite.py sim_ledger_checks 节,退役 commit f799914)。

    出处 = 2026-09-07 22:20:52 空批以旧 replay 根为 out_dir 把历史三流
    整份截断的事故(ADR-0586「单一源与守卫」节):守卫同时锁退役根
    字面量(kernel/cw_observe.RETIRED_* 单一源),根切换过渡窗口内旧根
    不失保护;不选「out_dir 限定 SIM_ROOT 子树」——A/B 对照等合法调用方
    写显式独立目录(docstring 契约),子树限定会破契约。
    安全网 = 检测网,非复原网:被测对象是守卫不是清理,``sim.runner.
    _prune_sim_runs`` 桩化 no-op;事前登记旧根流文件的存在/字节,守卫
    失守时 'w' 截断会真实发生,本测试职责 = 让失守在事后断言处现形(红)。
    现旧根流已全部迁移(ADR-0586),失守的实际危害 = 旧根新建空文件污染,
    无封存物可烧。
    """
    from sr_od.application.currency_war.kernel.cw_observe import (  # noqa: I001  (kernel/sim 两簇分组导入)
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


# --- 满级拒付守卫(engine_p1 执行层 cap 守卫;桩策略逼守卫本体) --------

_LEVELCAP_SIM_CACHE: dict[int, object] = {}


class _LevelUpSpamStub:
    """升级桩:每段恒发 3 个 LevelUp——未满级时合法执行,满级后逼出守卫。"""

    def decide_shop_screen(self, sess, cfg):  # noqa: ANN001, ARG002
        from sr_od.application.currency_war.kernel.cw_state import LevelUp
        return [LevelUp(cost=4) for _ in range(3)]


def _levelcap_spam_run():
    """桩策略一局(simulate 同次测试运行只跑一遍,两锁共享;README 第 11 条)。"""
    if 1 not in _LEVELCAP_SIM_CACHE:
        from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
        _LEVELCAP_SIM_CACHE[1] = simulate_p1(
            1, pool='fallback', strategy=_LevelUpSpamStub())
    return _LEVELCAP_SIM_CACHE[1]


def test_sim_levelup_cap_guard_rejects_and_discloses() -> None:
    """满级后 LevelUp 拒付:金不扣、无 LevelUp 执行行、计数披露(原名回补;
    前身 test_cw_sim_suite.py sim_levelcap_guard 节,退役 commit f799914)。

    语义按现行 engine_p1 重推:cap 守卫在执行层 LevelUp 分支
    (level >= LEVEL_CAP → 记 LevelUpRejected 行 + sim.level_cap_rejects
    计数,不扣金不进 XP;sim-only 已知差异申报保留 = ADR-0561 申报表 #6);
    决策层对齐(sim_decision_registry 注入 level_max)辖正常策略,本锁用
    桩策略直发动作逼守卫本体(决策层对齐不辖桩直发路径)。
    """
    from sr_od.application.currency_war.sim.engine_p1 import LEVEL_CAP

    rows = _levelcap_spam_run().ledger
    assert rows, '账本为空:运行异常'

    # 守卫确实介入:有轮记录了拒付计数
    rejected_total = sum((r.get('sim') or {}).get('level_cap_rejects', 0)
                         for r in rows)
    assert rejected_total > 0, '满级桩未逼出守卫:level_cap_rejects 全 0'

    # 满级判定:某轮末 state.level 达 LEVEL_CAP → 该轮**之后**的轮不再
    # 有 LevelUp 执行行(拒付行 LevelUpRejected 不算执行)。
    cap_seen = False
    for r in rows:
        if cap_seen:
            st = r.get('state') or {}
            assert st.get('level', 0) >= LEVEL_CAP, '满级后等级回退:状态链坏'
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
        cap_seen = cap_seen or (r.get('state') or {}).get('level', 0) >= LEVEL_CAP


def test_sim_levelup_rejected_rows_keep_flat4_ledger_lock() -> None:
    """拒付行不破坏升级支出锁(ADR-0632 决策 3 重推:spend == Σ action.cost,无折扣局
    退化 = 原 flat4 4×执行行数;原名回补,前身同上节)。

    判据本体(检查器单元面)由 test_cw_sim_models.py::
    test_levelup_flat4_lock_bidirectional 辖;本锁辖生产链路面
    (README 第 13 条):真实账本里拒付行(LevelUpRejected)不入
    LevelUp 执行行计数、spend.levelup 只计实付击——拒付混入即红。
    """
    from sr_od.application.currency_war.sim.checks.ledger import (
        check_levelup_flat4_ledger_lock,
    )

    violations = check_levelup_flat4_ledger_lock(_levelcap_spam_run().ledger)
    assert not violations, f'升级支出锁被拒付行破坏:{violations[:3]}'


class _SpyPricedLevelUpStub:
    """商业间谍局升级桩:单价走 kernel ``xp_click_cost`` 真值(与生产策略层
    同价源——mandate shop 升级链 spend_unified/LevelUp cost 同函数);
    sim 无 OCR 恒兜底支 4−1=3,载体链 = 决策层定价 → engine action.cost
    → 账本 spend。"""

    def decide_shop_screen(self, sess, cfg):  # noqa: ANN001, ARG002
        # 定价读 = 容器(W6 波 4 接缝族切容器帧;构造容器帧直接喂)
        from sr_od.application.currency_war.kernel.cw_board_state import (
            BoardState as _BS,
        )
        from sr_od.application.currency_war.kernel.cw_board_state import (
            ChannelSig,
        )
        from sr_od.application.currency_war.kernel.cw_economy import (
            xp_click_cost,
        )
        from sr_od.application.currency_war.kernel.cw_state import LevelUp
        _bs = _BS(schema_version=1)
        _bs.write_logic(_bs.active_strategies, ['商业间谍'],
                        produced_by='test_spy_stub',
                        sig=ChannelSig(family='logic_hook',
                                       actor='synthesize_from_game_state'))
        price = xp_click_cost(_bs)
        return [LevelUp(cost=price) for _ in range(3)]


_SPY_SIM_CACHE: dict[int, object] = {}


def _spy_levelup_run():
    """间谍局一局(simulate 同次测试运行只跑一遍,README 第 11 条)。"""
    if 1 not in _SPY_SIM_CACHE:
        from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
        _SPY_SIM_CACHE[1] = simulate_p1(
            1, pool='fallback', strategy=_SpyPricedLevelUpStub())
    return _SPY_SIM_CACHE[1]


def test_sim_spy_round_fee_path_single_discount() -> None:
    """商业间谍局 sim 对账(ADR-0632 验证自证):决策定价 → 执行载体 → 账本
    → 支出锁全链单次折扣一致。

    旧字面 flat4 锁(4×行数)对本局误报 = ADR-0632 锁重推动因(先红在案);
    重推后判据 spend == Σ action.cost 全程绿。价格面真值(折扣感知取价
    正确性)由 kernel 锁族(test_cw_economy xp 折扣修复锁族)辖,本锁辖
    执行/账本链一致性。"""
    from sr_od.application.currency_war.sim.checks.ledger import (
        check_levelup_flat4_ledger_lock,
    )

    rows = _spy_levelup_run().ledger
    executed = [a for r in rows for a in (r.get('actions') or [])
                if a.get('__type__') == 'LevelUp']
    assert executed, '间谍局无 LevelUp 执行行:桩未生效'
    assert all(a.get('cost') == 3 for a in executed), (
        '间谍局单价 ≠ 3:费用路径折扣口径漂移(应单次折扣 4−1)')
    violations = check_levelup_flat4_ledger_lock(rows)
    assert not violations, f'间谍局支出锁红:{violations[:3]}'


# --- 观测硬依赖键面哨兵(ledger.check_observation_keys_live) -----------

def test_observation_keys_check_bad_rows_report() -> None:
    """观测硬依赖键哨兵双向锁(原名回补;前身 test_cw_sim_suite.py
    sim_obs_keys 节,退役 commit f799914)。

    语义按现行 ledger.check_observation_keys_live 重推:坏形态 = 缺
    满栏旗标/旗标非布尔/下档越域/分配域非法/OR 聚合但帧缺 + 轮岗概率
    条缺键(p1_downgrade 位已随 v2 退役链删除,不在必检集);P2 行不辖
    (键族只承诺 P1 段);真实 sim 账本零违规 = 写端(engine_p1 逐轮
    披露)未断线(README 第 13 条生产链路面)。
    """
    import copy

    base = {
        'plane': 1, 'round_num': 3,
        'state': {'bench_full_flag': False, 'board_next_tier': {'仙舟': 3},
                  'refresh_probs': {2: 0.5, 3: 0.3}},
        'sim': {'alloc_frame': {'active': False, 'reason': 'out_of_scope'},
                'alloc_active_any': False},
    }
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
    del r['state']['refresh_probs']
    cases.append(('缺轮岗概率条', r))
    for label, row in cases:
        v = ledger.check_observation_keys_live([row])
        assert v, f'{label}: 坏行未报=检查静默失效'
    # P2 行不辖(键族只承诺 P1 段)
    p2 = copy.deepcopy(base)
    p2['plane'] = 2
    assert not ledger.check_observation_keys_live([p2])
    # 生产链路面:真实 sim 账本(与满级拒付两锁共享同一桩局)零违规
    assert not ledger.check_observation_keys_live(_levelcap_spam_run().ledger), \
        '真实账本观测键违规:写端断线或形状回归'
