# -*- coding: utf-8 -*-
"""ADR-0269 ``is_prep_like_frame`` 两段式测试(局72 伙伴误拖实锤锁)。

两段式:第一段逐屏遍历 ``UPPER_SCREENS``(上层画面/弹窗),任一命中 → False;
全部未命中 → 第二段判备战/开商店双屏。**必须逐屏单调用**——合并成一次
get_match_screen_name(全名单+备战)按注册序返首个命中,伙伴帧备战照样先中
(对抗审查轴①硬伤)。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


class _FakeMatcher:
    """get_match_screen_name 替身:hits 集合内的屏名命中,否则 None;记录调用序。"""

    def __init__(self, hits: set[str]) -> None:
        self.hits = hits
        self.calls: list[list[str]] = []

    def __call__(self, *, ctx, screen, screen_name_list, crop_first):  # noqa: ANN001 ANN003
        self.calls.append(list(screen_name_list))
        for name in screen_name_list:
            if name in self.hits:
                return name
        return None


@pytest.fixture
def matcher_env(monkeypatch):
    from one_dragon.base.screen import screen_utils
    from sr_od.application.currency_war.kernel import cw_obs_core
    fm = _FakeMatcher(set())
    monkeypatch.setattr(screen_utils, 'get_match_screen_name', fm)
    return cw_obs_core, fm


def _run(mod):
    ctx = object()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    return mod.is_prep_like_frame(ctx, screen)


def test_upper_hit_returns_false(matcher_env) -> None:
    """上层屏命中(如 选择伙伴)→ False,且命中即短路(不再判备战)。"""
    mod, fm = matcher_env
    fm.hits = {'货币战争-选择伙伴'}
    assert _run(mod) is False
    assert ['货币战争-选择伙伴'] in fm.calls
    # 第二段(备战/开商店,双元素调用)未发生——命中即短路:
    assert not any(len(c) == 2 for c in fm.calls)


def test_upper_miss_prep_hit_returns_true(matcher_env) -> None:
    """上层全未命中 + 备战命中 → True。"""
    mod, fm = matcher_env
    fm.hits = {'货币战争-备战'}
    assert _run(mod) is True
    # 先逐个判完所有上层屏,再判备战双屏(两段显式分离)
    assert len(fm.calls) == len(mod.UPPER_SCREENS) + 1
    assert all(len(c) == 1 for c in fm.calls[:-1])
    assert fm.calls[-1] == ['货币战争-备战', '货币战争-备战-开商店']


def test_all_miss_returns_false(matcher_env) -> None:
    """上层与备战/开商店全未命中(过渡/动画帧)→ False。"""
    mod, fm = matcher_env
    fm.hits = set()
    assert _run(mod) is False


def test_shop_open_returns_true(matcher_env) -> None:
    """开商店屏(第二段子态)→ True。"""
    mod, fm = matcher_env
    fm.hits = {'货币战争-备战-开商店'}
    assert _run(mod) is True


def test_upper_screens_names_registered() -> None:
    """UPPER_SCREENS 的每个 screen_name 都真实存在于 screen_info yml
    (防手写错别字静默失配——名单名错 = 该上层屏永不命中)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    repo_root = Path(__file__).resolve().parents[5]
    si_dir = repo_root / 'assets' / 'game_data' / 'screen_info'
    yml_names: set[str] = set()
    for yml in si_dir.glob('*.yml'):
        for line in yml.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('screen_name:'):
                yml_names.add(line.split(':', 1)[1].strip())
                break
    for name in cw_obs_core.UPPER_SCREENS:
        assert name in yml_names, f'UPPER_SCREENS 名 {name!r} 未在 screen_info 注册'


def test_mid_interest_floor_removed() -> None:
    """ADR-0270 死门删除:src 全仓无 _MID_INTEREST_FLOOR 引用残留。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    repo_root = Path(__file__).resolve().parents[5]
    src_dir = repo_root / 'src'
    hits = [p for p in src_dir.rglob('*.py')
            if '_MID_INTEREST_FLOOR' in p.read_text(encoding='utf-8')]
    assert hits == [], f'残留引用: {hits}'
