"""批 B 件3 锁:sim 接线对照表对账(sim-wiring.md)。

锁:对照表逐字段覆盖 GameState 全部字段(一字段一行,不重不漏),
三档+已接分类计数与文档头声明一致(17+12+3+5=37,ADR-0286),且与
dataclasses.fields(GameState) 实测对账——防后续加字段漏更对照表。
"""
from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_state import GameState

_DOC = (Path(cw_sim.__file__).resolve().parents[4]
        / 'docs' / 'develop' / 'currency_war' / 'sim-wiring.md')


def _tier_rows() -> dict[str, list[str]]:
    """解析文档四个二级节的数据表:节名 → 字段名列表。"""
    text = _DOC.read_text(encoding='utf-8')
    sections = re.split(r'^## ', text, flags=re.M)[1:]
    out: dict[str, list[str]] = {}
    for sec in sections:
        title = sec.splitlines()[0]
        names = re.findall(r'^\| ([a-z_]\w*) \|', sec, flags=re.M)
        out[title] = names
    return out


def test_doc_covers_all_gamestate_fields() -> None:
    """对照表覆盖 GameState 全部字段,一字段一行不重不漏。"""
    rows = _tier_rows()
    all_names = [n for names in rows.values() for n in names]
    expect = [f.name for f in fields(GameState)]
    assert sorted(all_names) == sorted(expect), (
        f'对照表与 GameState 字段不一致:'
        f'缺 {sorted(set(expect) - set(all_names))},'
        f'多 {sorted(set(all_names) - set(expect))}')
    assert len(all_names) == len(set(all_names)), '字段重复出现'


def test_tier_counts_match_declared_reconciliation() -> None:
    """三档+已接计数与文档头对账声明一致(18+12+5+5=40,ADR-0286 +deploy_cap;批㉖ F1 +enemy_difficulty_live、契约包 C1 步2 +action_log、ADR-0428 +hp_trusted)。"""
    rows = _tier_rows()
    counts = {k: len(v) for k, v in rows.items()}
    assert sum(counts.values()) == len(fields(GameState)) == 40
    assert any('已接线' in k for k in counts) and counts[
        next(k for k in counts if '已接线' in k)] == 18
    assert counts[next(k for k in counts if '必须接线' in k)] == 12
    assert counts[next(k for k in counts if '观测冗余' in k)] == 5
    assert counts[next(k for k in counts if '结构未建' in k)] == 5
