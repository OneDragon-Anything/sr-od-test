"""A/B 载体装载锁(加载/切换/对照面 + 假环境 2★ 直出机制)。

设计出处 = 装载设计 ``.debug/temp/currency_war/T-122-装载设计.md`` §3;
载体 = ``fixtures/cw_ab.py``(T-120 方案 §6.1「A/B 编排迁新 runner(测试仓)」
的测试仓落位);环境侧 = merge_mechanics §2.6/§2.7 直出 2★ 机制实锤 +
频率「概率待实机调研」→ 假环境补机制、频率落校准层常量(演练偏置申报)。
慢锁(整局装配 ≥2s)入 slow_marks.txt。
"""
from __future__ import annotations

import random

import pytest
from fixtures.cw_fake_game import rules
from fixtures.cw_fake_game.fake_match import FakeMatch

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

_SCRIPT: list[str] = ['battle', 'reward', 'battle', 'supply', 'boss']


def _find_direct_out_seed(window: range = range(0, 80)) -> int:
    """探针:扫描种子窗返回首个直出 2★ 命中 seed(机制开火采样防护)。"""
    for seed in window:
        m = FakeMatch(seed=seed, node_sequence=['battle'])
        m.open_shop()
        if any((c.star or 1) >= 2 for c in m.state.shop):
            return seed
    pytest.fail('种子窗 0-79 零直出 2★(机制未开火或校准常量取值过小,复查)')


class TestFakeEnvDirectOuts:

    def test_env_version_history_pins_direct_out(self):
        """直出机制改变环境分布 ⇒ env_version 升位(跨版禁裸串比)。
        锁钉版本历史语义而非当前值(消移动靶:后续批合法升版不再破锁,
        当前值由升版批按锁纪律自辖):断言版本历史含直出 2★ 通道语义 +
        v6 合流沿革(v5 曾短暂挂直出单语义未出版,终值与语义 = 编排者
        二次裁决 2026-09-10);终值 ≥6 防回拨。两臂同指纹由载体锁另辖。"""
        import inspect
        import re

        from fixtures.cw_fake_game import fake_match
        src = inspect.getsource(fake_match)
        m = re.search(r'#: 假游戏规则层版本位.*?FAKE_GAME_ENV_VERSION',
                      src, re.S)
        assert m is not None, '版本历史注释块缺失(锚 = 常量定义前 #: 段)'
        history = m.group(0)
        assert '直出 2★ 通道' in history, '版本历史缺直出 2★ 通道语义'
        assert '合流' in history, '版本历史缺 v6 合流语义'
        assert 'v5' in history, '版本历史缺 v5 未出版沿革(防考古歧义)'
        assert fake_match.FAKE_GAME_ENV_VERSION >= 6, '版本位回拨(<6)'

    def test_calibration_constant_declared(self):
        """校准层常量在册且量纲合法:0 < p ≤ 0.1(演练偏置:取值使机制
        在批量局可观测;真值「概率待实机调研」(merge_mechanics §2.7
        零样本存档),禁把该速率下频次读成真值估计)。"""
        p = rules.SHOP_DIRECT_OUT_2STAR_P
        assert 0.0 < float(p) <= 0.1

    def test_upgrade_fn_pool_guard_and_badge_price(self):
        """升级函数(直调):池 <3 基础副本不升(2★ = 三副本,不足不发);
        命中形态 = star 2 + cost 3×roster 基价(徽章实付语义,与 live
        费用通道同形,merge_mechanics §2.6)。"""
        from fixtures.cw_fake_game.fake_match import _upgrade_direct_outs

        from sr_od.application.currency_war.kernel.cw_state import ShopCard
        name = next(n for n in CHARACTERS if CHARACTERS[n].cost == 3)
        base = ShopCard(x=0, name=name, cost=3, star=1)
        for s in range(200):
            out = _upgrade_direct_outs([base], random.Random(s), {name: 2})
            assert (out[0].star or 1) == 1, '池 <3 副本不得发 2★'
        hit = None
        for s in range(400):
            out = _upgrade_direct_outs([base], random.Random(s), {name: 9})
            if (out[0].star or 1) == 2:
                hit = out[0]
                assert hit.cost == 9, \
                    f'直出 2★ 价 {hit.cost} ≠ 3×基价(徽章实付语义)'
                break
        assert hit is not None, '400 受控 rng 零命中:常量取值或实现破缺'

    def test_direct_out_frame_badge_price(self):
        """e2e:命中帧店内 2★ 卡 cost == 3×roster 基价(观察链 ShopCard
        直出透传,策略侧金闸按徽章实付比较)。"""
        seed = _find_direct_out_seed()
        m = FakeMatch(seed=seed, node_sequence=['battle'])
        m.open_shop()
        for c in m.state.shop:
            if (c.star or 1) >= 2:
                assert c.cost == CHARACTERS[c.name].cost * 3, \
                    f'直出 2★ 价 {c.cost} 非 ×3 律'

    def test_same_seed_shop_bitwise_replay(self):
        """确定性契约(方案 §2.2):同 seed 两次开店牌面逐位相等
        (直出掷签吃主 rng 流,同 seed 可复现)。"""
        seed = _find_direct_out_seed()

        def _deal() -> list:
            m = FakeMatch(seed=seed, node_sequence=['battle'])
            m.open_shop()
            return [(c.x, c.name, c.cost, c.star) for c in m.state.shop]

        assert _deal() == _deal(), '同 seed 直出牌面不逐位相等(确定性破缺)'


