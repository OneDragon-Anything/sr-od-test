"""CW A/B 批驱动(T-122 载体;T-120 方案 §6.1「A/B 编排迁新 runner(测试仓)」)。

脱离 pytest 可跑(上下文自建,等价 test_context fixture 形状)。

用法(项目根):
    uv run python sr-od-test/tools/cw_ab_batch.py --seeds 24 --out \
        .debug/temp/currency_war/T-122-AB批 [--nodes 9]

产出 = <out>/ab_result.json + ab_result.md(同 seed 配对表 + 逐臂汇总)。
**A/B 无数值裁决权**(strategy-work §4):本脚本只产出配对读数,禁据此
定数值;两臂同环境指纹(env_version 同位),唯一差异 = P77 2★ 现货
比较子开关(基线臂测试侧关闭,生产代码零开关)。假环境直出 2★ 频率 =
校准层演练偏置(rules.SHOP_DIRECT_OUT_2STAR_P),频次读数非真值估计。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / 'src'))
sys.path.insert(0, str(_REPO / 'sr-od-test'))
sys.path.insert(0, str(_REPO))
# 注意:禁把 sr-od-test/test 加上 path——其下 sr_od/ 子树会遮蔽 src/sr_od
# (conftest 的 sr_od.config import 即炸);test 包经 sr-od-test 根导入。

DEFAULT_NODE_SEQUENCE: list[str] = ['battle', 'reward', 'battle', 'supply',
                                    'boss', 'battle', 'reward', 'battle',
                                    'boss']


def _build_context():
    """等价 ``test.conftest`` fixture 形状的上下文(is_debug/实例 99/
    init 短路 GH 代理,与 fixture 逐句同形)。"""
    from test.conftest import SrTestContext

    from one_dragon.envs.ghproxy_service import GhProxyService
    ctx = SrTestContext()
    ctx.env_config.is_debug = True
    ctx.current_instance_idx = 99
    _real_update_proxy = GhProxyService.update_proxy_url
    GhProxyService.update_proxy_url = lambda self: False  # type: ignore[method-assign]
    try:
        ctx.init_by_config()
    finally:
        GhProxyService.update_proxy_url = _real_update_proxy  # type: ignore[method-assign]
    ctx.load_instance_config()
    return ctx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', type=int, default=24)
    parser.add_argument('--nodes', type=int, default=9)
    parser.add_argument('--initial-gold', type=int, default=30)
    parser.add_argument('--out', type=str, required=True)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    node_sequence = (DEFAULT_NODE_SEQUENCE[:args.nodes]
                     if args.nodes <= len(DEFAULT_NODE_SEQUENCE)
                     else DEFAULT_NODE_SEQUENCE + ['battle'] * (args.nodes
                                                                - len(DEFAULT_NODE_SEQUENCE)))

    from fixtures.cw_ab import (
        MonkeyShim,
        paired_delta,
        run_ab_game,
        summarize,
    )

    ctx = _build_context()
    games = {}
    shim = MonkeyShim()
    from test.harness.fixture_controller import (
        enter_running_state,
        reset_running_state,
    )
    enter_running_state(ctx)
    try:
        for seed in range(args.seeds):
            per = {}
            for arm in ('baseline', 'variant'):
                per[arm] = run_ab_game(ctx, shim, out_dir, seed, arm,
                                       node_sequence=node_sequence,
                                       initial_gold=args.initial_gold,
                                       archive_dir_name=f'ab_{arm}_{seed}')
                shim.undo()
            games[seed] = per
            print(f'seed={seed} done '
                  f'(B spot2={per["variant"].counter("m2_stockpile_spot2_buy")}, '
                  f'A mismatch={per["baseline"].counter("m2_stockpile_star_mismatch")})',
                  flush=True)
    finally:
        reset_running_state(ctx, ctx.cw_match)
        shim.undo()

    import statistics

    def _med(vals):
        vals = [float(v) for v in vals if v is not None]
        return statistics.median(vals) if vals else None

    result = {
        'seeds': args.seeds,
        'node_sequence': node_sequence,
        'initial_gold': args.initial_gold,
        'env_fingerprint': games[0]['baseline'].env_fingerprint,
        'per_seed': {str(s): {a: {
            'rounds': st.rounds,
            'gold_traj': st.gold_traj,
            'hp_traj': st.hp_traj,
            'launched': st.launched,
            'counters': st.counters,
        } for a, st in per.items()} for s, per in games.items()},
        'paired_delta': {k: {str(s): v for s, v in d.items()}
                         for k, d in paired_delta(games).items()},
        'summarize': summarize(games),
        'median_final_gold': {a: _med([per[a].gold_traj[-1]
                                       for per in games.values()])
                              for a in ('baseline', 'variant')},
    }
    (out_dir / 'ab_result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')

    lines = ['# T-122 A/B 批结果(P77 缺口面装载;A/B 无数值裁决权)',
             '',
             f"- seeds={args.seeds} nodes={len(node_sequence)} "
             f"initial_gold={args.initial_gold}",
             f"- env={result['env_fingerprint']}",
             '', '## 逐 seed 配对(Δ = variant − baseline)', '',
             '| seed | A:spot2买 | B:spot2买 | A:star_mismatch | '
             'Δ终金 | Δ最低hp | B:s_reserve对价 |',
             '|---|---|---|---|---|---|---|']
    for s, per in sorted(games.items()):
        a, b = per['baseline'], per['variant']
        d_gold = b.gold_traj[-1] - a.gold_traj[-1]
        d_hp = min(b.hp_traj or [0]) - min(a.hp_traj or [0])
        lines.append(
            f"| {s} | {a.counter('m2_stockpile_spot2_buy')} "
            f"| {b.counter('m2_stockpile_spot2_buy')} "
            f"| {a.counter('m2_stockpile_star_mismatch')} "
            f"| {d_gold:+d} | {d_hp:+d} "
            f"| {b.counter('m6_s_reserve_remeet_frames_sum')} |")
    lines += ['', '## 逐臂汇总', '', '```json',
              json.dumps(result['summarize'], ensure_ascii=False, indent=1),
              '```', '']
    (out_dir / 'ab_result.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'written: {out_dir / "ab_result.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
