"""调用点 kwarg 名 ↔ 被调签名 静态对拍扫描器(kwarg 错传病族回归资产)。

背景(2026-08-25 实锤):``@operation_node(node_name='处理策划事件')`` 用了不存在的
keyword,而框架签名是 ``name=`` —— TypeError 在 import 期爆,但该 handler 是惰性
import,常规测试不触发,存活 6 天才被 MCP ``list_operations`` 的 failures 暴露。
病根 = 调用点参数名无静态校验(Python 语言特性);本扫描器把「调用点 keyword 参数名
∈ 被调签名形参集」做成全仓静态校验,作为回归锁(测试网每次跑测试即对拍)。

覆盖范围:``src/`` 下 ``one_dragon`` + ``one_dragon_qt`` + ``sr_od``
(``onnxocr`` 是三方依赖,跳过)。

解析策略(按优先级):
  ① 同文件 def / class(``__init__`` 去 self 后形参)→ ast 直接比对;
  ② ``from X import Y`` / ``import X`` → 目标模块同仓 AST 提取签名
     (快速路径,零 import 副作用;重导出链按深度≤3 跟随);
     AST 不可见目标(动态生成 / C 扩展 / 重导出断链)→ importlib + inspect.signature
     兜底(try/except,导不动的记 unresolved,不算违规);
  ③ 被调签名含 ``**kwargs`` / ``**_`` → 合法通配,跳过(任意 keyword 合法);
  ④ functools.partial / getattr 间接 / 方法链(``self.ctx.ocr.xxx``)解析不了
     → unresolved 计数(不算违规,报告列量);
  ⑤ keyword 名不在签名形参集 → **违规**(就是 node_name= 那个病类)。

另输出签名侧 ``**kwargs`` 清单(sr_od 域内 def 带 ``**kwargs`` —— AGENTS.md
「构造函数显式声明参数」成文规范的对拍;one_dragon 是共享框架仓,不算)。

已知盲区(报告声明,不视为违规):
  - 位置只读参数(``def f(a, /)``)被 ``f(a=1)`` 调用是运行时 TypeError,但 a 在
    形参集内,本扫描器不判(单独记 posonly 命中,信息列);
  - 本地变量遮蔽模块级函数(``foo = lambda ...; foo(x=1)``)→ 保守记 unresolved;
  - 条件定义 / 同文件重定义取最后一个 AST 定义;
  - 运行时动态构造的调用目标(``getattr(obj, name)(...)``)→ unresolved。
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import importlib
import inspect
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

#: 扫描域(src/ 下顶层包名;onnxocr 三方跳过)
DEFAULT_DOMAINS: tuple[str, ...] = ('one_dragon', 'one_dragon_qt', 'sr_od')

#: 重导出链跟随深度上限
REEXPORT_DEPTH_LIMIT = 3

#: 模块级不可解析赋值(partial 等)的占位
_UNRESOLVABLE = object()


@dataclass
class ImportInfo:
    """模块级 import 绑定:本地名 → 来源。"""

    kind: str                  # 'from' | 'import'
    module: str                # 绝对 dotted 模块路径
    name: str | None = None    # 'from' 的导入名;'import' 为 None(别名绑定模块)
    alias: str | None = None   # 本地名(= 绑定键)


@dataclass
class ModuleInfo:
    """单个源文件的解析上下文。"""

    path: Path
    dotted: str                # dotted 模块名(相对 src/)
    tree: ast.Module
    defs: dict[str, ast.AST]   # 模块级 name → FunctionDef/AsyncFunctionDef/ClassDef
    imports: dict[str, ImportInfo]
    assign_only: set[str]      # 模块级赋值但非 def/class(不可解析)
    source_lines: list[str]


@dataclass
class CallIssue:
    """一条调用点问题记录(违规或信息列)。"""

    file: str                  # 相对仓库根(posix 风格)
    line: int
    col: int
    snippet: str
    callee: str                # 展示用:'foo' / 'mod.foo' / 'self.foo' / 解析失败原因
    kwargs: list[str]          # 违规/命中的 keyword 名
    posonly: list[str] = field(default_factory=list)  # 命中位置只读参数(信息列)


@dataclass
class AuditResult:
    """一次全仓审计的结果。"""

    files_scanned: int
    call_nodes: int            # 全部 Call 节点(含无 keyword 的)
    kw_call_nodes: int         # 含 ≥1 个具名 keyword 的 Call
    resolved_ok: int
    wildcard_skip: int         # 被调有 **kwargs → 合法通配
    builtin_skip: int          # 被调是内建
    external_skip: int         # 被调在 src/ 之外(三方库)
    unresolved: int
    unresolved_by_reason: Counter
    violations: list[CallIssue]                       # 第一列:kwarg 名不在形参集
    posonly_hits: list[CallIssue]                     # 信息列:命中位置只读参数
    sig_kwargs: list[tuple[str, int, str, str]]       # 第二列:sr_od def 带 **kwargs
    elapsed_seconds: float = 0.0

    @property
    def violation_count(self) -> int:
        return len(self.violations)


class _Sig:
    """被调签名:可接受的 keyword 形参集 + 是否有 **kwargs 通配。"""

    __slots__ = ('params', 'has_kwargs', 'posonly')

    def __init__(self, params: set[str], has_kwargs: bool = False,
                 posonly: set[str] | None = None) -> None:
        self.params = params
        self.has_kwargs = has_kwargs
        self.posonly = posonly or set()


def _def_sig(node: ast.AST, strip_first: bool = False) -> _Sig | None:
    """从 def/class AST 提取签名。

    - FunctionDef:posonly+args+kwonly 形参名;``**kwargs``/``**_`` → has_kwargs。
    - ClassDef:取 ``__init__``(去 self);``@singledispatchmethod`` 重载取并集;
      无显式 ``__init__`` → NamedTuple 字段 / TypedDict(任意 kwarg 合法)/
      ``@dataclass`` 字段 / 否则视为无参(``object.__init__`` 语义)。
    - 不可解析(赋值等)→ None。
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        a = node.args
        posonly = {p.arg for p in a.posonlyargs if p.arg}
        args = {p.arg for p in a.args if p.arg}
        kwonly = {p.arg for p in a.kwonlyargs if p.arg}
        params = posonly | args | kwonly
        if strip_first and params:
            # 方法:去掉 self/cls 本身(它不会以 keyword 传入)
            first = (a.posonlyargs + a.args)[0].arg
            params.discard(first)
            posonly.discard(first)
        has_kwargs = a.kwarg is not None
        return _Sig(params, has_kwargs, posonly)
    if isinstance(node, ast.ClassDef):
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and stmt.name == '__init__':
                if _is_decorated(stmt, 'singledispatchmethod'):
                    return _singledispatch_sig(node)
                return _def_sig(stmt, strip_first=True)
        if _has_base(node, 'NamedTuple'):
            return _Sig(set(_namedtuple_field_names(node)))
        if _has_base(node, 'TypedDict'):
            # TypedDict 实例化接受任意 kwargs(字段即 dict 键),合法通配
            return _Sig(set(), has_kwargs=True)
        if _is_dataclass(node):
            return _Sig(set(_dataclass_field_names(node)))
        return _Sig(set())
    return None


