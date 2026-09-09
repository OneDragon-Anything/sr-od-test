"""test_cw_affix_effects 主题锁——词缀效果注册表(affix_effects_data.py)读写两半。

2026-09-09 合并批:原 test_cw_affix_effects_load.py(load 半面)+
test_cw_affix_effects_write.py(write 半面)按模块两面对归并(同一注册表文件的
读/写两半;load 为 write 的 round-trip oracle——write 落盘内容必须能被 load
原样读回,write 半面各测已隐含走通这条环)。

**load 半面**(原 test_cw_affix_effects_load.py;W266 以 ast 替代原 exec 方案)锁三件事:

1. **行为表**:对真实文件形态(writer 生成的 AnnAssign 形态、人类手编 plain Assign
   + 夹杂语句形态)提取出 ``AFFIX_EFFECTS`` 字面量;
2. **边界口径**:缺文件 / 语法坏 / 非字面量值(AST 内含调用/名字)/ 非 dict 字面量 /
   无 AFFIX_EFFECTS 定义 → 一律 ``{}``(与旧 exec 实现异常兜底同口径);
3. **安全性质**:文件内夹带恶意代码(payload 后附 ``import os`` 触发语句)时 **不执行**
   ——旧 exec 版会执行,这是 W266 换 ast 的动机本身。

   (2026-09-08 瘦身批:原「与测试内 exec 参照实现同输入同输出」对拍删除——参照是
   已退役实现搬进测试的复刻,断言真值本就是各测的 registry 字面量;参照自身与
   registry 不一致只会造假红,对被测 loader 零判别力,自抄复刻纪律。)

**write 半面**(原 test_cw_affix_effects_write.py)验证 D-81 三策略:
① garbage(「下一步」按钮文字 / 空)拒写;② existing divergent 不覆盖
(词缀效果静态,现有值更可信);③ new key(过 garbage 守卫)正常新增。
根因:简报 tooltip 未弹时 ``read_affix_effect`` 读下行(下一词缀行 / 「下一步」按钮)
当效果 → garbage;同轮 OCR 也可能把 ``85%/60%/30%`` 坏成 ``85%160%/30%``(间歇)。
详见 decisions.md D-81。

两半共用桩 helper(``_seed``/``_annassign``/``_seed_registry``):一律 tmp 文件 +
monkeypatch ``_AFFIX_EFFECTS_PATH``,不碰真实注册表 ``affix_effects_data.py``。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览
docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import json

import sr_od.application.currency_war.obs.cw_briefing_obs as mod
from sr_od.application.currency_war.obs.cw_briefing_obs import (
    _is_garbage_affix,
    load_affix_effects_from_file,
    write_affix_effects,
)


def _seed(monkeypatch, tmp_path, content: str) -> None:
    """写注册表文件内容并把 loader/writer 的路径模块全局指到 tmp(纪律:不写真实 data/)。"""
    p = tmp_path / 'affix_effects_data.py'
    p.write_text(content, encoding='utf-8')
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', p)


def _annassign(registry: dict[str, str]) -> str:
    """writer 生成的注册表形态(cw_briefing_obs.write_affix_effects 同构)。"""
    return ('from __future__ import annotations\n\n'
            'AFFIX_EFFECTS: dict[str, str] = '
            + json.dumps(registry, ensure_ascii=False, indent=4) + '\n')


def _seed_registry(monkeypatch, tmp_path, registry: dict[str, str]) -> None:
    """write 半面专用:写最小合法注册表并接好路径桩(_seed + _annassign 组合;
    与 load 半面吃任意内容文本的 _seed 同名分工,勿混用)。"""
    _seed(monkeypatch, tmp_path, _annassign(registry))


# ==================== load 半面(原 test_cw_affix_effects_load.py) ====================

def test_writer_form_extracts_registry(monkeypatch, tmp_path) -> None:
    """writer 生成形态(dict[str,str] 字面量 AnnAssign)→ 原样提取。"""
    registry = {
        '形单影只': '造成的伤害变为原伤害的85%/60%/30%。',
        '火之熄火': '火属性目标伤害只造成1点。',
    }
    _seed(monkeypatch, tmp_path, _annassign(registry))
    assert load_affix_effects_from_file() == registry


def test_plain_assign_with_other_statements(monkeypatch, tmp_path) -> None:
    """plain Assign + 文件内夹杂注释/其他赋值/函数(人类手编容错)→ 同样提取。"""
    registry = {'随从强化': '速度提高30%。'}
    content = ('# 手编注释\nOTHER = "别的"\n\n'
               'AFFIX_EFFECTS = ' + json.dumps(registry, ensure_ascii=False) + '\n'
               '\ndef unused():\n    pass\n')
    _seed(monkeypatch, tmp_path, content)
    assert load_affix_effects_from_file() == registry


def test_missing_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'nope.py')
    assert load_affix_effects_from_file() == {}


def test_broken_syntax(monkeypatch, tmp_path) -> None:
    """语法损坏(D-81 曾见工作区损坏)→ {} 兜底。"""
    _seed(monkeypatch, tmp_path, 'AFFIX_EFFECTS: dict[str, str] = {"a": ')
    assert load_affix_effects_from_file() == {}


def test_non_literal_value_returns_empty(monkeypatch, tmp_path) -> None:
    """值为非字面量表达式(AST 含 Call)→ {} 不执行。"""
    _seed(monkeypatch, tmp_path, 'AFFIX_EFFECTS = dict(a="b")\n')
    assert load_affix_effects_from_file() == {}


def test_non_dict_literal_returns_empty(monkeypatch, tmp_path) -> None:
    """合法字面量但不是 dict(如 list)→ {}(与旧 isinstance 守卫同口径)。"""
    _seed(monkeypatch, tmp_path, 'AFFIX_EFFECTS = ["a", "b"]\n')
    assert load_affix_effects_from_file() == {}


def test_no_target_defined(monkeypatch, tmp_path) -> None:
    """文件存在但无 AFFIX_EFFECTS → {}(与旧 exec ns.get 默认同口径)。"""
    _seed(monkeypatch, tmp_path, 'OTHER = "x"\n')
    assert load_affix_effects_from_file() == {}


def test_never_executes_code_in_file(monkeypatch, tmp_path) -> None:
    """安全性质:payload 外的代码不执行 —— 夹带副作用写入 sentinel 文件,ast 版不应触发。

    (旧 exec 版会执行此代码并留下 sentinel——W266 换 ast 的动机本身。)
    """
    registry = {'形单影只': '好值'}
    sentinel = tmp_path / 'sentinel.txt'
    content = (_annassign(registry)
               + f'\nopen(r"{sentinel}", "w").write("executed")\n')
    _seed(monkeypatch, tmp_path, content)
    out = load_affix_effects_from_file()
    assert out == registry
    assert not sentinel.exists()


# ==================== write 半面(原 test_cw_affix_effects_write.py) ====================

def test_is_garbage_affix() -> None:
    """「下一步」按钮文字 / 拼接含「下一步」/ 空 → True;真效果 → False。"""
    assert _is_garbage_affix('开局不利', '下一步')
    assert _is_garbage_affix('*冰之熄火', '随从强化开局不利沉重脚步下一步')  # 拼接含「下一步」
    assert _is_garbage_affix('丢失幸运', '   ')  # 空
    assert not _is_garbage_affix('形单影只', '造成的伤害变为原伤害的85%/60%/30%。')


def test_garbage_rejected_not_written(monkeypatch, tmp_path) -> None:
    """garbage(「下一步」/空)update → 拒写,注册表不变。"""
    seed = {'形单影只': '原值'}
    _seed_registry(monkeypatch, tmp_path, seed)
    wrote = write_affix_effects({'开局不利': '下一步', '丢失幸运': ''})
    assert wrote is False
    assert load_affix_effects_from_file() == seed  # 无 garbage 写入


def test_existing_divergent_not_overwritten(monkeypatch, tmp_path) -> None:
    """existing key + divergent OCR → 不覆盖(静态数据,现有值更可信)。"""
    good = '造成的伤害变为原伤害的85%/60%/30%。'
    _seed_registry(monkeypatch, tmp_path, {'形单影只': good})
    # OCR 重读把 85%/60%/30% 坏成 85%160%/30%(D-81 实例)
    wrote = write_affix_effects({'形单影只': '造成的伤害变为原伤害的85%160%/30%。'})
    assert wrote is False
    assert load_affix_effects_from_file()['形单影只'] == good  # 好值没被覆盖


def test_new_key_added(monkeypatch, tmp_path) -> None:
    """新词缀(过 garbage 守卫)→ 正常新增。"""
    _seed_registry(monkeypatch, tmp_path,
                   {'首领强化': '首领敌人获得强化,速度提高60%,生命上限提高30%。'})
    wrote = write_affix_effects({'随从强化': '普通和精英敌人获得强化,速度提高30%,生命上限提高20%。'})
    assert wrote is True
    out = load_affix_effects_from_file()
    assert '随从强化' in out and '首领强化' in out


def test_existing_same_is_noop(monkeypatch, tmp_path) -> None:
    """existing + 一致 → no-op(不写文件,返回 False)。"""
    seed = {'首领强化': '原值'}
    _seed_registry(monkeypatch, tmp_path, seed)
    wrote = write_affix_effects({'首领强化': '原值'})
    assert wrote is False
    assert load_affix_effects_from_file() == seed


def test_mixed_batch_keeps_new_rejects_garbage(monkeypatch, tmp_path) -> None:
    """混合 batch:新 key 加、garbage 拒、existing divergent 跳 → 只 new 进文件。"""
    _seed_registry(monkeypatch, tmp_path, {'形单影只': '好值'})
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
