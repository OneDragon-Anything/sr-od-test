"""结算屏胜负标识解析(``parse_settlement_verdict`` 三态 + ``parse_settlement_won`` 委托等价)。

锁的设计约定(标定依据见 src cw_settlement_obs.py ``parse_settlement_verdict`` docstring):
- 标题词 → 三态:挑战成功→win / 挑战失败→failed / 挑战结束→ended;三词皆无→None(不冒认)。
- 判定走全等子串不走 LCS 相似:兄弟词(成功/结束/失败 两两共享「挑战」前缀)不得互串——
  这是画面档标题 area 曾因默认 lcs 0.5 放行兄弟词的同一缺陷,识别器侧以子串全等锁死。
- ``parse_settlement_won`` 委托后行为等价:win→True、failed→False、ended→None(非 killed,
  交进度符号分支);标题词全缺时进度符号分支照常。

帧级真 OCR 三态复放住 test_settlement_recognizer.py(area 命中组合 + 识别器 verdict)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.obs.cw_settlement_obs import (
    SETTLE_VERDICT_ENDED,
    SETTLE_VERDICT_FAILED,
    SETTLE_VERDICT_WIN,
    parse_settlement_verdict,
    parse_settlement_won,
)


@pytest.mark.parametrize(('texts', 'expected'), [
    (['挑战成功', '1-3X点', '战斗', '继续挑战'], SETTLE_VERDICT_WIN),
    # 标题与节点类型粘连成一个 token(实跑形态)仍按子串命中
    (['挑战成功战斗', '小队生命值82i'], SETTLE_VERDICT_WIN),
    (['挑战失败', '小队生命值0', '下一步'], SETTLE_VERDICT_FAILED),
    (['挑战结束', '1-9', '首领', '小队生命值1i', '继续挑战'], SETTLE_VERDICT_ENDED),
    (['挑战结束', '2-2战斗', '挑战进度', '-22', '前往结算'], SETTLE_VERDICT_ENDED),
    # 标题词全缺 → None(不冒认任何一态)
    ([], None),
    (['小队生命值79i', '获得金币总览', '继续挑战'], None),
])
def test_verdict_three_states(texts: list[str], expected: str | None) -> None:
    """标题词 → 三态 / 全缺 → None。"""
    assert parse_settlement_verdict(texts) == expected


def test_won_delegates_to_verdict_without_changing_killed_semantics() -> None:
    """``parse_settlement_won`` 委托后 killed 语义等价:win→True / failed→False /
    ended→None(非 killed)/ 标题词全缺走进度符号分支。"""
    assert parse_settlement_won(['挑战成功', '继续挑战']) is True
    assert parse_settlement_won(['挑战失败', '下一步']) is False
    # 「挑战结束」含平局式结束,不得判成输(ended → None)
    assert parse_settlement_won(['挑战结束', '继续挑战']) is None
    # 标题词全缺时进度符号分支照常:负 → 输,正 → 赢,无进度 → None
    assert parse_settlement_won(['挑战进度', '-22']) is False
    assert parse_settlement_won(['挑战进度', '+2']) is True
    assert parse_settlement_won(['小队生命值79i']) is None
