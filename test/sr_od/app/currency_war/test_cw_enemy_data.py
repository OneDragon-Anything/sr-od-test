"""cw_enemy_data(15 号敌情层 v0)测试:俗称归一/matchup 结构层/boss_fit 接通(ADR-0160)。"""
import pytest

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, boss_fit, get_comp
from sr_od.application.currency_war.data.cw_enemy_data import (
    boss_tags,
    matchup,
    normalize_boss_name,
)


def test_nickname_normalization():
    assert normalize_boss_name('剧目') == '造梦兄弟影业'
    assert normalize_boss_name('蕉研组') == '造梦互动娱乐'
    assert normalize_boss_name('造梦兄弟影业') == '造梦兄弟影业'   # 已规范原样
    assert normalize_boss_name('火线动力机甲') == '火线动力机甲'


def test_boss_fit_seam_now_hits():
    """接缝接通实证:希儿量子 countered=[剧目,蕉研组] vs plane_bosses 含 造梦兄弟影业 → 命中降分
    (旧:俗称 vs 规范名永命中不了,task#73 遗留)。"""
    seele = get_comp('希儿量子')
    hit = boss_fit(seele, ['造梦兄弟影业', '铁盾安保集团', '猎星资本'])
    no_hit = boss_fit(seele, ['火线动力机甲', '铁盾安保集团', '猎星资本'])
    assert hit is not None and hit < 0.5
    assert no_hit == 0.5   # boss 在但不利害此 comp(真实中性)


def test_matchup_structure_layer():
    """结构层:治疗队打 削治疗 boss(火线动力机甲)→ 克制降分 + reasons 可解释;
    群攻队打召唤 boss(银甲)→ 利好升分。"""
    s1, r1 = matchup(['治疗', '治疗护盾'], ['火线动力机甲'])
    assert s1 < 0.5 and any('克' in x for x in r1)
    s2, r2 = matchup(['群攻'], ['银甲武装公司'])
    assert s2 > 0.5 and any('利' in x for x in r2)
    s3, r3 = matchup([], [])
    assert s3 == 0.5 and r3 == []


def test_boss_fit_mechanics_fallback():
    """无 countered_by_bosses 但有 mechanic_attributes 的 comp → 结构层兜底
    (20 boss 里 16 个无 countered 数据的 comp 不再恒 None)。"""
    comp = next(c for c in COMP_LIBRARY
                if not c.countered_by_bosses and c.mechanic_attributes)
    v = boss_fit(comp, ['火线动力机甲'])
    assert v is not None and 0.0 <= v <= 1.0


def test_boss_tags_roundtrip():
    canon, tags = boss_tags(['剧目', '电视机'])
    assert '造梦兄弟影业' in canon
    assert 'share_hp' in tags          # 剧目 → 共享血量
    assert 'speed_lock' not in tags and 'share_hp' in tags  # 电视机已定位造梦互动娱乐(2026-08-17),tag 挂钩退役
