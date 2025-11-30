# Cloud Sync Status Implementation Plan

## 概述
实现Quick Notes的云端同步状态管理和用户界面改进，包括缓存过期检测、状态显示和完整的操作按钮。

## 核心功能需求

### 1. 缓存过期检测系统
- **触发时机**：
  - Shift+F7打开Quick Notes窗口时
  - 点击Force Sync按钮时
- **检测逻辑**：
  - 下载云端`overall_notes_index.json`
  - 与本地缓存的索引进行比较
  - 根据`updated_at`时间戳判断每个笔记的状态

### 2. 笔记状态分类
- **New**：云端有但本地没有的笔记
- **Updated**：云端版本比本地版本新
- **Current**：本地版本与云端版本一致
- **Local Only**：仅存在于本地的笔记
- **Syncing**：正在同步中的笔记

### 3. UI界面改进
- **新增Status列**：显示笔记的同步状态
- **改进Actions列**：4个明确的操作按钮
  1. **Open** (📖)：打开笔记进行编辑
  2. **Refresh** (🔄)：强制从云端下载最新版本
  3. **Public URL** (🔗)：获取公共分享链接
  4. **Delete** (🗑️)：删除笔记

## 详细实现任务

### Task 1: 实现笔记状态检测系统
**文件**: `fastshot/notes_manager.py`

**功能**:
- 添加`check_notes_sync_status()`方法
- 实现本地与云端索引的比较逻辑
- 返回每个笔记的状态信息

**实现要点**:
```python
def check_notes_sync_status(self) -> Dict[str, Dict]:
    """
    检查所有笔记的同步状态
    返回格式: {note_id: {"status": "updated|current|new|local_only", "cloud_updated_at": "...", "local_updated_at": "..."}}
    """
    # 1. 获取云端索引
    # 2. 获取本地缓存索引
    # 3. 比较时间戳
    # 4. 返回状态字典
```

### Task 2: 扩展缓存管理器
**文件**: `fastshot/notes_cache.py`

**功能**:
- 添加`compare_with_cloud_index()`方法
- 实现缓存状态元数据管理
- 支持单个笔记的状态更新

### Task 3: 改进UI状态显示
**文件**: `fastshot/quick_notes_ui.py`

**功能**:
- 在notes_tree中添加"Status"列
- 实现状态图标和颜色显示
- 添加状态刷新机制

**UI设计**:
```
| Title | Code | Created | Updated | Status | Actions |
|-------|------|---------|---------|--------|---------|
| xxx   | BT1P | 08/03   | 08/03   | 🔄 Updated | 📖🔄🔗🗑️ |
| ttt111| 9EN9 | 08/02   | 08/03   | ✅ Current | 📖🔄🔗🗑️ |
```

### Task 4: 实现Actions按钮功能
**文件**: `fastshot/quick_notes_ui.py`

**功能**:
- 替换现有的模糊图标
- 实现4个具体的操作按钮
- 添加按钮点击事件处理
- 实现按钮状态管理（启用/禁用）

**按钮实现**:
```python
def _create_action_buttons(self, note_id: str, status: str) -> str:
    """创建操作按钮HTML或按钮组件"""
    buttons = []
    buttons.append("📖")  # Open - 总是可用
    buttons.append("🔄")  # Refresh - 有云端版本时可用
    buttons.append("🔗")  # Public URL - 云端存在时可用
    buttons.append("🗑️")  # Delete - 总是可用
    return " ".join(buttons)
```

### Task 5: 实现自动同步检查
**文件**: `fastshot/quick_notes_ui.py`

**功能**:
- 在`show_window()`中添加状态检查
- 在`_force_sync()`中添加状态更新
- 实现后台状态检查机制

### Task 6: 实现单个笔记刷新功能
**文件**: `fastshot/notes_manager.py`, `fastshot/quick_notes_ui.py`

**功能**:
- 添加`refresh_note_from_cloud()`方法
- 强制从云端下载指定笔记
- 更新本地缓存和UI显示

## 测试计划

### 自动化测试
创建`test_cloud_sync_status.py`测试以下场景：
1. 状态检测逻辑正确性
2. 缓存比较算法
3. UI状态更新机制
4. 按钮功能响应

### 人工交互测试用例

#### 测试环境准备
1. 准备两台机器（Host A 和 Host B）
2. 确保两台机器都能访问同一个S3存储
3. 在两台机器上都安装最新版本的Fastshot

#### Test Case 1: 基本状态显示测试
**步骤**:
1. 在Host A上打开Quick Notes (Shift+F7)
2. 创建一个新笔记"Test Note 1"
3. 保存并确认同步到云端
4. 在Host B上打开Quick Notes
5. 点击Force Sync

**预期结果**:
- Host B的列表中应显示"Test Note 1"
- Status列应显示"🆕 New"状态
- Actions列应显示4个按钮：📖🔄🔗🗑️

#### Test Case 2: 缓存过期检测测试
**步骤**:
1. 在Host A上打开已存在的笔记"Test Note 1"
2. 修改内容并保存
3. 在Host B上打开Quick Notes（不要点击Force Sync）
4. 观察"Test Note 1"的状态
5. 点击Force Sync
6. 再次观察状态变化

**预期结果**:
- Force Sync前：Status应显示"✅ Current"（基于本地缓存）
- Force Sync后：Status应显示"🔄 Updated"（检测到云端更新）

#### Test Case 3: Refresh按钮功能测试
**步骤**:
1. 在Host B上找到状态为"🔄 Updated"的笔记
2. 点击该笔记的Refresh按钮（🔄）
3. 观察笔记内容和状态变化

**预期结果**:
- 笔记内容应更新为最新版本
- Status应变为"✅ Current"
- 如果笔记当前在编辑器中打开，内容应自动刷新

#### Test Case 4: Actions按钮完整性测试
**步骤**:
1. 选择一个笔记，逐个测试每个Action按钮
2. 📖 Open：应在右侧编辑器中打开笔记
3. 🔄 Refresh：应从云端下载最新版本
4. 🔗 Public URL：应生成并复制公共链接
5. 🗑️ Delete：应弹出确认对话框并删除笔记

**预期结果**:
- 每个按钮都应有明确的功能响应
- 按钮应有适当的启用/禁用状态
- 操作完成后应有状态反馈

#### Test Case 5: 状态一致性测试
**步骤**:
1. 在Host A上创建、修改、删除笔记
2. 在Host B上执行各种同步操作
3. 交替在两台机器上进行操作
4. 观察状态显示的一致性

**预期结果**:
- 状态显示应准确反映实际的同步情况
- 不应出现状态显示错误或延迟
- 冲突情况应有合理的处理机制

### 性能测试
- 大量笔记（100+）的状态检查性能
- 频繁同步操作的响应时间
- 网络异常情况的处理

## 风险控制

### 向后兼容性
- 保持现有API接口不变
- 新功能作为增强，不影响基本功能
- 提供降级机制（云端不可用时的本地模式）

### 错误处理
- 网络连接失败的优雅处理
- 云端数据损坏的恢复机制
- 并发操作的冲突解决

### 用户体验
- 状态检查不应阻塞UI
- 提供操作进度反馈
- 清晰的错误信息提示

## 实现优先级
1. **高优先级**：状态检测系统、UI状态显示
2. **中优先级**：Actions按钮功能、自动同步检查
3. **低优先级**：性能优化、高级错误处理

这个实现计划将显著改善Quick Notes的云端同步体验，让用户能够清楚地了解笔记的同步状态并进行精确的操作控制。