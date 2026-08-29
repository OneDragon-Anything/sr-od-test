"""批㊲ 检查项锁:ADR-0306 Δ池扩容批对抗审计的回归资产。

覆盖三新检查 + 两处加固:
- ``check_delta_pool_poverty_selfconsistency``(贫困披露↔池内容
  双向结构对拍;变异杀:格式漂移/漏披露/过期披露/n 值不符);
- ``check_boss_rung_corpus_sample_gate``(boss rung 语料样本门;
  变异杀:killed 全 None 采集断裂);
- ``check_ab_verdict_claim`` 词表反转(变异杀:换措辞'首超'/
  'wins' 旧版绕过、新版必辖);
- ``check_paired_prefork_wave_identity`` 扩全波(变异杀:第二波
  篡改旧版漏检、新版必红)。

(check_boss_win_p_cache_freshness 已随 ADR-0308 废除:rung 外推
机制被 W31 节点胜率阶梯替换,无进程内缓存可查。)

数据边界:全部合成 dict/list 纯函数锁 + 真快照自洽(resolve_pool
产物,只读;不触 replay/不写 .debug)。来源实证见
``sim_压测_批㊲``。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.sim import pool as cw_sim
from sr_od.application.currency_war.data.cw_delta_pool_data import (
    META as SNAP_META,
)

from sr_od.application.currency_war.sim.checks.calib import check_ab_verdict_claim

from sr_od.application.currency_war.sim.checks.corpus import check_boss_rung_corpus_sample_gate, check_delta_pool_poverty_selfconsistency, check_paired_prefork_wave_identity

# --------------------------------------------------------------------
# check_delta_pool_poverty_selfconsistency
# --------------------------------------------------------------------

def _mini_pool() -> dict:
    """合成池:battle r0 富 / r2 薄 / r3 缺;boss 桶9 薄。"""
    return {
        'battle': {0: [-10] * 12, 2: [-7] * 9},
        'boss': {9: [-20] * 2},
    }


def _mini_meta() -> dict:
    return {'bucket_poverty': [
        'battle:桶1(缺)', 'battle:桶2(n=9)', 'battle:桶3(缺)',
        'battle:桶4(缺)', 'boss:桶9(n=2)',
    ]}


def test_poverty_selfconsistency_real_snapshot_green() -> None:
    """真实快照(resolve_pool 产物)↔ META 双向自洽 = 0 违规
    (锁生成器 _poverty_list 与池内容同源;重生成后仍须自洽;
    ADR-0362:检查项辖 plane=1 视图,与批内 pool-level 检查同口径)。"""
    pm, _, _ = cw_sim.resolve_pool('snapshot')
    out = check_delta_pool_poverty_selfconsistency(
        cw_sim.plane_view(pm), SNAP_META)
    assert out['violations'] == 0, f'{out}'
    assert out['disclosed_n'] == out['pool_poor_n']


def test_poverty_selfconsistency_synthetic_green() -> None:
    out = check_delta_pool_poverty_selfconsistency(
        _mini_pool(), _mini_meta())
    assert out['violations'] == 0, f'{out}'


def test_poverty_selfconsistency_meta_none_skips() -> None:
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), None)
    assert out['violations'] == 0
    assert '不辖' in out['note']


def test_poverty_selfconsistency_empty_pool_skips() -> None:
    out = check_delta_pool_poverty_selfconsistency({}, _mini_meta())
    assert out['violations'] == 0


def test_poverty_selfconsistency_format_drift_flags() -> None:
    """变异杀①:格式漂移(全角括号/空格)→ 解析失败违规
    (旧 coverage 的字符串精确匹配下这是静默失配,批㊲ 攻击面)。"""
    drifted = {'bucket_poverty': ['battle:桶2(n=9)', 'battle:桶3(缺)',
                                  'battle:桶4(缺)',
                                  'boss:桶9(n=9)]']}   # 全角括号
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), drifted)
    assert out['violations'] >= 1
    assert any('不可解析' in v for v in out['detail'])


def test_poverty_selfconsistency_undisclosed_flags() -> None:
    """变异杀②:池贫困未披露(删 boss 披露行)→ 违规。"""
    meta = {'bucket_poverty': ['battle:桶2(n=9)', 'battle:桶3(缺)',
                               'battle:桶4(缺)']}
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), meta)
    assert out['violations'] >= 1
    assert any('未披露' in v for v in out['detail'])


def test_poverty_selfconsistency_stale_flags() -> None:
    """变异杀③:过期披露(池中不贫困的桶出现在披露)→ 违规。"""
    meta = _mini_meta()
    meta['bucket_poverty'] = list(meta['bucket_poverty']) + [
        'battle:桶0(n=9)']
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), meta)
    assert out['violations'] >= 1
    assert any('过期' in v for v in out['detail'])


def test_poverty_selfconsistency_n_mismatch_flags() -> None:
    """变异杀④:披露 n 值与池不符(池 n=8 披露 n=9)→ 违规。"""
    pool = _mini_pool()
    pool['battle'][2] = [-7] * 8
    out = check_delta_pool_poverty_selfconsistency(pool, _mini_meta())
    assert out['violations'] >= 1
    assert any('n 值' in v for v in out['detail'])


# --------------------------------------------------------------------
# (check_boss_win_p_cache_freshness 六锁已随 ADR-0308 删除——被检
#  机制 boss_win_p/_BOSS_WIN_P_EXTRAPOLATED 缓存已废弃,锁死码无义)
# --------------------------------------------------------------------

# --------------------------------------------------------------------
# check_boss_rung_corpus_sample_gate
# --------------------------------------------------------------------

def _boss_rows_b37() -> list[dict]:
    """批㊲ 探针实证形态(2026-08-25 语料 17 行):r0 0/5、
    r1 0/9+1None、r2 1/2。"""
    return (
        [{'rung': 0, 'killed': False}] * 5
        + [{'rung': 1, 'killed': False}] * 9
        + [{'rung': 1, 'killed': None}]
        + [{'rung': 2, 'killed': True}, {'rung': 2, 'killed': False}])


def test_boss_gate_b37_shape_green() -> None:
    out = check_boss_rung_corpus_sample_gate(_boss_rows_b37())
    assert out['violations'] == 0
    assert out['buckets']['1']['win_killed'] == 0.0
    assert out['buckets']['1']['killed_known'] == 9
    assert out['buckets']['2']['win_killed'] == 0.5
    assert out['rung3plus_exists'] is False
    # 样本门逐桶属性(批㉗ F6 known≥3):rung1 known=9 已就绪、
    # rung2 known=2 未就绪;批㊲ 反证针对 rung≥3 直拟合(缺桶)
    assert out['buckets']['1']['direct_fit_ready'] is True
    assert out['buckets']['2']['direct_fit_ready'] is False


def test_boss_gate_all_unknown_flags() -> None:
    """变异杀:killed 全 None(采集断裂)→ 违规。"""
    out = check_boss_rung_corpus_sample_gate(
        [{'rung': 1, 'killed': None}] * 5)
    assert out['violations'] == 1
    assert '采集断裂' in out['detail'][0]


def test_boss_gate_empty_skips() -> None:
    out = check_boss_rung_corpus_sample_gate([])
    assert out['violations'] == 0
    assert '不辖' in out['note']


def test_boss_gate_direct_fit_ready_tracks() -> None:
    """样本门追踪:known≥3 的桶标 direct_fit_ready(直拟合就绪)。"""
    rows = [{'rung': 3, 'killed': True}] * 2 + \
           [{'rung': 3, 'killed': False}] + \
           [{'rung': 2, 'killed': True}] * 3
    out = check_boss_rung_corpus_sample_gate(rows)
    assert out['buckets']['3']['direct_fit_ready'] is True
    assert out['buckets']['2']['direct_fit_ready'] is True
    assert out['rung3plus_exists'] is True


# --------------------------------------------------------------------
# check_ab_verdict_claim 词表反转(批㊲ 加固)
# --------------------------------------------------------------------

@pytest.mark.parametrize('claim', ['首超', 'wins', '更高', 'better', ''])
def test_verdict_claim_unknown_wording_now_flagged(claim: str) -> None:
    """批㊲ 攻击面锁:换措辞旧版绕过(词表命中才辖)→ 新版默认辖。
    n=30 + 带内差 → 至少 1 违规。"""
    out = check_ab_verdict_claim(3.0, 14.0, 30, claim)
    assert out['directional'] is True
    assert out['violations'] >= 1, (
        f'claim={claim!r} 绕过判罚面 = 词表反转回归')


@pytest.mark.parametrize('claim', ['noise', 'noise_band', 'tie', '平局',
                                   '持平', '无差异', 'parity'])
def test_verdict_claim_nondirectional_whitelist_still_exempt(claim: str
                                                             ) -> None:
    out = check_ab_verdict_claim(-3.0, 14.0, 30, claim)
    assert out['directional'] is False
    assert out['violations'] == 0


@pytest.mark.parametrize('claim', ['leads', 'behind', '领先', '落后'])
def test_verdict_claim_legacy_directional_words_still_flagged(claim: str
                                                              ) -> None:
    """旧方向词在反转后仍辖(回归,不因词表反转漏放)。"""
    out = check_ab_verdict_claim(-3.0, 14.0, 30, claim)
    assert out['directional'] is True
    assert out['violations'] >= 1


# --------------------------------------------------------------------
# check_paired_prefork_wave_identity 扩全波(批㊲ 加固)
# --------------------------------------------------------------------

def _row(rn: int, waves: list[list[str]],
         actions: list[dict] | None = None) -> dict:
    return {
        'round_num': rn,
        'sim': {'shop_waves': [{'cards': [{'name': n} for n in w]}
                               for w in waves]},
        'actions': actions or [],
    }


def test_prefork_full_wave_synthetic_green() -> None:
    """合成 green:两臂全波一致(含同轮刷新波)+ 动作 sig 一致 → 0。"""
    a = [[_row(1, [['青雀', '姬子'], ['三月七']],
               actions=[{'__type__': 'RefreshShop'}])],
         [_row(2, [['希儿']])]]
    b = [[_row(1, [['青雀', '姬子'], ['三月七']],
               actions=[{'__type__': 'RefreshShop'}])],
         [_row(2, [['希儿']])]]
    out = check_paired_prefork_wave_identity(a, b)
    assert out['violations'] == 0, f'{out}'


def test_prefork_second_wave_drift_now_flagged() -> None:
    """批㊲ 攻击面锁:同轮 wave0 一致、wave1(刷新波)不一致且动作
    sig 一致 → 旧版(只比首波)0 违规=漏检;新版必红。"""
    a = [[_row(1, [['青雀'], ['姬子', '三月七']],
               actions=[{'__type__': 'RefreshShop'}])],
         [_row(2, [['希儿']])]]
    b = [[_row(1, [['青雀'], ['希儿', '娜塔莎']],
               actions=[{'__type__': 'RefreshShop'}])],
         [_row(2, [['希儿']])]]
    out = check_paired_prefork_wave_identity(a, b)
    assert out['violations'] >= 1, (
        '第二波(刷新波)不一致未被捕获 = 全波扩展回归(旧版漏检面)')


def test_prefork_first_wave_drift_still_flagged() -> None:
    """回归:首波不一致(批㊱ 原判据)仍必红。"""
    a = [[_row(1, [['青雀'], ['姬子']],
               actions=[{'__type__': 'RefreshShop'}])]]
    b = [[_row(1, [['三月七'], ['姬子']],
               actions=[{'__type__': 'RefreshShop'}])]]
    out = check_paired_prefork_wave_identity(a, b)
    assert out['violations'] >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-q'])

