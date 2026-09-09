"""load_affix_effects_from_file 行为锁(ast 静态提取,零代码执行;W266 以 ast 替代原 exec 方案)。

本文件锁三件事:

1. **行为表**:对真实文件形态(writer 生成的 AnnAssign 形态、人类手编 plain Assign
   + 夹杂语句形态)提取出 ``AFFIX_EFFECTS`` 字面量;
2. **边界口径**:缺文件 / 语法坏 / 非字面量值(AST 内含调用/名字)/ 非 dict 字面量 /
   无 AFFIX_EFFECTS 定义 → 一律 ``{}``(与旧 exec 实现异常兜底同口径);
3. **安全性质**:文件内夹带恶意代码(payload 后附 ``import os`` 触发语句)时 **不执行**
   ——旧 exec 版会执行,这是 W266 换 ast 的动机本身。

(2026-09-08 瘦身批:原「与测试内 exec 参照实现同输入同输出」对拍删除——参照是
已退役实现搬进测试的复刻,断言真值本就是各测的 registry 字面量;参照自身与
registry 不一致只会造假红,对被测 loader 零判别力,自抄复刻纪律。)

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import json

import sr_od.application.currency_war.obs.cw_briefing_obs as mod
from sr_od.application.currency_war.obs.cw_briefing_obs import load_affix_effects_from_file


def _seed(monkeypatch, tmp_path, content: str) -> None:
    """写注册表文件并把 loader 的路径模块全局指到 tmp(纪律:不写真实 data/)。"""
    p = tmp_path / 'affix_effects_data.py'
    p.write_text(content, encoding='utf-8')
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', p)


def _annassign(registry: dict[str, str]) -> str:
    """writer 生成的注册表形态(cw_briefing_obs.write_affix_effects 同构)。"""
    return ('from __future__ import annotations\n\n'
            'AFFIX_EFFECTS: dict[str, str] = '
            + json.dumps(registry, ensure_ascii=False, indent=4) + '\n')


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
