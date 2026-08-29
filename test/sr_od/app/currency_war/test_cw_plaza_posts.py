"""W495 Phase A:plaza 逐篇语料入库 + 影子模型特征面接入的锁测试。

出处(设计单一源):
- 语料 schema = ``tools/cw/gen_plaza_comps.py`` 模块 docstring「同源三产物」节
  (逐篇明细 cw_plaza_posts.py 为生成器产物,勿手编);
- 特征化/权重口径 = ``cw_win_model.plaza_post_features`` /
  ``plaza_sample_weight`` / ``plaza_prior_weights`` docstring
  (use 对数压缩 + 先验面份额配平,生存者偏差声明同处);
- 零漂移红线 = ``ShadowKilledModel.features`` 列集不变(W47 单一源锁延续);
  ``cw_plaza_comps`` 聚合 schema 向后兼容(n>=5 生成器不变式,非数值锁)。
"""
from __future__ import annotations

import sys
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from sr_od.application.currency_war.data.cw_plaza_comps import (
    PLAZA_CARRY_CLUSTERS,
    PLAZA_GLOBAL,
    cluster_by_carry,
    default_star_goal,
    early_transition_pool,
)
from sr_od.application.currency_war.data.cw_plaza_posts import (
    PLAZA_POSTS,
    PlazaPost,
    post_by_id,
)
from sr_od.application.currency_war.cw_win_features import (
    features_from_deployed,
)
from sr_od.application.currency_war.cw_win_model import (
    PLAZA_BASE_WEIGHT,
    ShadowKilledModel,
    plaza_post_features,
    plaza_prior_weights,
    plaza_sample_weight,
)

REPO = Path(__file__).resolve().parents[5]


# --- 生成器产物 schema 锁(逐篇语料,784 篇) --------------------------------

def test_corpus_schema_and_uniqueness() -> None:
    """逐篇语料不变式(生成器过滤与去重的产物契约):
    帖 id 唯一、每篇 >=1 单位且 >=1 carry、星级 1-3、pos 合法、use >=0。"""
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


def test_corpus_field_arity() -> None:
    """units 五元组 / equips 二元组形状锁(特征化消费方按位解包)。"""
    p = PLAZA_POSTS[0]
    for u in p.units:
        assert len(u) == 5
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
    from sr_od.application.currency_war.cw_win_model import PLAZA_PRIOR_FACE_N
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
    early_transition_pool / default_star_goal 不因三产物化而破;
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
    assert default_star_goal(3) == 3
    assert default_star_goal(4) == 2


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
