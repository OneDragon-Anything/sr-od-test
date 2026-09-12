"""CW A/B 载体(T-122 装载;T-120 方案 §6.1「A/B 编排迁新 runner(测试仓)」)。

三面(装载设计 §3.1):
- **加载面** = ``run_ab_game``/``run_ab_games``:每 (seed, arm) 一次
  ``fake_p1_run`` 全链装配 → ``run_p1()``,产出 ``AbGameStats``(轨迹/
  发生面/计数器切片/环境指纹)。
- **切换面** = 臂开关:P77 2★ 现货比较子的基线臂经 monkeypatch 关闭
  (``shop.spot2_direct_out_card`` 恒 None)。生产代码零开关
  (strategy-work §3「A/B 对照手段不进生产代码」);pytest 传原生
  monkeypatch,独立驱动(tools/cw_ab_batch.py)传 ``MonkeyShim``
  (同 setattr 形状,含 raising 语义)。
- **对照面** = ``paired_delta``(同 seed 配对逐指标 Δ=variant−baseline)
  + ``summarize``(逐臂中位/p90)。**A/B 无数值裁决权**(strategy-work
  §4):产出仅配对读数,禁据此定数值。

环境前置:2★ 直出机制入假环境(rules.SHOP_DIRECT_OUT_2STAR_P,校准层
演练偏置申报)使比较子在本载体上可观测(否则结构性无帧)。
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

_ARMS: tuple[str, ...] = ('baseline', 'variant')

#: A/B 默认节点剧本(与保真基线批同形,五节点覆盖四类节点与胜负两态;
#: 保持与 fidelity 批同剧本 = 同 seed 跨批读数可比)。
DEFAULT_NODE_SEQUENCE: list[str] = ['battle', 'reward', 'battle', 'supply',
                                    'boss']

#: 计数器切片键(对照面消费的事件面全集;取自 ADR-0626 遥测分键与
#: 既有拒因键)。
CARRIER_COUNTER_KEYS: tuple[str, ...] = (
    'm2_stockpile_spot2_buy',
    'm2_stockpile_star_mismatch',
    'stockpile_unaffordable',
    'bench_full',
    'm6_s_reserve_reject',
    'm6_s_reserve_remeet_frames_sum',
)


class MonkeyShim:
    """脱离 pytest 的 monkeypatch 等价物(仅 ``setattr`` 形状;
    harness ``_install_stubs`` 与本载体全部消费点共用此形状,
    ``raising`` 语义与 pytest 对齐)。"""


    def __init__(self) -> None:
        self._undo: list[tuple[Any, str, Any]] = []

    def setattr(self, target: Any, name: str, value: Any,
                raising: bool = True) -> None:
        if not hasattr(target, name):
            if not raising:
                return
            raise AttributeError(f'{target!r} 无属性 {name}')
        self._undo.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def undo(self) -> None:
        for target, name, value in reversed(self._undo):
            setattr(target, name, value)
        self._undo.clear()


@dataclass
class AbGameStats:
    """一局假局 A/B 读数(全链生产返回值,零测试侧再计算)。"""

    seed: int
    arm: str
    rounds: int
    gold_traj: list[int]
    hp_traj: list[int]
    launched: bool
    counters: dict[str, int] = field(default_factory=dict)
    env_fingerprint: dict = field(default_factory=dict)

    def counter(self, key: str) -> int:
        return int(self.counters.get(key, 0))


def run_ab_game(ctx, monkeypatch: Any, tmp_path, seed: int, arm: str, *,
                node_sequence: list[str] | None = None,
                initial_gold: int = 30,
                archive_dir_name: str | None = None) -> AbGameStats:
    """单局加载(一臂一种子)。``arm='baseline'`` 经切换面关闭 P77
    比较子;``arm='variant'`` 生产原样。"""
    if arm not in _ARMS:
        raise ValueError(f'未知臂 {arm!r}(合法 {_ARMS})')
    from fixtures.cw_fake_game.fake_match import FAKE_GAME_ENV_VERSION
    from fixtures.cw_harness import fake_p1_run
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        shop as shop_mod,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )
    with fake_p1_run(ctx, monkeypatch, tmp_path, seed,
                     node_sequence=(list(node_sequence)
                                    if node_sequence is not None
                                    else list(DEFAULT_NODE_SEQUENCE)),
                     initial_gold=initial_gold,
                     archive_dir_name=(archive_dir_name
                                       or f'ab_{arm}_{seed}')) as run:
        if arm == 'baseline':
            monkeypatch.setattr(shop_mod, 'spot2_direct_out_card',
                                lambda *a, **k: None)
        res = run.run_p1()
        counters = dict(getattr(state_of(run.cw_match.session),
                                'cw4_counters', {}) or {})
        fp = dict(run.match.env_fingerprint())
        fp['FAKE_GAME_ENV_VERSION'] = FAKE_GAME_ENV_VERSION
        return AbGameStats(seed=seed, arm=arm, rounds=len(res.rounds),
                           gold_traj=list(res.gold_trajectory),
                           hp_traj=list(res.hp_trajectory),
                           launched=bool(res.launched),
                           counters=counters, env_fingerprint=fp)


def run_ab_games(ctx, monkeypatch: Any, tmp_path, seeds,
                 arms: tuple[str, ...] = _ARMS, *,
                 node_sequence: list[str] | None = None,
                 initial_gold: int = 30) -> dict[int, dict[str, AbGameStats]]:
    """配对批加载:逐 (seed, arm) 隔离档案根;返回 ``{seed: {arm: stats}}``。
    运行态前置/复位在本函数内闭环(与保真批同形)。"""
    from test.harness.fixture_controller import (
        enter_running_state,
        reset_running_state,
    )
    games: dict[int, dict[str, AbGameStats]] = {}
    enter_running_state(ctx)
    try:
        for seed in seeds:
            per: dict[str, AbGameStats] = {}
            for arm in arms:
                per[arm] = run_ab_game(ctx, monkeypatch, tmp_path, seed,
                                       arm, node_sequence=node_sequence,
                                       initial_gold=initial_gold,
                                       archive_dir_name=f'ab_{arm}_{seed}')
            games[seed] = per
    finally:
        reset_running_state(ctx, ctx.cw_match)
    return games


def paired_delta(games: dict[int, dict[str, AbGameStats]]) -> dict[str, dict]:
    """对照面:同 seed 配对逐指标 Δ=variant−baseline(A/B 无裁决权,
    输出仅读数)。指标 = 终金/最低 hp/轮数 + 计数器切片键。"""
    out: dict[str, dict[int, float]] = {}
    for seed, per in games.items():
        a, b = per['baseline'], per['variant']
        rows: dict[str, float] = {
            'final_gold': b.gold_traj[-1] - a.gold_traj[-1],
            'min_hp': min(b.hp_traj or [0]) - min(a.hp_traj or [0]),
            'rounds': b.rounds - a.rounds,
        }
        for key in CARRIER_COUNTER_KEYS:
            rows[key] = b.counter(key) - a.counter(key)
        for k, v in rows.items():
            out.setdefault(k, {})[seed] = v
    return out


def summarize(games: dict[int, dict[str, AbGameStats]]) -> dict[str, dict]:
    """逐臂汇总(中位 | p90);轨迹类取终值/最低 hp,计数类取合计。"""

    def _med_p90(vals: list[float]) -> tuple[float, float]:
        if not vals:
            return float('nan'), float('nan')
        ordered = sorted(vals)
        p90 = ordered[min(int(len(ordered) * 0.9), len(ordered) - 1)]
        return float(statistics.median(ordered)), float(p90)

    out: dict[str, dict] = {}
    for arm in _ARMS:
        rows = [per[arm] for per in games.values()]
        final_gold, _ = _med_p90([float(r.gold_traj[-1])
                                  for r in rows if r.gold_traj])
        min_hp, _ = _med_p90([float(min(r.hp_traj or [0])) for r in rows])
        out[arm] = {
            'n': len(rows),
            'final_gold_median': final_gold,
            'min_hp_median': min_hp,
            'counters': {key: sum(r.counter(key) for r in rows)
                         for key in CARRIER_COUNTER_KEYS},
        }
    return out


def scan_s_reserve_reject_frames(ctx, monkeypatch: Any, tmp_path, *,
                                 seeds, node_sequence: list[str],
                                 initial_gold: int = 30):
    """种子窗扫描首个 s_reserve 拒帧局(接线锁用;返回 (seed, stats) 或
    None=窗口内零拒帧,调用方按采样缺陷扩窗)。"""
    games = run_ab_games(ctx, monkeypatch, tmp_path, seeds,
                         arms=('variant',), node_sequence=node_sequence,
                         initial_gold=initial_gold)
    for seed in sorted(games):
        stats = games[seed]['variant']
        if stats.counter('m6_s_reserve_reject') > 0:
            return seed, stats
    return None
