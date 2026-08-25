"""W160 停机事故修复锁:变体模板机制(load_avatar_templates raw_*.png + identify 剥 #)。

事故链(2026-08-26 run_20260826_022811):商店卡「开拓者·欢愉」玩家名遮挡卡名
→ SIFT 唯一通道,但图鉴 art 对商店卡立绘仅 5 内点(min_inliers=10)→ 停机钩子
触发。修法=变体模板(现场裁图 raw_shop.png 同目录)+ 键 #k 剥离 + 同 cid 变体
不构成歧义。
"""
import numpy as np
import pytest
from cv2.typing import MatLike
from pathlib import Path

from sr_od.application.currency_war.currency_war_char_id import (
    identify_character,
    load_avatar_templates,
)


def _make_png(path: Path, seed: int) -> None:
    """生成确定性测试图(带角点特征,非纯色)。"""
    rng = np.random.default_rng(seed)
    img = (rng.random((120, 120, 3)) * 255).astype('uint8')
    import cv2
    cv2.imencode('.png', img)[1].tofile(str(path))


@pytest.fixture
def tpl_dir(tmp_path: Path) -> Path:
    d = tmp_path / '角色A'
    d.mkdir()
    _make_png(d / 'raw.png', seed=1)        # 主模板(图鉴 art)
    _make_png(d / 'raw_shop.png', seed=2)   # 变体(现场 art,与主不同)
    (tmp_path / '角色B').mkdir()
    _make_png(tmp_path / '角色B' / 'raw.png', seed=3)
    _make_png(tmp_path / '角色A' / 'raw_bak_plaza.png', seed=9)  # 备份:不应进库
    return tmp_path


def test_variant_templates_loaded_and_bak_excluded(tpl_dir: Path) -> None:
    t = load_avatar_templates(tpl_dir)
    keys = sorted(t)
    assert keys == ['角色A', '角色A#1', '角色B']   # bak 不进库,变体带 #1


def test_identify_returns_base_cid_for_variant_match(tpl_dir: Path) -> None:
    t = load_avatar_templates(tpl_dir)
    import cv2
    # 用变体模板原图(角色A#1 的 gray)做现场帧:应命中且返回裸 cid
    slot: MatLike = cv2.cvtColor(t['角色A#1'][0], cv2.COLOR_GRAY2RGB)
    cid, inliers = identify_character(slot, t)
    assert cid == '角色A'
    assert inliers >= 10


def test_identify_same_cid_variants_not_ambiguous(tpl_dir: Path) -> None:
    """同 cid 两变体在 top2(互为最强匹配)不判歧义——返回 base。"""
    t = load_avatar_templates(tpl_dir)
    import cv2
    # 构造一半主模板一半变体的拼接帧:两者都强 → 若按歧义逻辑会 None
    g1, g2 = t['角色A'][0], t['角色A#1'][0]
    mixed = cv2.vconcat([g1[:60], g2[60:]])
    slot = cv2.cvtColor(mixed, cv2.COLOR_GRAY2RGB)
    cid, _ = identify_character(slot, t, min_inliers=5)
    assert cid == '角色A'