def _singledispatch_sig(cls_node: ast.ClassDef) -> _Sig:
    """``@singledispatchmethod`` 的 ``__init__``:取基签名 + 各 register 重载的并集。"""
    params: set[str] = set()
    posonly: set[str] = set()
    has_kwargs = False
    overloads: list[ast.AST] = []
    for stmt in cls_node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and stmt.name == '__init__' or isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and _is_register_overload(stmt, '__init__'):
            overloads.append(stmt)
    for d in overloads:
        sig = _def_sig(d, strip_first=True)
        if sig is None:
            continue
        if sig.has_kwargs:
            has_kwargs = True
        params |= sig.params
        posonly |= sig.posonly
    return _Sig(params, has_kwargs, posonly)


def _is_decorated(node: ast.AST, name: str) -> bool:
    """def/class 是否带 ``@name`` / ``@mod.name``(含 ``@name(...)`` 调用形式)。"""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == name:
            return True
        if isinstance(target, ast.Attribute) and target.attr == name:
            return True
    return False


def _is_register_overload(node: ast.FunctionDef | ast.AsyncFunctionDef,
                          init_name: str) -> bool:
    """是否 ``@<init_name>.register`` 装饰的重载方法。"""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Attribute) and dec.attr == 'register' \
                and isinstance(dec.value, ast.Name) \
                and dec.value.id == init_name:
            return True
    return False


def _has_base(cls_node: ast.ClassDef, name: str) -> bool:
    """类是否有名为 ``name`` 的基类(``NamedTuple`` / ``typing.NamedTuple`` 等)。"""
    for base in cls_node.bases:
        if isinstance(base, ast.Name) and base.id == name:
            return True
        if isinstance(base, ast.Attribute) and base.attr == name:
            return True
    return False


