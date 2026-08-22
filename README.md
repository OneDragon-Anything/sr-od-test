# SR测试项目

需要将本目录设置成 test source folder

## 测试纪律(硬规则)

1. **`test_context` 是 session 级共享**(conftest):改其属性(`run_context`/`controller` 等)一律
   `monkeypatch.setattr`(自动还原);裸赋值会污染后续**别的测试文件**(单跑必过/全量必挂的假
   flaky),conftest 有 autouse 守卫(警告+还原),但守卫不是写裸赋值的许可。
2. **测试不写真实 `.debug/` 路径**:落盘一律 `tmp_path` 或 monkeypatch 重定向目标模块的
   `_DIR` 常量;`finally` 还原动过的外部状态(文件备份-恢复、flag 清理)。
3. **fixture 驱动的 op 流程测试**用 `test/harness/fixture_controller.py`(`FixtureController`
   + `WatchdogOperationMixin` + `enter_running_state`/`reset_running_state`);运行态前置/复位
   已封装在 helper 里,别手写 `_run_state` 裸赋值。