class TestAbCarrier:

    def test_paired_two_seeds_structure_and_counterfactual(
            self, test_context, monkeypatch, tmp_path):
        """加载/对照面结构锁:2 seed × 2 臂可跑、两臂环境指纹相等
        (同环境配对前提)、基线臂零 spot2 计数(切换面反事实)、
        paired_delta 键集完整。臂间开火差异由 A/B 批(驱动脚本)承载,
        测试网不锁分布数值(纪律 8)。"""
        pytest.importorskip('fixtures.cw_ab')
        from fixtures.cw_ab import paired_delta, run_ab_games
        games = run_ab_games(test_context, monkeypatch, tmp_path,
                             seeds=(11, 23), node_sequence=_SCRIPT)
        assert set(games) == {11, 23}
        for per in games.values():
            assert set(per) == {'baseline', 'variant'}
            fp_a = per['baseline'].env_fingerprint
            fp_b = per['variant'].env_fingerprint
            assert fp_a == fp_b, '两臂环境指纹不等(配对前提破缺)'
            assert per['baseline'].counter('m2_stockpile_spot2_buy') == 0, \
                '基线臂比较子应已关闭(spot2 计数须恒零)'
        delta = paired_delta(games)
        for key in ('final_gold', 'min_hp', 'm2_stockpile_spot2_buy',
                    'm6_s_reserve_remeet_frames_sum'):
            assert key in delta, f'配对 Δ 缺指标 {key}'

    def test_same_seed_same_arm_deterministic(
            self, test_context, monkeypatch, tmp_path):
        """同 seed 同臂两次全程 → 计数器切片与金轨迹逐位相等
        (重放契约在 A/B 载体上的配对前提)。"""
        pytest.importorskip('fixtures.cw_ab')
        from fixtures.cw_ab import run_ab_game
        r1 = run_ab_game(test_context, monkeypatch, tmp_path, 11, 'variant',
                         node_sequence=_SCRIPT, archive_dir_name='abx_1')
        r2 = run_ab_game(test_context, monkeypatch, tmp_path, 11, 'variant',
                         node_sequence=_SCRIPT, archive_dir_name='abx_2')
        assert r1.gold_traj == r2.gold_traj
        assert r1.counters == r2.counters