def _namedtuple_field_names(cls_node: ast.ClassDef) -> list[str]:
    """NamedTuple 类级注解字段名(``content: str`` / ``image: T | None = None``)。"""
    names: list[str] = []
    for stmt in cls_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.append(stmt.target.id)
    return names


def _is_dataclass(cls_node: ast.ClassDef) -> bool:
    """类是否被 ``@dataclass`` 装饰(含 ``@dataclass(slots=True)`` / ``dataclasses.dataclass``)。"""
    for dec in cls_node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == 'dataclass':
            return True
        if isinstance(target, ast.Attribute) and target.attr == 'dataclass':
            return True
    return False


def _dataclass_field_names(cls_node: ast.ClassDef) -> list[str]:
    """dataclass 类级字段名(AnnAssign 注解字段 + ``= field(...)`` 赋值)。"""
    names: list[str] = []
    for stmt in cls_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            name = stmt.target.id
            if name == '_' or _is_classvar_annotation(stmt.annotation):
                continue
            names.append(name)
        elif isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call) \
                and isinstance(stmt.value.func, ast.Name) \
                and stmt.value.func.id == 'field':
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    names.append(t.id)
    return names


def _is_classvar_annotation(annotation: ast.AST | None) -> bool:
    """注解是否是 ``ClassVar`` / ``typing.ClassVar``。"""
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name) and annotation.id == 'ClassVar':
        return True
    if isinstance(annotation, ast.Attribute) and annotation.attr == 'ClassVar':
        return True
    if isinstance(annotation, ast.Subscript):
        return _is_classvar_annotation(annotation.value)
    return False


def _find_in_class(cls_node: ast.ClassDef, name: str) -> ast.AST | None:
    """在类体中找成员(方法 / 嵌套类)。"""
    for stmt in cls_node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and stmt.name == name:
            return stmt
    return None


def _collect_assigned_names(body: list[ast.stmt]) -> set[str]:
    """收集函数体/类体中的赋值名(用于识别本地遮蔽,不递归进嵌套 def 体)。"""
    names: set[str] = set()

    def _target(t: ast.AST) -> None:
        if isinstance(t, ast.Name):
            names.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                _target(e)
        elif isinstance(t, ast.Starred):
            _target(t.value)

    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(stmt.name)
            continue
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                _target(t)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.add(stmt.target.id)
        elif isinstance(stmt, (ast.AugAssign, ast.For, ast.AsyncFor)):
            _target(stmt.target)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                if item.optional_vars is not None:
                    _target(item.optional_vars)
        elif isinstance(stmt, ast.ExceptHandler) and stmt.name:
            names.add(stmt.name)
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            if isinstance(stmt, ast.Import):
                for a in stmt.names:
                    names.add(a.asname or a.name.split('.')[0])
            else:
                for a in stmt.names:
                    names.add(a.asname or a.name)
        elif isinstance(stmt, ast.NamedExpr):
            _target(stmt.target)
    return names


