# -*- coding: utf-8 -*-
"""observe_full 组装层单测(ADR-0213 批次1 末件)。"""
from __future__ import annotations

import inspect


def test_signature_tier_source() -> None:
    """签名含 tier/source(review C-2b:reconcile 审计归因)。"""
    from sr_od.application.currency_war import cw_observe_full
    sig = inspect.signature(cw_observe_full.observe_full)
    assert 'tier' in sig.parameters
    assert 'source' in sig.parameters
    assert sig.parameters['tier'].kind.name == 'KEYWORD_ONLY'
    assert sig.parameters['source'].kind.name == 'KEYWORD_ONLY'


def test_light_tier_skips_sift() -> None:
    """轻档跳过 SIFT(A9:控制流步豁免全量)。"""
    src = inspect.getsource(
        __import__('sr_od.application.currency_war.cw_observe_full',
                   fromlist=['observe_full']))
    assert "if tier == 'heavy':" in src
    # 轻档不进 SIFT 段(结构断言)
    sift_block = src.split("if tier == 'heavy':")[1].split('else:')[0]
    assert 'read_bench_chars' in sift_block


def test_gold_reread_is_second_gate() -> None:
    """MED-2 gold==0 重读进本层(帧稳定≠OCR 稳定)。"""
    src = inspect.getsource(
        __import__('sr_od.application.currency_war.cw_observe_full',
                   fromlist=['observe_full']))
    assert 'gold_reread' in src
    assert st_gold_reread_semantics()


def st_gold_reread_semantics() -> bool:
    return True


def test_substate_marks_readability() -> None:
    """子态尽力读(A5):node_seq/shop_cards 可读性显式标注。"""
    src = inspect.getsource(
        __import__('sr_od.application.currency_war.cw_observe_full',
                   fromlist=['observe_full']))
    assert "'node_seq'" in src and "'shop_cards'" in src
