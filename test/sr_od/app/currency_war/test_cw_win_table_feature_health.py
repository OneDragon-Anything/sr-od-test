# -*- coding: utf-8 -*-
"""批38 新检查 check_win_train_table_feature_health 的 sr-od-test 锁。

来源:压测官批38(报告 sim_压测_批38/);变异探针 M1-M3 由压测官
当场自检(禁零方差分支/禁 tier 门/禁标签断裂 → 对应锁必炸)。
覆盖:零方差红/tier 覆盖红/标签断裂红/全特征健康绿/空表不辖/
相关系数披露不判红。
"""
from __future__ import annotations


from sr_od.application.currency_war.sim.checks.corpus import check_win_train_table_feature_health as chk


def _row(killed: bool, i: int = 0, equip: int | None = None,
         tier: int | None = None) -> dict:
    """构造训练表行;默认各特征随 i 变化(避免夹具自身零方差)。"""
    return {
        'char_count': 3 + i % 3, 'star_sum': 4 + i % 4,
        'equip_count': i % 2 if equip is None else equip,
        'total_cost': 6 + i % 5,
        'max_tier': 1 + i % 2 if tier is None else tier,
        'killed': killed,
    }


class TestWinTrainTableFeatureHealth:
    def test_zero_variance_feature_violation(self) -> None:
        """equip_count 全 0(零方差)→ 红,且 detail 点名特征。"""
        rows = [_row(killed=b, i=i, equip=0, tier=t) for i, (b, t) in
                enumerate([(True, 2), (False, 1), (True, 2), (False, 2)])]
        r = chk(rows)
        assert r['violations'] == 1
        assert 'equip_count' in r['detail'][0] and '零方差' in r['detail'][0]

    def test_tier_coverage_gate_violation(self) -> None:
        """max_tier>=2 样本 <3 → 覆盖门红(其余特征健康,恰 1 红)。"""
        rows = [_row(killed=b, i=i, tier=t) for i, (b, t) in
                enumerate([(True, 1), (False, 1), (True, 2), (False, 1)])]
        r = chk(rows)
        assert r['violations'] == 1
        assert 'max_tier>=2' in r['detail'][0]

    def test_bad_label_schema_violation(self) -> None:
        """killed 非 bool 行 → 标签断裂红。"""
        rows = [_row(killed=True, i=0), _row(killed=False, i=1),
                {**_row(killed=True, i=2), 'killed': None},
                _row(killed=False, i=3)]
        r = chk(rows)
        assert any('killed' in v and '非 bool' in v for v in r['detail'])

    def test_healthy_table_green(self) -> None:
        """特征有方差 + tier>=2 样本 >=3 → 0 红。"""
        rows = [_row(killed=bool(i % 2), i=i) for i in range(6)]
        assert chk(rows)['violations'] == 0

    def test_empty_rows_not_governed(self) -> None:
        """空表 → 不辖 0 红。"""
        r = chk([])
        assert r['violations'] == 0
        assert r['rows'] == 0

    def test_correlation_disclosed_not_red(self) -> None:
        """相关系数近零/负号只披露不判红(健康特征 + 零相关 → 绿)。"""
        rows = [_row(killed=bool(i % 2), i=i, equip=i % 3)
                for i in range(6)]
        r = chk(rows)
        assert r['violations'] == 0
        assert r['features']['total_cost']['r_with_killed'] is not None