class _Resolver:
    """模块表 + 调用点解析。一次审计一个实例(模块解析结果跨文件缓存)。"""

    def __init__(self, src_root: Path, domains: tuple[str, ...]) -> None:
        self.src_root = src_root
        self.domains = domains
        self.modules: dict[str, ModuleInfo] = {}       # dotted → ModuleInfo
        self.by_path: dict[Path, ModuleInfo] = {}
        self._import_cache: dict[tuple[str, str], _Sig | None] = {}
        self.unresolved_by_reason: Counter = Counter()
        self.import_fail_count = 0
        self._scan_failed: list[str] = []

    # ------------------------------------------------------------------ #
    # 模块加载
    # ------------------------------------------------------------------ #
    def load_all(self) -> int:
        """加载全部扫描文件;返回文件数。单文件解析失败不中断(记入 _scan_failed)。"""
        count = 0
        for domain in self.domains:
            domain_dir = self.src_root / domain
            if not domain_dir.is_dir():
                continue
            for py in sorted(domain_dir.rglob('*.py')):
                if any(part.startswith('.') or part == '.install'
                       for part in py.parts):
                    # 隐藏目录 / 构建产物(如 src/sr_od/gui/.install/uv_cache 三方缓存)
                    continue
                self._load_file(py)
                count += 1
        return count

    def _load_file(self, path: Path) -> None:
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            return
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            self._scan_failed.append(str(path))
            return
        dotted = self._dotted_of(path)
        info = ModuleInfo(
            path=path,
            dotted=dotted,
            tree=tree,
            defs={},
            imports={},
            assign_only=set(),
            source_lines=text.splitlines(),
        )
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                info.defs[stmt.name] = stmt
            elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                self._register_import(info, stmt)
            elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                    and isinstance(stmt.targets[0], ast.Name):
                # 赋值名:def/class 已被上面收集;其余算不可解析
                info.assign_only.add(stmt.targets[0].id)
        self.modules[dotted] = info
        self.by_path[path] = info

    def _dotted_of(self, path: Path) -> str:
        rel = path.relative_to(self.src_root)
        parts = list(rel.parts)
        if parts[-1] == '__init__.py':
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        return '.'.join(parts)

    def _register_import(self, info: ModuleInfo, stmt: ast.stmt) -> None:
        if isinstance(stmt, ast.Import):
            for a in stmt.names:
                local = a.asname or a.name.split('.')[0]
                info.imports[local] = ImportInfo(kind='import', module=a.name)
        else:  # ImportFrom
            base = stmt.module or ''
            for a in stmt.names:
                if a.name == '*':
                    continue
                if stmt.level > 0:
                    # 相对导入:基于本文件 dotted 名算绝对模块
                    base_parts = info.dotted.split('.')
                    drop = stmt.level - 1
                    if drop > 0:
                        base_parts = base_parts[:-drop]
                    module = '.'.join(base_parts + ([base] if base else []))
                else:
                    module = base
                info.imports[a.asname or a.name] = ImportInfo(
                    kind='from', module=module, name=a.name)

    def _find_module(self, dotted: str) -> ModuleInfo | None:
        return self.modules.get(dotted)

    # ------------------------------------------------------------------ #
    # 签名解析
    # ------------------------------------------------------------------ #
    def resolve(self, func: ast.AST, module: ModuleInfo,
                scope_assigns: set[str],
                enclosing_class: ast.ClassDef | None) -> tuple[str, _Sig | None]:
        """解析调用表达式;返回 (状态, 签名)。

        状态取值:'ok' / 'wildcard' / 'builtin' / 'external' / 'unresolved'。
        """
        if isinstance(func, ast.Name):
            name = func.id
            if name in scope_assigns:
                self.unresolved_by_reason['local-shadow'] += 1
                return 'unresolved', None
            if name in module.defs:
                sig = _def_sig(module.defs[name])
                return ('unresolved', None) if sig is None else ('ok', sig)
            if name in module.assign_only:
                self.unresolved_by_reason['module-assign'] += 1
                return 'unresolved', None
            if name in module.imports:
                imp = module.imports[name]
                if imp.kind == 'from':
                    status, sig = self._resolve_from_import(imp, 0)
                    return status, sig
                # 模块本身被调用(``import x; x()``)→ 不可解析
                self.unresolved_by_reason['module-call'] += 1
                return 'unresolved', None
            if hasattr(builtins, name):
                return 'builtin', None
            if _is_builtin_soft(name):
                return 'builtin', None
            self.unresolved_by_reason['unknown-name'] += 1
            return 'unresolved', None

        if isinstance(func, ast.Attribute):
            return self._resolve_attribute(func, module, scope_assigns,
                                           enclosing_class)

        if isinstance(func, (ast.Call, ast.Lambda, ast.Subscript, ast.Starred)):
            # ``decorator(...)(...)`` / lambda / ``d['x'](...)``
            self.unresolved_by_reason['indirect'] += 1
            return 'unresolved', None
        self.unresolved_by_reason['other'] += 1
        return 'unresolved', None

    def _resolve_from_import(self, imp: ImportInfo, depth: int
                             ) -> tuple[str, _Sig | None]:
        if imp.module not in self.domains and not self._module_in_scope(imp.module):
            # 三方库 / 标准库:外部,不校验
            return 'external', None
        target = self._find_module(imp.module)
        if target is None:
            # 目标模块在 src 外(如标准库包)→ 外部
            if not self._module_in_scope(imp.module):
                return 'external', None
            # 在 scope 内但文件不在(不太可能)→ unresolved
            self.unresolved_by_reason['module-not-loaded'] += 1
            return 'unresolved', None
        name = imp.name or ''
        if name in target.defs:
            sig = _def_sig(target.defs[name])
            return ('unresolved', None) if sig is None else ('ok', sig)
        if name in target.assign_only:
            # 重导出 / partial 赋值:跟随一次(限深)
            if depth < REEXPORT_DEPTH_LIMIT and name in target.imports:
                return self._resolve_from_import(target.imports[name], depth + 1)
            self.unresolved_by_reason['re-export-assign'] += 1
            return 'unresolved', None
        if name in target.imports:
            sub = target.imports[name]
            if sub.kind == 'from':
                return self._resolve_from_import(sub, depth + 1)
            # ``import x.y`` 再 ``x.y.z`` 形式 → 走模块链
            if depth < REEXPORT_DEPTH_LIMIT:
                return self._resolve_module_attr(sub.module, [], target)
            self.unresolved_by_reason['re-export-module'] += 1
            return 'unresolved', None
        # AST 不可见 → import + inspect.signature 兜底
        sig = self._inspect_fallback(imp.module, name)
        if sig is None:
            self.unresolved_by_reason['import-inspect-fail'] += 1
            return 'unresolved', None
        return 'ok', sig

    def _module_in_scope(self, dotted: str) -> bool:
        """dotted 是否属于扫描域内(src/ 下三个顶层包)。"""
        return dotted.split('.')[0] in self.domains

    def _resolve_attribute(self, func: ast.Attribute, module: ModuleInfo,
                           scope_assigns: set[str],
                           enclosing_class: ast.ClassDef | None
                           ) -> tuple[str, _Sig | None]:
        parts: list[str] = []
        node: ast.AST = func
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        parts.reverse()
        if isinstance(node, ast.Name):
            base = node.id
            if base in ('self', 'cls') and enclosing_class is not None:
                sig = self._resolve_in_class(enclosing_class, parts)
                if sig is None:
                    self.unresolved_by_reason['attr-chain'] += 1
                    return 'unresolved', None
                return 'ok', sig
            if base in module.defs and isinstance(module.defs[base], ast.ClassDef):
                sig = self._resolve_in_class(module.defs[base], parts)
                if sig is None:
                    self.unresolved_by_reason['attr-chain'] += 1
                    return 'unresolved', None
                return 'ok', sig
            if base in module.imports:
                imp = module.imports[base]
                if imp.kind == 'import':
                    status, sig = self._resolve_module_attr(
                        imp.module, parts, module)
                    return status, sig
                # ``from x import y`` 的 y 上继续取属性(y.attr) — 跟随
                if imp.kind == 'from':
                    status, sig = self._resolve_from_import_attr(imp, parts, 0)
                    return status, sig
            if base in scope_assigns or base in module.assign_only:
                self.unresolved_by_reason['attr-chain'] += 1
                return 'unresolved', None
            self.unresolved_by_reason['attr-chain'] += 1
            return 'unresolved', None
        self.unresolved_by_reason['attr-chain'] += 1
        return 'unresolved', None

    def _resolve_in_class(self, cls_node: ast.ClassDef, parts: list[str]
                          ) -> _Sig | None:
        """类内解析:``Cls.method`` / ``Cls.Nested.method``。"""
        node: ast.AST = cls_node
        for attr in parts:
            if isinstance(node, ast.ClassDef):
                node = _find_in_class(node, attr)
                if node is None:
                    return None
            else:
                return None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # @staticmethod 无 self/cls,不剥首参
            return _def_sig(node, strip_first=not _is_decorated(node, 'staticmethod'))
        if isinstance(node, ast.ClassDef):
            return _def_sig(node, strip_first=False)
        return None

    def _resolve_module_attr(self, module_dotted: str, parts: list[str],
                             module: ModuleInfo) -> tuple[str, _Sig | None]:
        """``import x`` 后 ``x.a.b.C(...)``:最长前缀匹配模块,再解属性链。"""
        # 先试完整模块名(parts 全部是模块的一部分)
        for split in range(len(parts), -1, -1):
            candidate = '.'.join([module_dotted] + parts[:split])
            target = self._find_module(candidate)
            if target is not None:
                rest = parts[split:]
                if not rest:
                    self.unresolved_by_reason['module-call'] += 1
                    return 'unresolved', None
                return self._resolve_in_module(target, rest)
        if not self._module_in_scope(module_dotted):
            return 'external', None
        self.unresolved_by_reason['attr-chain'] += 1
        return 'unresolved', None

    def _resolve_in_module(self, target: ModuleInfo, names: list[str]
                           ) -> tuple[str, _Sig | None]:
        node: ast.AST | None = None
        for i, name in enumerate(names):
            if node is None:
                if name in target.defs:
                    node = target.defs[name]
                elif name in target.imports:
                    sub = target.imports[name]
                    if sub.kind == 'from':
                        status, sig = self._resolve_from_import(sub, 0)
                        if status != 'ok' or i < len(names) - 1:
                            return status, sig
                        return status, sig
                    return self._resolve_module_attr(sub.module, names[i + 1:],
                                                     target)
                else:
                    sig = self._inspect_fallback(target.dotted, name)
                    if sig is None:
                        self.unresolved_by_reason['import-inspect-fail'] += 1
                        return 'unresolved', None
                    if i < len(names) - 1:
                        return 'unresolved', None
                    return 'ok', sig
            elif isinstance(node, ast.ClassDef):
                node = _find_in_class(node, name)
                if node is None:
                    self.unresolved_by_reason['attr-chain'] += 1
                    return 'unresolved', None
            else:
                self.unresolved_by_reason['attr-chain'] += 1
                return 'unresolved', None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 模块级 def(无 self)或类内方法(有 self)——strip 由 _def_sig 决定
            strip = _looks_like_method(node) \
                and not _is_decorated(node, 'staticmethod')
            return 'ok', _def_sig(node, strip_first=strip)
        if isinstance(node, ast.ClassDef):
            return 'ok', _def_sig(node)
        self.unresolved_by_reason['attr-chain'] += 1
        return 'unresolved', None

    def _resolve_from_import_attr(self, imp: ImportInfo, parts: list[str],
                                  depth: int) -> tuple[str, _Sig | None]:
        """``from x import y`` 后 ``y.a.b(...)``。"""
        target = self._find_module(imp.module)
        if target is None:
            if not self._module_in_scope(imp.module):
                return 'external', None
            self.unresolved_by_reason['module-not-loaded'] += 1
            return 'unresolved', None
        name = imp.name or ''
        if name in target.defs:
            return self._resolve_in_module(target, [name] + parts)
        if name in target.imports:
            sub = target.imports[name]
            if sub.kind == 'from' and depth < REEXPORT_DEPTH_LIMIT:
                return self._resolve_from_import_attr(sub, parts, depth + 1)
            if sub.kind == 'import':
                return self._resolve_module_attr(sub.module, parts, target)
        self.unresolved_by_reason['attr-chain'] += 1
        return 'unresolved', None

    def _inspect_fallback(self, module_dotted: str, name: str) -> _Sig | None:
        """import + inspect.signature 兜底;失败缓存 None。"""
        key = (module_dotted, name)
        if key in self._import_cache:
            return self._import_cache[key]
        try:
            mod = importlib.import_module(module_dotted)
            obj = getattr(mod, name)
            sig = inspect.signature(obj)
        except Exception:
            self._import_cache[key] = None
            self.import_fail_count += 1
            return None
        params: set[str] = set()
        posonly: set[str] = set()
        has_kwargs = False
        for p in sig.parameters.values():
            if p.kind is inspect.Parameter.VAR_KEYWORD:
                has_kwargs = True
            elif p.kind is inspect.Parameter.POSITIONAL_ONLY:
                params.add(p.name)
                posonly.add(p.name)
            else:
                params.add(p.name)
        res = _Sig(params, has_kwargs, posonly)
        self._import_cache[key] = res
        return res


