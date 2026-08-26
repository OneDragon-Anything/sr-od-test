# -*- coding: utf-8 -*-
"""W221(ADR-0398)行为锁:boss 节点定位 = 位置先验点击 + 详情条「首领」标签验证 + 徽章态分流。

背景(run 29/30 同夜实证,2026-08-26):
- **头像态**(run29/佩佩局):最右节点=红框 boss 头像,详情条大图标 SIFT 断层命中
  (run29 三位面 11/13/5)——已有锁见 test_cw_node_boss.py(佩佩局 fixture
  cw_plane_detail_nodes.png 最右 SIFT 巨鹿生物制药)= 本文件「双态锁」的头像态侧;
- **徽章态**(run30 位面1):最右节点=通用金色徽章(逐圆 SIFT 全拒,零假阳)、详情条=
  「首领节点」+通用描述,大图标=徽章 SIFT 未命中——**本屏无任何 boss 身份信息**。
  旧 op「SIFT 未命中→round_retry 重点」在徽章态确定性空转 12 retry 耗尽停机。

锁四件事:
1. 徽章态带内零假阳(9 圆全拒——位置先验仍指向真 boss 节点,缺的是身份);
2. 详情条类型名 OCR 可读出「首领」(定位验证锚,真实 OCR);
3. ``conclude_plane_boss`` 分流矩阵(头像态 record / 徽章态 skip / 标签异常 retry);
4. battle_loop 实采写 session **保位**(None 不滤——滤掉=位面错序回潮,ADR-0397 同病)。

fixture = cw_plane_detail_emblem_full.png(run30 位面1 现场帧,徽章态代表;
点最右圆后详情条显示「1-9 首领节点」即位置先验的反例帧内自证)。
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.cw_node_reader import (
    classify_node_row,
    load_boss_templates,
    load_node_type_templates,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_FIXTURE = Path(__file__).parent / 'cw_plane_detail_emblem_full.png'
_ASSETS = Path(cv2_utils.__file__).resolve().parents[3] / 'assets'   # 仓根 assets
_NODE_TPL_DIR = _ASSETS / 'game_data' / 'cw_node_types'
_BOSS_TPL_DIR = _ASSETS / 'template' / 'currency_war' / 'boss_avatar'
#: 位面详情节点带(与 screen_info「货币战争-位面详情/区域-节点条」一致;yml 单一源,测试兜底)
_PD_BAND_RECT = (385, 514, 1596, 661)


def _load_fixture_rgb() -> np.ndarray:
    img_bgr = cv2.imdecode(np.fromfile(str(_FIXTURE), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {_FIXTURE}'
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB


def test_emblem_band_zero_false_positive() -> None:
    """锁①:run30 徽章态带内 9 圆逐圆 SIFT 全拒(零假阳;身份缺失≠识别误报)。"""
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    assert len(bt) == 20, f'boss 模板库应 20 件(缺库会让全拒断言空过),得 {len(bt)}'
    img = _load_fixture_rgb()
    x1, y1, x2, y2 = _PD_BAND_RECT
    slots = classify_node_row(img[y1:y2, x1:x2], tpls, boss_templates=bt)
    assert len(slots) == 9, f'run30 位面1 带 9 圆,得 {len(slots)}'
    assert all(s.boss is None for s in slots), (
        f'徽章态带内不应有 boss 命中(得 {[s.boss for s in slots]})——假阳比缺数据危险'
    )


def test_emblem_detail_label_reads_boss(test_context: SrTestContext) -> None:
    """锁②:run30 帧详情条类型名 OCR 含「首领」(真实 OCR;定位验证锚)。"""
    from sr_od.application.currency_war.cw_obs_core import _area_rect
    from sr_od.application.currency_war.cw_observation import read_detail_node_type_label

    if _area_rect(test_context, '文本-节点类型名', '货币战争-位面详情') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    label = read_detail_node_type_label(test_context, _load_fixture_rgb())
    assert label is not None, '详情条类型名应可 OCR(锚缺失会让徽章态分流失效)'
    assert '首领' in label.replace(' ', ''), (
        f'点最右圆后详情条应显示首领节点类型,得 {label!r}(位置先验失效信号)'
    )


def test_conclude_plane_boss_matrix() -> None:
    """锁③:分流矩阵——头像态 record / 徽章态 skip(不 retry)/ 标签异常 retry。"""
    from sr_od.application.currency_war.operations.handlers.collect_plane_intel import (
        conclude_plane_boss,
    )

    # 头像态(run29 型):标签=首领 + SIFT 命中 → 记录真值
    assert conclude_plane_boss('首领节点', '深穹智械科技') == ('record', '深穹智械科技')
    # 徽章态(run30 型):标签=首领 + SIFT 未命中 → 记 None 跳过(**不得 retry 空转**)
    assert conclude_plane_boss('首领节点', None) == ('skip', None)
    assert conclude_plane_boss('首 领 节 点', None) == ('skip', None)   # OCR 空格容错
    # 标签未读出(过渡帧/OCR 失败)→ retry 等下帧(不得当徽章态误跳)
    act, _ = conclude_plane_boss(None, None)
    assert act == 'retry'
    act, _ = conclude_plane_boss('', '巨鹿生物制药')
    assert act == 'retry'
    # 点到的非首领节点(节点带误读/布局变)→ retry 兜底
    act, _ = conclude_plane_boss('奖励节点', None)
    assert act == 'retry'


def test_battle_loop_preserves_none_positions() -> None:
    """锁④:实采写 session 保位(None 不滤)——滤 None 会让后续位面名字左移错序
    (ADR-0397 修的「按序消费错位面」同病;旧形态 `[n for n in ... if n]` 禁回潮)。"""
    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert '[n for n in self.ctx.cw_plane_bosses if n]' not in src, (
        '实采列表滤 None 回潮(徽章态位面 None 被丢→位面错序)'
    )
    assert '_names = list(self.ctx.cw_plane_bosses)' in src, '实采应保位写 3 槽(None 原样)'


def test_boss_fit_tolerates_none_entries() -> None:
    """锁④伴生:boss_fit 跳过 None 项(保位列表下游);全 None → None(无信息,
    与空表同形,动态权重剔除)——不得把 None 传进 normalize_boss_name 崩溃。"""
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY, boss_fit

    comp = COMP_LIBRARY[0]
    assert boss_fit(comp, [None, None, None]) is None
    full = boss_fit(comp, ['巨鹿生物制药', '增熵能源集团', '绘师家族产业'])
    holed = boss_fit(comp, [None, '增熵能源集团', '绘师家族产业'])
    assert full == holed, 'None 位应被跳过而非改变其余 boss 的判定'
