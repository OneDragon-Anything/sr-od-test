"""cw_observe.obs_conflict 截图节流测试(2026-08-18 治理,18.8GB 积压根因)。

慢性状态冲突(deployed_align「补齐」每帧触发)画面微变(gold 计数/动画帧)→
内容哈希必新 → 每帧存 1.7MB → 18.8GB 积压。节流 = 同 (field,verdict) 300s 内
只存一张;JSONL 证据行不受节流(200B/行,统计价值保留);异 verdict 照存。
(独立文件:test_obs_conflict_guards 的 autouse fixture no-op 掉 obs_conflict,
真实节流逻辑需跑真实现。)
"""
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import sr_od.application.currency_war.cw_observe as obs_mod  # noqa: E402


def test_obs_conflict_shot_throttle(monkeypatch, tmp_path):
    """节流三态:窗内第二张不存(JSONL 照写)/ 异 verdict 不受影响 / 窗口过后恢复。"""
    calls: list[str] = []
    monkeypatch.setattr(obs_mod, 'cw_shot_unique',
                        lambda img, label: (calls.append(label), f'{label}__x.png')[1])
    monkeypatch.setattr(obs_mod, '_CONFLICT_JOURNAL', tmp_path / 'conf.jsonl')
    obs_mod._conflict_shot_ts.clear()
    fake = np.zeros((4, 4, 3), dtype=np.uint8)
    # 第一张:存
    obs_mod.obs_conflict('deployed_align', 4, 6, fake, verdict='补齐-tracked少计')
    assert len(calls) == 1
    # 同 key 窗内:不存(JSONL 仍追加)
    obs_mod.obs_conflict('deployed_align', 4, 6, fake, verdict='补齐-tracked少计')
    assert len(calls) == 1, '同 (field,verdict) 300s 内节流'
    lines = (tmp_path / 'conf.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 2, 'JSONL 证据行不受节流(统计价值保留)'
    # 异 verdict:不受影响
    obs_mod.obs_conflict('deployed_align', 4, 6, fake, verdict='留证-双源不等')
    assert len(calls) == 2, '不同 verdict = 不同慢性态,照存'
    # 窗口过后(monotonic 回拨):恢复存
    obs_mod._conflict_shot_ts[('deployed_align', '补齐-tracked少计')] = -1e9
    obs_mod.obs_conflict('deployed_align', 4, 6, fake, verdict='补齐-tracked少计')
    assert len(calls) == 3, '窗口过后恢复存'