def _looks_like_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """启发式:def 首个形参是 self/cls(跨模块类内方法由 AST 路径保证,这里兜底)。"""
    a = node.args
    first = (a.posonlyargs + a.args)[0] if (a.posonlyargs or a.args) else None
    return first is not None and first.arg in ('self', 'cls')


def _is_builtin_soft(name: str) -> bool:
    """Python3 里不在 builtins 模块但仍应视为内建的少数名。"""
    return name in {'print', 'input', 'open', 'exit', 'quit', 'exec', 'eval',
                    'dir', 'vars', 'locals', 'globals', 'getattr', 'setattr',
                    'hasattr', 'callable', 'type', 'isinstance', 'issubclass',
                    'iter', 'next', 'format', 'hash', 'id', 'repr', 'bytes',
                    'bytearray', 'memoryview', 'frozenset', 'range', 'map',
                    'filter', 'zip', 'enumerate', 'sorted', 'reversed', 'sum',
                    'min', 'max', 'abs', 'all', 'any', 'round', 'pow', 'divmod',
                    'ord', 'chr', 'bin', 'oct', 'hex', 'int', 'float', 'complex',
                    'bool', 'str', 'list', 'dict', 'set', 'tuple', 'object',
                    'super', 'staticmethod', 'classmethod', 'property',
                    'functools'}


