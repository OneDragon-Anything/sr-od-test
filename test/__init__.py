"""SR 测试公共包(包标识,无导出)。

历史:曾定义 ``SrTestBase``(unittest.TestCase + 每 test 方法实例化重初始化 ctx/OCR)和配套
``MockController``。测试慢的根因正是 SrTestBase —— pytest 对 unittest.TestCase 每个 test 方法
都实例化一次,而 ``SrTestBase.__init__`` 每次都 ``init_by_config + load_instance_config +
ocr.init_model``(~7s/次)→ N 方法 × ~7s。现已全部迁移至 ``conftest.py``:

- ``test_context`` fixture(session 级 ctx/OCR 复用)替代 SrTestBase 的 ctx;
- ``test_image_dir`` fixture 替代 ``SrTestBase.get_test_image``(读本地 png);
- 所有测试改为 pytest 函数风格(``assert`` + ``pytest.raises`` / ``pytest.approx``)。

本文件保留为 Python 包标识。
"""
