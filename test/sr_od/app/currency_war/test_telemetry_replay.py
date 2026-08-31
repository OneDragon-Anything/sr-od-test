"""r121 遥测整库回放回归测试(用户提议落地:用真实遥测数据验证决策动作)。

数据源:.debug/temp/currency_war/replay/decisions.jsonl(缺文件则 skip——
CI/他机无 .debug 时不阻塞)。快照为**进店帧**真实读数,回放当前决策函数。
r122 数据质量:已删 7 个重试环废 run(378 行,判据=单轮高频重复×买0×
board 不演化;备份 .bak_r122);hp=100 毒化行(hp_readable=False)**保留**
——board/bench/shop 是真的,只有 hp 字段不可信,回放断言不用它。

三个断言(源自 2026-08-21 整库回放基线:12964 条/253 run):
① decision_target 双轨+框架件在 bench → 返配方伪 comp(r120 修复面,
   303 条历史快照受益——含 2026-08-18 老局,跨周老病);
② _should_deploy 框架 carry/partial 双轨 → True(拒因只允许同名守卫);
③ pick_framework fresh-read 相邻横跳率 < 12%(基线 7.5%;r114 tracking
   在实跑已零横跳,此阈值是 fresh-read 兜底路径的回归护栏)。


出处:docs/develop/currency_war/decisions/0477-buylayer-takeover-strategy-v1-retirement.md(2026-08-31 测试瘦身批考证补记)。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_deploy_seat import _should_deploy, deploy_legal
from sr_od.application.currency_war.kernel.cw_recipe import decision_target
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, ShopCard
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_transition import (
    FRAMEWORKS,
    TRANSITION_PACK,
    pick_framework,
)

JSONL = (Path(__file__).resolve().parents[5] / '.debug' / 'temp'
         / 'currency_war' / 'replay' / 'decisions.jsonl')


def _rows():
    if not JSONL.exists():
        pytest.skip('遥测 decisions.jsonl 不存在(本机 .debug)')
    return [json.loads(l) for l in JSONL.open(encoding='utf-8') if l.strip()]


def _to_bench(lst):
    return [BenchChar(slot=c.get('slot', 0), char_id=c['char_id'],
                      faction=c.get('faction', '?'), star=c.get('star', 1),
                      position_pref=c.get('position_pref', 'back'))
            for c in (lst or []) if isinstance(c, dict) and c.get('char_id')]


def _to_shop(lst):
    return [ShopCard(x=0, name=c['name'], faction=c.get('faction', '?'),
                     cost=c.get('cost', 1))
            for c in (lst or []) if isinstance(c, dict) and c.get('name')]


def _dual_snapshots_with_fw_bench(rows):
    """双轨 + bench 含框架 carry/partial 的快照(抽样限流)。"""
    out = []
    for d in rows[::13]:   # 抽样(整库 1.3 万条,抽样 ~1000 条秒级)
        st = d.get('state') or {}
        if not st.get('dual_track_phase'):
            continue
        bench = _to_bench(st.get('bench'))
        if not any(TRANSITION_PACK.get(c.char_id, ('',))[0] in FRAMEWORKS
                   and TRANSITION_PACK[c.char_id][1] != 'drop' for c in bench):
            continue
        out.append((d, bench))
    return out


def test_replay_decision_target_recipe_for_fw_bench():
    """① 双轨快照(bench 有框架件)→ decision_target 必返配方(r120 回归)。"""
    snaps = _dual_snapshots_with_fw_bench(_rows())
    assert snaps, '历史库应有双轨+框架件快照(r121 基线 303 条)'
    for d, _bench in snaps[:200]:
        sess = StrategySession()
        sess.transition_framework = '仙舟'   # 框架件在 bench → 至少可设仙舟口径
        st = d.get('state') or {}
        gs = GameState(round_num=d.get('round_num') or 1,
                       plane=d.get('plane') or 1, dual_track_phase=True)
        gs.board = st.get('board') or {}
        dt = decision_target(sess, gs)
        assert dt is not None and '配方' in dt.name, \
            f'{d.get("run_id")} p{d.get("plane")}r{d.get("round_num")} 应返配方伪 comp'


def test_replay_should_deploy_fw_carry():
    """② 框架 carry/partial 双轨 deploy 应 True(拒因只许同名守卫)。"""
    for d in _rows()[::13]:
        st = d.get('state') or {}
        if not st.get('dual_track_phase'):
            continue
        gs = GameState(round_num=d.get('round_num') or 1,
                       plane=d.get('plane') or 1, dual_track_phase=True)
        gs.level = st.get('level') or 3
        gs.bench = _to_bench(st.get('bench'))
        gs.deployed = _to_bench(st.get('deployed'))
        dep_names = {c.char_id for c in gs.deployed if c.char_id}
        for c in gs.bench:
            ent = TRANSITION_PACK.get(c.char_id)
            if not ent or ent[0] not in FRAMEWORKS or ent[1] == 'drop':
                continue
            if _should_deploy(c, gs, None):
                continue
            assert not deploy_legal(c, dep_names), \
                f'{c.char_id} 被拒但非同名守卫(p{gs.plane}r{gs.round_num})——回归!'


def test_replay_framework_flip_rate_guard():
    """③ fresh-read 相邻横跳率护栏(全量相邻序列,基线 7.5%,阈值 12%)。

    ⚠️ 不抽样——抽样破坏相邻性(每 N 取 1 让「相邻」跨 N 条,横跳率机械
    膨胀:实测 ::7 采样子集 13.9% vs 全量 7.5%)。
    """
    rows = _rows()
    seq = []
    for d in sorted(rows, key=lambda r: (r.get('run_id'), r.get('ts') or '')):
        st = d.get('state') or {}
        seq.append((d.get('run_id'),
                    pick_framework(_to_bench(st.get('bench')),
                                   _to_bench(st.get('deployed')),
                                   _to_shop(st.get('shop')))))
    flips = sum(1 for i in range(1, len(seq))
                if seq[i][0] == seq[i - 1][0] and seq[i][1] != seq[i - 1][1])
    rate = flips / max(1, len(seq))
    assert rate < 0.12, f'fresh-read 横跳率 {rate:.1%} 超护栏(基线 7.5%)'