class _AuditWalker(ast.NodeVisitor):
    """带作用域追踪的 AST 遍历:统计 + 校验调用点。"""

    def __init__(self, resolver: _Resolver, module: ModuleInfo,
                 repo_root: Path, whitelist: set[tuple[str, int, str]]) -> None:
        self.r = resolver
        self.m = module
        self.repo_root = repo_root
        self.whitelist = whitelist
        self.class_stack: list[ast.ClassDef] = []
        self.scope_stack: list[set[str]] = []
        self.call_nodes = 0
        self.kw_call_nodes = 0
        self.resolved_ok = 0
        self.wildcard_skip = 0
        self.builtin_skip = 0
        self.external_skip = 0
        self.unresolved = 0
        self.violations: list[CallIssue] = []
        self.posonly_hits: list[CallIssue] = []

    # -- 结构访问 -------------------------------------------------------- #
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for d in node.decorator_list:
            self.visit(d)
        for b in node.bases:
            self.visit(b)
        for k in node.keywords:
            self.visit(k)
        self.class_stack.append(node)
        self.scope_stack.append(_collect_assigned_names(node.body))
        for stmt in node.body:
            self.visit(stmt)
        self.scope_stack.pop()
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for d in node.decorator_list:
            self.visit(d)            # 装饰器在外层作用域求值
        for a in node.args.defaults:
            self.visit(a)
        for a in node.args.kw_defaults:
            if a is not None:
                self.visit(a)
        self.scope_stack.append(_collect_assigned_names(node.body))
        for stmt in node.body:
            self.visit(stmt)
        self.scope_stack.pop()

    # -- 调用点 ---------------------------------------------------------- #
    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        self.call_nodes += 1
        kws = [k for k in node.keywords if k.arg is not None]
        if not kws:
            return
        self.kw_call_nodes += 1
        scope_assigns: set[str] = set()
        for s in self.scope_stack:
            scope_assigns |= s
        enclosing = self.class_stack[-1] if self.class_stack else None
        status, sig = self.r.resolve(node.func, self.m, scope_assigns, enclosing)
        if status == 'builtin':
            self.builtin_skip += 1
            return
        if status == 'external':
            self.external_skip += 1
            return
        if status == 'unresolved':
            self.unresolved += 1
            return
        if sig.has_kwargs:
            self.wildcard_skip += 1
            return
        bad = [k.arg for k in kws if k.arg not in sig.params]
        posonly = [k.arg for k in kws
                   if k.arg in sig.posonly and k.arg not in bad]
        if not bad and not posonly:
            self.resolved_ok += 1
            return
        rel = self._rel_path()
        if bad:
            kept = [k for k in bad
                    if (rel, node.lineno, k) not in self.whitelist]
            if kept:
                self.violations.append(self._issue(node, kept))
            if len(kept) < len(bad):
                self.resolved_ok += 1
            else:
                self.resolved_ok += 0
        if posonly:
            self.posonly_hits.append(self._issue(node, posonly))

    def _issue(self, node: ast.Call, kwargs: list[str]) -> CallIssue:
        snippet = ''
        if 0 < node.lineno <= len(self.m.source_lines):
            snippet = self.m.source_lines[node.lineno - 1].strip()
        return CallIssue(
            file=self._rel_path(),
            line=node.lineno,
            col=node.col_offset,
            snippet=snippet,
            callee=_display_func(node.func),
            kwargs=kwargs,
        )

    def _rel_path(self) -> str:
        try:
            return self.m.path.relative_to(self.repo_root).as_posix()
        except ValueError:
            return self.m.path.as_posix()


