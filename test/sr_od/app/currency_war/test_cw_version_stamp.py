"""版本戳(version_stamp)回归锁。

锁的是 2026-08-29 迭代对抗审计两条 P2 的修复语义:
- _REPO_ROOT 错层(旧取 parents[4]=src,注释却当仓库根):修为模块相对
  向上找 pyproject.toml 锚点,禁 cwd 依赖。
- _normalize 集合分支 sorted 对混合/容器元素直接比较 → TypeError(炸点
  在局终写档,runs 行整行丢失):修为按规范化 JSON 串排序,恒全序。
"""

import dataclasses
import json

from sr_od.application.currency_war.telemetry.version_stamp import (
    _REPO_ROOT,
    _normalize,
    code_commit,
    current_version_stamp,
    registry_fingerprint,
)

# ===== 锁 1:_REPO_ROOT 模块相对定位 =====

def test_repo_root_points_at_real_repo_root() -> None:
    """_REPO_ROOT 必须是仓库根(含 pyproject.toml + src/sr_od),不是 src 层。

    旧缺陷:parents[4] 实为 src/,git rev-parse 从子目录向上搜索侥幸命中
    同仓——按注释把 _REPO_ROOT 当根拼路径、或部署形态变化即产出错误
    commit/串仓版本。锁钉「根的客观锚点存在」而非路径字面值。"""
    assert (_REPO_ROOT / 'pyproject.toml').is_file()
    assert (_REPO_ROOT / 'src' / 'sr_od').is_dir()


# ===== 锁 2:_normalize 集合分支全序可排序 =====

def test_normalize_set_with_mixed_scalar_and_container_elements() -> None:
    """集合元素规范化后类型混合(标量 + tuple→list)→ 不抛 TypeError
    (P2-6 回归锁:旧 sorted 直接比较 list 与 str/int 必炸)。
    注:集合元素必须可哈希,混合形态的真实来源是 tuple(规范化转 list)
    与标量共存;规范化后类型互异即触发旧缺陷。"""
    mixed = {1, 2, (3, 4), 'a'}
    out = _normalize(mixed)
    assert isinstance(out, list)
    assert len(out) == 4
    # 输出可稳定 JSON 化(JSON dumps 本身也是指纹链路的一环)
    json.dumps(out, sort_keys=True, ensure_ascii=False)


@dataclasses.dataclass(frozen=True)   # frozen=True 才可哈希、可进集合(与注册表字段同构)
class _FakeEntry:   # 模拟注册表里可能出现的 set[SomeDataclass] 字段
    name: str
    value: int


def test_normalize_set_of_dataclass() -> None:
    """set[dataclass](指纹契约声称「应付任意注册表内容」的未来形态)
    → 元素规范化为 dict(asdict 对 set 字段只 deepcopy,数据类实例原样
    进集合分支),排序不炸且结果确定。"""
    s = {_FakeEntry('x', 1), _FakeEntry('y', 2)}
    out = _normalize(set(s))
    assert isinstance(out, list) and len(out) == 2
    assert all(isinstance(x, dict) for x in out)
    assert out == sorted(out, key=lambda x: json.dumps(
        x, sort_keys=True, ensure_ascii=False))


def test_normalize_set_order_stable() -> None:
    """同元素集合(不同构造插入序)→ 规范化输出逐位相等(set 无序,
    指纹对构造序不敏感是 hash 口径的隐含契约)。"""
    a = _normalize({3, 1, 2})
    b = _normalize({2, 3, 1})
    assert a == b


# ===== 锁 3:对外契约不回归 =====

def test_registry_fingerprint_contract() -> None:
    """指纹 = 12 位 hex 且两次调用稳定(同一进程内注册表不变 → 指纹不变)。"""
    fp1 = registry_fingerprint()
    fp2 = registry_fingerprint()
    assert len(fp1) == 12
    assert int(fp1, 16) >= 0   # hex 可解析
    assert fp1 == fp2


def test_fingerprint_survives_exotic_registry(monkeypatch) -> None:
    """端到端回归锁(P2-6 真实炸点链):注册表未来形态 set[dataclass]
    (asdict 对 set 成员不递归,实例原样进 _normalize)→ 指纹不抛
    TypeError 且确定。旧代码在局终写档(无异常保护)整行丢 runs。"""
    import sr_od.application.currency_war.telemetry.version_stamp as vs

    @dataclasses.dataclass(frozen=True)
    class _Reg:
        mapping: dict

    s = {_FakeEntry('x', 1), _FakeEntry('y', 2)}
    reg = _Reg(mapping={'k': s})   # set 塞 dict 值域(asdict 递归 dict 但 set 成员只 deepcopy)
    monkeypatch.setattr(vs, 'DEFAULT_REGISTRY', reg, raising=False)
    fp1 = vs.registry_fingerprint()
    fp2 = vs.registry_fingerprint()
    assert len(fp1) == 12 and fp1 == fp2


def test_current_version_stamp_keys() -> None:
    """版本戳双键齐全;code_commit 在 git checkout 内应为非空短哈希
    (best-effort 契约:失败回 '',但本仓测试运行环境恒在 checkout 内)。"""
    stamp = current_version_stamp()
    assert set(stamp.keys()) == {'code_commit', 'registry_fingerprint'}
    assert stamp['code_commit'] == code_commit()
    assert 0 < len(stamp['code_commit']) <= 12
