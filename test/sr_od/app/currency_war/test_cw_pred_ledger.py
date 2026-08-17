"""cw_pred_ledger(40 号预测台账)v0 测试:J0 自洽锚 + 对账/分区/回归语义。"""
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_pred_ledger import (  # noqa: E402
    FidelityMap,
    Prediction,
    reconcile,
    region_of,
    residual_regression,
)


def _mk_preds(n=40, seed=7, lo=None, hi=None) -> list[Prediction]:
    """n 条 income/node 点预测(值域 ~5-6)。"""
    rng = random.Random(seed)
    preds = []
    for i in range(n):
        p = 5.0 + rng.random()
        preds.append(Prediction('r', i + 1, 'income/node', point=p, lo=lo, hi=hi))
    return preds, rng


def test_reconcile_point_errors() -> None:
    """点预测:误差 = actual − point;缺实现值跳过。"""
    preds = [Prediction('r', 1, 'income/node', point=5.0),
             Prediction('r', 2, 'income/node', point=6.0),
             Prediction('r', 3, 'income/node', point=9.0)]   # 无实现值 → 跳过
    actuals = {('r', 1): {'income/node': 7.0}, ('r', 2): {'income/node': 6.0}}
    scored = reconcile(preds, actuals)
    assert len(scored) == 2
    assert scored[0].error == 2.0 and scored[1].error == 0.0


def test_reconcile_interval_hit() -> None:
    """区间预测:命中判定独立于点误差。"""
    preds = [Prediction('r', 1, 'hp/drop', point=10.0, lo=5.0, hi=15.0),
             Prediction('r', 2, 'hp/drop', point=10.0, lo=5.0, hi=12.0)]
    actuals = {('r', 1): {'hp/drop': 12.0}, ('r', 2): {'hp/drop': 14.0}}
    scored = reconcile(preds, actuals)
    assert scored[0].in_interval is True
    assert scored[1].in_interval is False


def test_region_partition() -> None:
    """分区键 = 机制族×位面×等级档(三档)。"""
    assert region_of('hp/drop', 2, 4) == 'hp/drop|p2|early'
    assert region_of('hp/drop', 2, 7) == 'hp/drop|p2|mid'
    assert region_of('hp/drop', 3, 9) == 'hp/drop|p3|late'


def test_fidelity_map_aggregates() -> None:
    """分区聚合:mae/bias;dark = 应覆盖而 n=0。"""
    preds, _ = _mk_preds(20, seed=3)
    # 实现值 = 预测 − 2(模型高估 2 → bias=−2 系统可见)
    actuals = {('r', i + 1): {'income/node': p.point - 2.0} for i, p in enumerate(preds)}
    scored = reconcile(preds, actuals, level_of={('r', i + 1): 4 for i in range(20)})
    fm = FidelityMap()
    fm.update(scored)
    rep = fm.finalize()
    reg = 'income/node|p1|early'
    assert rep[reg]['n'] == 20
    assert abs(rep[reg]['bias'] - (-2.0)) < 1.5   # 系统性低估 −2 可见
    assert 'income/node|p3|late' in fm.dark_regions({'income/node|p1|early', 'income/node|p3|late'})


def test_j0_bias_detection() -> None:
    """J0 自洽锚切片:幅度错(实现恒高于预测 3)→ 分区 bias 同号显著(检出)。"""
    preds, _ = _mk_preds(30, seed=11)
    actuals = {('r', p.round_num): {'income/node': p.point + 3.0} for p in preds}
    scored = reconcile(preds, actuals)
    fm = FidelityMap()
    fm.update(scored)
    rep = fm.finalize()['income/node|p1|early']
    assert rep['bias'] > 1.5, f"幅度偏移未检出: bias={rep['bias']}"


def test_residual_regression_detects_coupling() -> None:
    """J0 切片:缺耦合项(残差随连胜线性增长)→ 回归显著提名。"""
    preds, _ = _mk_preds(30, seed=5)
    cov: dict[tuple[str, int], float] = {}
    actuals = {}
    for i, p in enumerate(preds):
        streak = i % 5   # 协变量:连胜 0-4
        actuals[('r', p.round_num)] = {'income/node': p.point + streak * 2.0}   # 残差=+2×streak
        cov[('r', p.round_num)] = float(streak)
    scored = reconcile(preds, actuals)
    nom = residual_regression(scored, cov)
    assert nom and nom[0][0] == 'income/node' and nom[0][1] > 1.0, f"耦合项未提名: {nom}"


def test_residual_regression_quiet_on_white_noise() -> None:
    """白噪残差 → 无显著提名(不误报)。"""
    rng = random.Random(2)
    preds, _ = _mk_preds(30, seed=9)
    cov, actuals = {}, {}
    for p in preds:
        cov[('r', p.round_num)] = float(p.round_num % 5)
        actuals[('r', p.round_num)] = {'income/node': p.point + rng.uniform(-0.3, 0.3)}
    scored = reconcile(preds, actuals)
    assert residual_regression(scored, cov) == []
