"""load_affix_effects_from_file ast 解析锁(W266)。

W266 把原 ``exec`` 解析换成 ast 静态提取(零代码执行)。本文件锁两件事:

1. **行为等价**:对真实文件形态(writer 生成 / 测试 seed 的 AnnAssign 形态、plain Assign 形态)
   与 exec 参照实现**同输入同输出**;
2. **边界口径**:缺文件 / 空文件 / 语法坏 / 非字面量值(AST 内含调用/名字)/ 非 dict 字面量 /
   无 AFFIX_EFFECTS 定义 → 一律 ``{}``(与旧实现异常兜底同口径);
3. **安全性质**:文件内夹带恶意代码(payload 后附 ``import os`` 触发语句)时 **不执行**(exec 版会执行)。
"""
import json

import sr_od.application.currency_war.cw_briefing_obs as mod
from sr_od.application.currency_war.cw_briefing_obs import load_affix_effects_from_file


def _write(tmp_path, content: str):
    p = tmp_path / 'affix_effects_data.py'
    p.write_text(content, encoding='utf-8')
    return p


def _exec_reference(content: str) -> dict:
    """旧行为参照(exec 全文 → 取 AFFIX_EFFECTS;异常/非 dict → {})。仅用于测试内对拍。"""
    ns: dict = {}
    try:
        exec(content, ns)
        result = ns.get('AFFIX_EFFECTS', {})
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def _annassign(registry: dict[str, str]) -> str:
    """writer 生成的注册表形态(cw_briefing_obs.write_affix_effects 同构)。"""
    return ('from __future__ import annotations\n\n'
            'AFFIX_EFFECTS: dict[str, str] = '
            + json.dumps(registry, ensure_ascii=False, indent=4) + '\n')


def test_equivalence_writer_form(monkeypatch, tmp_path) -> None:
    """writer 生成形态(dict[str,str] 字面量)→ 与 exec 参照同输出。"""
    registry = {
        '形单影只': '造成的伤害变为原伤害的85%/60%/30%。',
        '火之熄火': '火属性目标伤害只造成1点。',
    }
    content = _annassign(registry)
    _write(tmp_path, content)
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    assert load_affix_effects_from_file() == registry == _exec_reference(content)


def test_equivalence_plain_assign_and_junk(monkeypatch, tmp_path) -> None:
    """plain Assign + 文件内夹杂其他语句(人类手编容错)→ 同输出。"""
    registry = {'随从强化': '速度提高30%。'}
    content = ('# 手编注释\nOTHER = "别的"\n\n'
               'AFFIX_EFFECTS = ' + json.dumps(registry, ensure_ascii=False) + '\n'
               '\ndef unused():\n    pass\n')
    _write(tmp_path, content)
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    assert load_affix_effects_from_file() == registry
    # plain Assign 里 dict value 是字面量 → exec 参照也一致
    assert load_affix_effects_from_file() == _exec_reference(content)


def test_missing_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'nope.py')
    assert load_affix_effects_from_file() == {}


def test_broken_syntax(monkeypatch, tmp_path) -> None:
    """语法损坏(D-81 曾见工作区损坏)→ {} 兜底。"""
    _write(tmp_path, 'AFFIX_EFFECTS: dict[str, str] = {"a": ')
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    assert load_affix_effects_from_file() == {}


def test_non_literal_value_returns_empty(monkeypatch, tmp_path) -> None:
    """值为非字面量表达式(AST 含 Call)→ {} 不执行。"""
    content = 'AFFIX_EFFECTS = dict(a="b")\n'
    _write(tmp_path, content)
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    assert load_affix_effects_from_file() == {}


def test_non_dict_literal_returns_empty(monkeypatch, tmp_path) -> None:
    """合法字面量但不是 dict(如 list)→ {}(与旧 isinstance 守卫同口径)。"""
    content = 'AFFIX_EFFECTS = ["a", "b"]\n'
    _write(tmp_path, content)
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    assert load_affix_effects_from_file() == {}


def test_no_target_defined(monkeypatch, tmp_path) -> None:
    """文件存在但无 AFFIX_EFFECTS → {}(旧版取 ns.get 默认)。"""
    content = 'OTHER = "x"\n'
    _write(tmp_path, content)
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    assert load_affix_effects_from_file() == {}


def test_never_executes_code_in_file(monkeypatch, tmp_path) -> None:
    """安全性质:payload 外的代码不执行 —— 夹带副作用写入 sentinel 文件,ast 版不应触发。

    (旧 exec 版会在 import 该文件语义上执行此代码并留下 sentinel。)
    """
    registry = {'形单影只': '好值'}
    sentinel = tmp_path / 'sentinel.txt'
    content = (_annassign(registry)
               + f'\nopen(r"{sentinel}", "w").write("executed")\n')
    _write(tmp_path, content)
    monkeypatch.setattr(mod, '_AFFIX_EFFECTS_PATH', tmp_path / 'affix_effects_data.py')
    out = load_affix_effects_from_file()
    assert out == registry
    assert not sentinel.exists()