def _display_func(func: ast.AST) -> str:
    """调用表达式的展示名(不解析,纯文本)。"""
    parts: list[str] = []
    node = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    parts.reverse()
    if parts:
        return '.'.join(parts)
    return ast.unparse(func) if hasattr(ast, 'unparse') else '<call>'


def run_audit(src_root: Path,
              domains: tuple[str, ...] = DEFAULT_DOMAINS,
              whitelist: set[tuple[str, int, str]] | None = None,
              repo_root: Path | None = None) -> AuditResult:
    """全仓 kwarg 对拍审计。

    Args:
        src_root: ``src/`` 目录。
        domains: 扫描的顶层包名。
        whitelist: 豁免表 {(相对仓库根 posix 路径, 行号, kwarg 名)} —— 人工确认
            属合法转发的调用点,从违规中剔除。
        repo_root: 用于输出相对路径;缺省取 src_root 的父目录。
    """
    import time
    repo_root = repo_root or src_root.parent
    whitelist = whitelist or set()
    resolver = _Resolver(src_root, domains)
    files = resolver.load_all()

    result = AuditResult(
        files_scanned=files,
        call_nodes=0,
        kw_call_nodes=0,
        resolved_ok=0,
        wildcard_skip=0,
        builtin_skip=0,
        external_skip=0,
        unresolved=0,
        unresolved_by_reason=Counter(),
        violations=[],
        posonly_hits=[],
        sig_kwargs=[],
    )
    start = time.perf_counter()
    for dotted in sorted(resolver.modules):
        info = resolver.modules[dotted]
        walker = _AuditWalker(resolver, info, repo_root, whitelist)
        walker.visit(info.tree)
        result.call_nodes += walker.call_nodes
        result.kw_call_nodes += walker.kw_call_nodes
        result.resolved_ok += walker.resolved_ok
        result.wildcard_skip += walker.wildcard_skip
        result.builtin_skip += walker.builtin_skip
        result.external_skip += walker.external_skip
        result.unresolved += walker.unresolved
        result.violations.extend(walker.violations)
        result.posonly_hits.extend(walker.posonly_hits)
        result.unresolved_by_reason.update(resolver.unresolved_by_reason)
        # 签名侧 **kwargs(sr_od 域):AGENTS.md「构造函数显式声明参数」对拍
        if info.dotted.split('.')[0] == 'sr_od':
            for node in ast.walk(info.tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and node.args.kwarg is not None:
                    result.sig_kwargs.append((
                        info.path.relative_to(repo_root).as_posix(),
                        node.lineno,
                        node.name,
                        node.args.kwarg.arg or '',
                    ))
    result.elapsed_seconds = time.perf_counter() - start
    result.unresolved_by_reason = resolver.unresolved_by_reason
    return result


def format_report(result: AuditResult) -> str:
    """人类可读报告(CLI / 测试失败信息用)。"""
    lines: list[str] = []
    lines.append(f'扫描文件数: {result.files_scanned}')
    lines.append(f'Call 节点: {result.call_nodes} '
                 f'(含 keyword 调用 {result.kw_call_nodes})')
    lines.append(f'解析成功: {result.resolved_ok} | 通配跳过: {result.wildcard_skip} '
                 f'| 内建跳过: {result.builtin_skip} | 外部跳过: {result.external_skip}')
    lines.append(f'unresolved: {result.unresolved} '
                 f'({dict(result.unresolved_by_reason)})')
    lines.append(f'耗时: {result.elapsed_seconds:.2f}s')
    lines.append('')
    lines.append(f'== 违规(调用点 kwarg 名不在被调签名形参集): {len(result.violations)} ==')
    for v in result.violations:
        lines.append(f'  {v.file}:{v.line}:{v.col}  {v.callee}'
                     f'  kwarg={v.kwargs}  | {v.snippet}')
    lines.append('')
    lines.append(f'== 信息列(命中位置只读参数): {len(result.posonly_hits)} ==')
    for v in result.posonly_hits:
        lines.append(f'  {v.file}:{v.line}:{v.col}  {v.callee}'
                     f'  kwarg={v.kwargs}  | {v.snippet}')
    lines.append('')
    lines.append(f'== 签名侧 **kwargs(sr_od 域): {len(result.sig_kwargs)} ==')
    for f, ln, name, kwarg in result.sig_kwargs:
        lines.append(f'  {f}:{ln}  {name}  **{kwarg}')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口:``uv run python kwarg_audit.py [src根]``。"""
    import argparse
    parser = argparse.ArgumentParser(description='调用点 kwarg 名静态对拍扫描器')
    parser.add_argument('--src-root', type=Path, default=None,
                        help='src/ 目录(缺省自动探测)')
    parser.add_argument('--whitelist-file', type=Path, default=None,
                        help='豁免表文件(每行 相对路径:行号:kwarg 名, # 注释)')
    args = parser.parse_args(argv)
    src_root = args.src_root
    if src_root is None:
        here = Path(__file__).resolve()
        # sr-od-test/kwarg_audit/scanner.py → 仓库根 = parents[2]
        src_root = here.parents[2] / 'src'
    whitelist: set[tuple[str, int, str]] = set()
    if args.whitelist_file and args.whitelist_file.is_file():
        for raw in args.whitelist_file.read_text(encoding='utf-8').splitlines():
            line = raw.split('#', 1)[0].strip()
            if not line:
                continue
            parts = line.split(':')
            if len(parts) >= 3:
                with contextlib.suppress(ValueError):
                    whitelist.add((parts[0], int(parts[1]), parts[2]))
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    result = run_audit(src_root, whitelist=whitelist)
    print(format_report(result))
    return 1 if result.violations else 0


if __name__ == '__main__':
    raise SystemExit(main())
