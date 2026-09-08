# -*- coding: utf-8 -*-
"""test_cw_screens_ops 主题锁(结构合并批;拼接疤痕已收敛为单一顶层导入)。

成员(原文件 docstring 语义索引):
- test_handle_supply_sphere: test_handle_supply_sphere.py
- test_settlement_recognizer: test_settlement_recognizer.py
- test_interrupt_dialog_screen: test_interrupt_dialog_screen.py —— 真阳性锁与
  父屏无碰撞锁的语义现由中央归档库自动扫描承载(超集):
  test/sr_od/screen_state/test_get_match_screen_name/test_id_mark.py 对
  screens/货币战争-中断挑战弹窗/open.webp 逐帧做「自家 id_mark 真阳性 +
  全画面碰撞」双检;本文件仅保留非 id_mark area 可命中锁。
- test_in_match_screen_layer: test_in_match_screen_layer.py
- plaza_posts: test_cw_plaza_posts.py
"""
from __future__ import annotations

import sys
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.screen.screen_utils import find_area_in_screen
from sr_od.application.currency_war.currency_war_app import CurrencyWarApp
from sr_od.application.currency_war.data.cw_plaza_comps import (
    PLAZA_CARRY_CLUSTERS,
    PLAZA_GLOBAL,
    cluster_by_carry,
    early_transition_pool,
)
from sr_od.application.currency_war.data.cw_plaza_posts import (
    PLAZA_POSTS,
    PlazaPost,
    post_by_id,
)
from sr_od.application.currency_war.kernel.cw_prep_expect import (
    material_value as _material_value,
)
from sr_od.application.currency_war.obs.cw_identity_obs import (
    read_reward_spheres,
    read_supply_boxes,
)
from sr_od.application.currency_war.obs.recognizers import (
    settlement_recognizer as mod,
)
from sr_od.application.currency_war.obs.recognizers.settlement_recognizer import (
    SettlementRecognizer,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply import (
    CwScreenSupply,
)
from sr_od.application.currency_war.telemetry.cw_win_features import (
    features_from_deployed,
)
from sr_od.application.currency_war.telemetry.cw_win_model import (
    PLAZA_BASE_WEIGHT,
    ShadowKilledModel,
    plaza_post_features,
    plaza_prior_weights,
    plaza_sample_weight,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

REPO = Path(__file__).resolve().parents[5]


# ==================== test_handle_supply_sphere ====================


def test_material_value_table() -> None:
    """合成材料通用性表:生命之花(7 配方)最高,幸运星(3)低,未知 0。"""
    assert _material_value('生命之花') == 7
    assert _material_value('轮滑鞋') == 6
    assert _material_value('未知装备') == 0


def test_fixture_reads_spheres_and_box(test_context: SrTestContext) -> None:
    """8 球帧无箱(时间线:箱由后续球掉落);5 球帧球+箱同帧共存,两 reader 互不干扰。"""
    if not test_context.has_screen('货币战争-备战', 'reward_spheres_8'):
        pytest.skip('fixture 缺:reward_spheres_8.webp')
    img = test_context.load_screen('货币战争-备战', 'reward_spheres_8')
    assert len(read_reward_spheres(test_context, img)) == 8
    assert read_supply_boxes(test_context, img) == [], '8 球帧箱未出现(箱由后续球掉落)'
    if not test_context.has_screen('货币战争-备战', 'reward_spheres_5'):
        pytest.skip('fixture 缺:reward_spheres_5.webp')
    img5 = test_context.load_screen('货币战争-备战', 'reward_spheres_5')
    spheres5 = read_reward_spheres(test_context, img5)
    boxes5 = read_supply_boxes(test_context, img5)
    assert len(spheres5) == 5 and [s for s, _p in boxes5] == [1], '5 球帧:球 5 + 箱槽1 共存'


def test_pick_card_fallback_by_material_value(test_context: SrTestContext) -> None:
    """选卡回落路径锁:无 cw_match(局外)时按材料通用性选卡(生命之花 7 >
    轮滑鞋 6),空卡列表返 None。key_equips 命中/策略打分路径需 cw_match
    在场(pick_box_card 前置分支),不在本锁断言面。"""
    op = CwScreenSupply(test_context)
    assert op._pick_card(['轮滑鞋', '生命之花', '幸运星']) == '生命之花'
    assert op._pick_card([]) is None


# ==================== test_settlement_recognizer ====================


def _ctx_with_ocr(ocr_texts: list[str]) -> MagicMock:
    """构造 mock ctx:ocr_service.get_ocr_result_list 返回给定文本(data 字段)。"""
    ctx = MagicMock()
    ctx.ocr_service.get_ocr_result_list.return_value = [MagicMock(data=t) for t in ocr_texts]
    return ctx


def test_screen_name_matches_settlement() -> None:
    """recognizer 注册的 screen_name = '货币战争-结算'(与 screen_info 一致)。"""
    assert SettlementRecognizer.screen_name == '货币战争-结算'


@pytest.mark.parametrize(
    'ocr_texts,parsed_hp,expected',
    [
        (['挑战结束', '小队生命值71', '继续挑战'], 71,
         {'hp_after': 71, 'is_failed': False}),
        (['挑战失败', '继续挑战'], None,
         {'hp_after': 0, 'is_failed': True}),
        (['挑战结束', '继续挑战'], None,
         {'hp_after': None, 'is_failed': False}),
    ],
    ids=['nonfail_hp_parsed', 'failed_screen_ground_truth_zero',
         'nonfail_hp_unreadable_none'],
)
def test_recognize_hp_branches(monkeypatch, ocr_texts: list[str],
                               parsed_hp: int | None,
                               expected: dict) -> None:
    """recognize 三分支同形体参数化(断言面逐 case 同拆前单测):
    - nonfail_hp_parsed:parse_settlement_hp 读到 71 → hp_after=71,is_failed=False;
    - failed_screen_ground_truth_zero:失败屏(「挑战失败」)parse 读不到
      → hp_after=0(团灭 ground truth,is_failed 由失败文案判定);
    - nonfail_hp_unreadable_none:非失败屏 parse 读不到 → hp_after=None(不硬塞)。"""
    monkeypatch.setattr(mod, 'parse_settlement_hp', lambda texts: parsed_hp)
    ctx = _ctx_with_ocr(ocr_texts)

    out = SettlementRecognizer().recognize(ctx, MagicMock(), MagicMock())
    assert out == expected


def test_does_not_import_session_based_reader() -> None:
    """并发安全墓碑:模块不导入需 plane/round(从 session)的 read_round_outcome。"""
    assert not hasattr(mod, 'read_round_outcome'), '不得复用需 session plane/round 的 read_round_outcome'


# ==================== test_interrupt_dialog_screen ====================


def _load(test_context: SrTestContext):
    if not test_context.has_screen('货币战争-中断挑战弹窗', 'open'):
        pytest.skip('fixture 缺:screens/货币战争-中断挑战弹窗/open.webp')
    return test_context.load_screen('货币战争-中断挑战弹窗', 'open')


def test_interrupt_dialog_areas(test_context: SrTestContext) -> None:
    """按钮/只读 area 在 fixture 上可命中(1g 分支点按钮-关闭的前提);
    真阳性/父屏无碰撞由 test_id_mark 中央归档库扫描承载(见文件头)。"""
    img = _load(test_context)
    si = test_context.screen_loader.get_screen('货币战争-中断挑战弹窗')
    for name in ('按钮-暂时离开', '文本-小队生命值'):
        area = next((a for a in si.area_list if a.area_name == name), None)
        assert area is not None, f'area 缺:{name}'
        # 文本-小队生命值 = 图标(❤)紧邻数值:全图 OCR 把图标+数字并成一个框,无法按区域
        # 切分(crop_first=False 语义,见 OcrService 类 docstring 缺点)→ 该查询显式走
        # crop_first=True(先裁剪再 OCR,「从连续文本中只提取特定区域」的合法场景)。
        assert find_area_in_screen(
            test_context, img, area, crop_first=(name == '文本-小队生命值'),
        ).value == 1, (
            f'area 应命中:{name}')


# ==================== test_in_match_screen_layer ====================


class _FakeScreenInfo:
    def __init__(self, name: str):
        self.screen_name = name


def test_in_match_screen_names_filters_lobby_states() -> None:
    """屏名过滤:大厅态排除、对局态纳入、前缀外不入。"""
    infos = [_FakeScreenInfo(n) for n in (
        '货币战争-大厅', '货币战争-模式选择', '货币战争-攻略列表',
        '货币战争-备战', '货币战争-投资策略', '货币战争-挑战失败',
        '货币战争-结算', '模拟宇宙--index', '星际列车')]
    got = CurrencyWarApp.in_match_screen_names(infos)
    assert '货币战争-大厅' not in got
    assert '货币战争-模式选择' not in got
    assert '货币战争-攻略列表' not in got
    assert '货币战争-备战' in got
    assert '货币战争-投资策略' in got
    assert '货币战争-挑战失败' in got
    # 前缀外判定面:输入在场的两个非 货币战争- 前缀名都不得入列
    assert '模拟宇宙--index' not in got
    assert '星际列车' not in got


def test_in_match_screen_names_auto_includes_new_screen() -> None:
    """新对局画面建档(带前缀)自动进列表——治本判据(M54 类漏判消除)。"""
    infos = [_FakeScreenInfo('货币战争-未来新屏')]
    assert CurrencyWarApp.in_match_screen_names(infos) == ['货币战争-未来新屏']


# 白名单排除登记项:屏名带 货币战争- 前缀但语义非对局屏。被前缀自动收录机制
# 收进对局屏集的后果 = 弹窗帧被误判「已在对局中」→ 入口链跳过 enter/start
# 直交 cw_loop(停机/卡死)。逐项事故出处见各 case 注释;移除对应排除行 =
# 对应 case 红。
_POPUP_EXCLUSION_CASES = [
    # 列车补给弹窗:match2 实锤(2026-08-31)——弹窗帧误判对局中 → 未知态钩子 33s 停机。
    '货币战争-列车补给弹窗',
    # 星琼详情:T-98 事故(ADR-0574)——模态详情弹窗在场即误判对局中,卡死换姿势复发。
    '货币战争-星琼详情',
    # 星徽详情:已建档同族「标题+X」详情弹窗(currency_war_star_badge_detail.yml),
    # 同族泛化待办,先行入清单防复发(方案审 F3;ADR-0574)。
    '货币战争-星徽详情',
    # 积分奖励:入口链 3b 分支处理的局末奖励页(cw_entry_start 一键领取+关闭),
    # 语义非对局屏(方案审 F3)。
    '货币战争-积分奖励',
]


@pytest.mark.parametrize('popup', _POPUP_EXCLUSION_CASES)
def test_in_match_screen_names_excludes_non_match_popups(popup: str) -> None:
    """白名单排除锁(逐项出处见 _POPUP_EXCLUSION_CASES 注释)。"""
    assert CurrencyWarApp.in_match_screen_names([_FakeScreenInfo(popup)]) == [], (
        f'{popup} 是非对局屏,不得进对局屏集(否则弹窗帧被误判对局中)'
    )


def test_train_supply_popup_fixture_not_in_match(test_context: SrTestContext) -> None:
    """大世界+弹窗真帧:不得被判成对局中态(match2 误路由场景回归)。"""
    from one_dragon.base.screen.screen_utils import get_match_screen_name

    if not test_context.has_screen('货币战争-列车补给弹窗', '今日未领取'):
        pytest.skip('fixture 缺:货币战争-列车补给弹窗/今日未领取')
    screens = CurrencyWarApp.in_match_screen_names(test_context.screen_loader.screen_info_list)
    img = test_context.load_screen('货币战争-列车补给弹窗', '今日未领取')
    hit = get_match_screen_name(test_context, img, screen_name_list=screens)
    assert hit is None, (
        f'弹窗真帧被误判对局屏 {hit}(入局流会被误路由交 cw_loop 停机)'
    )


def test_jade_detail_popup_fixture_not_in_match(test_context: SrTestContext) -> None:
    """大世界+星琼详情弹窗真帧:不得被判成对局中态(T-98 误路由场景回归)。"""
    from one_dragon.base.screen.screen_utils import get_match_screen_name

    if not test_context.has_screen('货币战争-星琼详情', 'default'):
        pytest.skip('fixture 缺:货币战争-星琼详情/default')
    screens = CurrencyWarApp.in_match_screen_names(test_context.screen_loader.screen_info_list)
    img = test_context.load_screen('货币战争-星琼详情', 'default')
    hit = get_match_screen_name(test_context, img, screen_name_list=screens)
    assert hit is None, (
        f'星琼详情弹窗真帧被误判对局屏 {hit}(T-98 卡死换姿势复发)'
    )


def test_in_match_fixture_states(test_context: SrTestContext) -> None:
    """实拍帧判定:挑战失败(对局终局)True;大厅 False。

    M42/M54 场景回归:战败态/结算态 app 重启时不再误走 enter 链。
    """
    from one_dragon.base.screen.screen_utils import get_match_screen_name
    ctx = test_context
    screens = CurrencyWarApp.in_match_screen_names(ctx.screen_loader.screen_info_list)
    assert '货币战争-挑战失败' in screens

    if not test_context.has_screen('货币战争-挑战失败', 'failed'):
        pytest.skip('fixture 缺:货币战争-挑战失败/failed')
    img = test_context.load_screen('货币战争-挑战失败', 'failed')
    # 画面匹配层直接判(绕开 app 实例化;_in_match 同源调用)
    assert get_match_screen_name(ctx, img, screen_name_list=screens) == '货币战争-挑战失败'

    if test_context.has_screen('货币战争-大厅', 'lobby'):
        lobby = test_context.load_screen('货币战争-大厅', 'lobby')
        lobby_hit = get_match_screen_name(ctx, lobby, screen_name_list=screens)
        assert lobby_hit is None, f'大厅帧不应命中对局屏,实命中 {lobby_hit}'


# ==================== plaza_posts ====================


# --- 生成器产物 schema 锁(逐篇语料,784 篇) --------------------------------

def test_corpus_schema_and_uniqueness() -> None:
    """逐篇语料不变式(生成器过滤与去重的产物契约):
    帖 id 唯一、每篇 >=1 单位且 >=1 carry、星级 1-3、pos 合法、use >=0;
    units 五元组 / equips 二元组按消费方位解包逐篇校验(特征化消费方按位解包)。"""
    assert len(PLAZA_POSTS) >= 700
    ids = [p.post_id for p in PLAZA_POSTS]
    assert len(ids) == len(set(ids)) == len(post_by_id())
    for p in PLAZA_POSTS:
        assert p.post_id
        assert p.use >= 0
        assert p.carries, f'无 carry: {p.post_id}'
        assert p.units
        for name, star, cost, pos, is_carry in p.units:
            assert 1 <= star <= 3
            assert cost >= 0
            assert pos in ('front', 'back')
            assert isinstance(is_carry, bool)
            assert name
        for name, eqs in p.equips:
            assert name
            assert all(e for e in eqs)


# --- 特征化(逐篇 → 胜率模型特征行) -----------------------------------------


def _post(use: int = 100) -> PlazaPost:
    return PlazaPost(
        post_id='t1', use=use, carries=('景元',),
        units=(('景元', 3, 5, 'front', True),
               ('艾丝妲', 2, 2, 'back', False),
               ('未注册角色', 1, 0, 'back', False)),
        equips=(('景元', ('火力风暴潮',)),),
        traits=('仙舟',), augs=(), portals=(),
        labels=('7级搜牌',), early=('艾丝妲',),
        craft_first='山贼弯刀', basic_first='')


def test_post_features_align_deployed_schema() -> None:
    """特征行 = features_from_deployed 全量列 + 引擎派生列 + plaza 附加列;
    deploy 口径对齐(char_count/装备计数/注册表外角色披露)。"""
    f = plaza_post_features(_post())
    base = features_from_deployed([
        {'char_id': '景元', 'star': 3, 'equips': ['火力风暴潮']},
        {'char_id': '艾丝妲', 'star': 2, 'equips': []},
        {'char_id': '未注册角色', 'star': 1, 'equips': []},
    ])
    for k, v in base.items():
        assert f[k] == v, k
    assert f['char_count'] == 3
    assert f['equip_count'] == 1
    assert f['unknown_char_count'] == 1
    assert f['n_carry'] == 1
    assert f['n_labels'] == 1 and f['n_portals'] == 0 and f['n_augs'] == 0
    assert f['plaza_use'] == 100


def test_sample_weight_log_compression_and_base() -> None:
    """权重口径:use=0 → 基础权重;use>0 → 1+ln(1+use)(头部帖压扁,
    出处=cw_win_model.plaza_sample_weight docstring 的份额论证)。"""
    import math
    assert plaza_sample_weight(0) == PLAZA_BASE_WEIGHT == 1.0
    assert plaza_sample_weight(-5) == PLAZA_BASE_WEIGHT  # 防御负值
    assert plaza_sample_weight(100) == pytest.approx(1 + math.log1p(100))
    # 头部帖(万级 use)压缩后 <=12,不会淹没遥测集(784 篇原值和 ~10^6)
    assert plaza_sample_weight(30000) < 12


def test_prior_weights_face_normalized() -> None:
    """先验面归一:权重和 = PLAZA_PRIOR_FACE_N × 遥测局数;行内排序
    (use 高 → 权重高)不变;空集/零权重退化原样返回。"""
    from sr_od.application.currency_war.telemetry.cw_win_model import PLAZA_PRIOR_FACE_N
    rows = [{'plaza_weight_raw': plaza_sample_weight(u)} for u in (0, 10, 1000)]
    w = plaza_prior_weights(rows, n_telemetry=123)
    assert sum(w) == pytest.approx(PLAZA_PRIOR_FACE_N * 123)
    assert w[0] < w[1] < w[2]
    assert plaza_prior_weights([], 10) == []
    zero = plaza_prior_weights([{'plaza_weight_raw': 0.0}], 10)
    assert zero == [0.0]


# --- 零漂移红线 --------------------------------------------------------------

def test_shadow_features_column_set_unchanged() -> None:
    """ShadowKilledModel.features 列集锁(W495 重构抽 _engine_columns 共用,
    输出键必须与重构前逐一相同)。"""
    deployed = [{'char_id': '藿藿', 'star': 2, 'equips': []},
                {'char_id': '丹恒·饮月', 'star': 1, 'equips': []}]
    feats = ShadowKilledModel().features(deployed)
    base_keys = set(features_from_deployed(deployed))
    assert set(feats) == base_keys | {'star2_plus', 'tier_sum', 'n_tier1',
                                      'n_tier2', 'engine_trio', 'dot_pieces',
                                      'seele'}


def test_plaza_comps_aggregate_schema_backward_compat() -> None:
    """聚合表向后兼容锁(既有消费者 cluster_by_carry /
    early_transition_pool 不因三产物化而破;
    n>=5 = 生成器 MIN_CLUSTER_N 不变式,非数值锁)。"""
    assert PLAZA_CARRY_CLUSTERS
    assert all(c.n_posts >= 5 for c in PLAZA_CARRY_CLUSTERS)
    expected = {'carry', 'n_posts', 'total_use', 'carry_star3_rate', 'traits',
                'units', 'carry_equips', 'augs', 'labels', 'portals'}
    assert {f.name for f in dc_fields(PLAZA_CARRY_CLUSTERS[0])} == expected
    by_carry = cluster_by_carry()
    assert set(by_carry) == {c.carry for c in PLAZA_CARRY_CLUSTERS}
    assert early_transition_pool()
    assert PLAZA_GLOBAL['n_posts'] == len(PLAZA_POSTS)  # 聚合/逐篇同源对账


# --- 生成器渲染 schema 锁(render_posts 产物可执行且结构正确) ----------------

def test_render_posts_exec_schema() -> None:
    """render_posts 输出可 exec 且 dataclass 结构/字段齐全(改渲染模板的锁)。"""
    sys.path.insert(0, str(REPO / 'tools' / 'cw'))
    import gen_plaza_comps
    rec = {
        'post_id': '12345', 'use': 7,
        'carries': ('景元',),
        'units_t': (('景元', 3, 5, 'front', True),),
        'equips_t': (('景元', ('火力风暴潮',)),),
        'traits_t': ('仙舟',), 'augs_t': (), 'portals_t': ('长线利好',),
        'labels_t': ('7级搜牌',), 'early_t': ('艾丝妲',),
        'craft_first': '山贼弯刀', 'basic_first': '锋利的牙',
    }
    code = gen_plaza_comps.render_posts('V4.4', [rec])
    ns: dict = {}
    exec(compile(code, '<render_posts>', 'exec'), ns)  # noqa: S102
    posts = ns['PLAZA_POSTS']
    assert len(posts) == 1
    p = posts[0]
    assert p.post_id == '12345' and p.use == 7
    assert p.units == (('景元', 3, 5, 'front', True),)
    assert p.equips == (('景元', ('火力风暴潮',)),)
    assert ns['post_by_id']()['12345'] is p
