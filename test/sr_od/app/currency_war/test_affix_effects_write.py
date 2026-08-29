"""write_affix_effects OCR 污染守卫测试(D-81)。

验证 D-81 三策略:① garbage(「下一步」按钮文字 / 空)拒写;② existing divergent 不覆盖
(词缀效果静态,现有值更可信);③ new key(过 garbage 守卫)正常新增。

用 tmp 文件 + monkeypatch ``_AFFIX_EFFECTS_PATH``,不碰真实注册表 ``affix_effects_data.py``。
根因:简报 tooltip 未弹时 ``read_affix_effect`` 读下行(下一词缀行 / 「下一步」按钮)当效果 → garbage;
同轮 OCR 也可能把 ``85%/60%/30%`` 坏成 ``85%160%/30%``(间歇)。详见 decisions.md D-81。
"""
import json

import sr_od.application.currency_war.obs.cw_briefing_obs as mod
from sr_od.application.currency_war.obs.cw_briefing_obs import (
    _is_garbage_affix,
    load_affix_effects_from_file,
    write_affix_effects,
)


def _seed(tmp_path, registry: dict[str, str]) -> None:
    """写一个最小合法 affix_effects_data.py(含 ``AFFIX_EFFECTS`` dict)到 tmp。"""
    (tmp_path / 'affix_effects_data.py').write_text(
        'AFFIX_EFFECTS: dict[str, str] = '
        + json.dumps(registry, ensure_ascii=False, indent=4) + '\n',
        encoding='utf-8',
    )


def test_is_garbage_affix() -> None:
    """「下一步」按钮文字 / 拼接含「下一步」/ 空 → True;真效果 → False。"""
    assert _is_garbage_affix('开局不利', '下一步')
    assert _is_garbage_affix('*冰之熄火', '随从强化开局不利沉重脚步下一步')  # 拼接含「下一步」
    assert _is_garbage_affix('丢失幸运', '   ')  # 空
    assert not _is_garbage_affix('形单影只', '造成的伤害变为原伤害的85%/60%/30%。')


def test_garbage_rejected_not_written(monkeypatch, tmp_path) -> None:
    """garbage(「下一步」/空)update → 拒写,注册表不变。"""
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    seed = {'形单影只': '原值'}
    _seed(tmp_path, seed)
    wrote = write_affix_effects({'开局不利': '下一步', '丢失幸运': ''})
    assert wrote is False
    assert load_affix_effects_from_file() == seed  # 无 garbage 写入


def test_existing_divergent_not_overwritten(monkeypatch, tmp_path) -> None:
    """existing key + divergent OCR → 不覆盖(静态数据,现有值更可信)。"""
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    good = '造成的伤害变为原伤害的85%/60%/30%。'
    _seed(tmp_path, {'形单影只': good})
    # OCR 重读把 85%/60%/30% 坏成 85%160%/30%(D-81 实例)
    wrote = write_affix_effects({'形单影只': '造成的伤害变为原伤害的85%160%/30%。'})
    assert wrote is False
    assert load_affix_effects_from_file()['形单影只'] == good  # 好值没被覆盖


def test_new_key_added(monkeypatch, tmp_path) -> None:
    """新词缀(过 garbage 守卫)→ 正常新增。"""
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    _seed(tmp_path, {'首领强化': '首领敌人获得强化,速度提高60%,生命上限提高30%。'})
    wrote = write_affix_effects({'随从强化': '普通和精英敌人获得强化,速度提高30%,生命上限提高20%。'})
    assert wrote is True
    out = load_affix_effects_from_file()
    assert '随从强化' in out and '首领强化' in out


def test_existing_same_is_noop(monkeypatch, tmp_path) -> None:
    """existing + 一致 → no-op(不写文件,返回 False)。"""
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    seed = {'首领强化': '原值'}
    _seed(tmp_path, seed)
    wrote = write_affix_effects({'首领强化': '原值'})
    assert wrote is False
    assert load_affix_effects_from_file() == seed


def test_mixed_batch_keeps_new_rejects_garbage(monkeypatch, tmp_path) -> None:
    """混合 batch:新 key 加、garbage 拒、existing divergent 跳 → 只 new 进文件。"""
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    _seed(tmp_path, {'形单影只': '好值'})
    wrote = write_affix_effects({
        '随从强化': '新词缀好值',           # new → 加
        '开局不利': '下一步',               # garbage → 拒
        '形单影只': '坏值 divergent',       # existing divergent → 不覆盖
    })
    assert wrote is True
    out = load_affix_effects_from_file()
    assert out['随从强化'] == '新词缀好值'
    assert '开局不利' not in out
    assert out['形单影只'] == '好值'  # 未被 divergent 覆盖
