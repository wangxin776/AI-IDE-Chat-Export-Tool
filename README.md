# AI IDE 聊天导出工具 (AI IDE Chat Export Tool)

一个功能强大的 AI IDE 聊天记录查看和导出工具，支持多种数据源的统一管理和导出。

## 🎯 项目简介

本项目是一个专门用于查看、管理和导出 AI IDE 聊天记录的 Web 应用程序。它能够从多个不同的 AI 助手数据源中提取对话数据，并提供统一的界面进行查看、搜索和导出。

### 主要功能

- **多数据源支持**：统一管理来自 5 种不同 AI 助手的对话记录
- **现代化界面**：基于 Material-UI 的深色主题设计，提供优秀的用户体验
- **强大的导出功能**：支持 HTML、JSON、Markdown 三种格式的导出
- **智能数据提取**：自动解析和转换不同格式的聊天数据
- **项目识别**：智能识别和显示对话所属的项目信息
- **设置管理**：提供可视化的设置页面，支持自定义数据源路径配置
- **路径验证**：智能验证配置路径的有效性，提供实时反馈

## 🔧 技术栈

### 前端技术

- **React 18** - 现代化的用户界面框架
- **Material-UI (MUI)** - 专业的 React UI 组件库
- **React Router** - 单页应用路由管理
- **Axios** - HTTP 客户端库
- **React Markdown** - Markdown 内容渲染

### 后端技术

- **Flask** - 轻量级 Python Web 框架
- **SQLite** - 数据库操作和查询
- **Flask-CORS** - 跨域资源共享支持

## 📊 支持的数据源

### 1. Cursor 原生对话

- **来源**：Cursor IDE 的原生 AI 聊天功能
- **数据位置**：Cursor 的 workspaceStorage 和全局存储
- **特点**：支持完整的对话历史和项目上下文

### 2. VSCode Augment 对话

- **来源**：VSCode 中的 Augment AI 助手插件
- **数据位置**：VSCode 的 workspaceStorage SQLite 数据库
- **特点**：专业的代码辅助对话记录

### 3. Cursor Augment 对话

- **来源**：Cursor IDE 中的 Augment AI 助手插件
- **数据位置**：Cursor 的 workspaceStorage（与 VSCode 格式兼容）
- **特点**：结合 Cursor 环境的 Augment 对话

### 4. IDEA Augment 对话

- **来源**：JetBrains IntelliJ IDEA 中的 Augment AI 助手插件
- **数据位置**：IDEA 的配置目录中的 XML 格式数据
- **特点**：支持 Java 开发环境的专业代码对话

### 5. PyCharm Augment 对话

- **来源**：JetBrains PyCharm 中的 Augment AI 助手插件
- **数据位置**：PyCharm 的配置目录中的 XML 格式数据
- **特点**：专门针对 Python 开发的代码辅助对话

## 🚀 安装和启动

### 环境要求

- **Node.js** 16.0+
- **Python** 3.7+
- **npm** 或 **yarn**

### 安装步骤

1. **克隆项目**

```bash
git clone <repository-url>
cd AI-IDE-Chat-Export-Tool
```

2. **安装前端依赖**

```bash
cd frontend
npm install
```

3. **构建前端生产版本**

```bash
npm run build
```

4. **安装后端依赖**

```bash
cd ../backend
pip install -r ../requirements.txt
```

### 启动应用

1. **启动后端服务器**

```bash
cd backend
python server.py
```

2. **访问应用**
   打开浏览器访问：`http://localhost:5000`

> **注意**：请确保按照上述顺序启动，先构建前端，再启动后端服务器。应用运行在 5000 端口，而不是 3000 端口。

## 💡 使用说明

### 数据源切换

1. 在页面顶部的数据源选择器中选择要查看的数据源
2. 系统会自动加载对应数据源的聊天记录
3. 支持在 5 种数据源之间无缝切换（Cursor、VSCode Augment、Cursor Augment、IDEA Augment、PyCharm Augment）

### 查看对话

1. 在聊天列表中浏览所有对话
2. 点击任意对话进入详细查看页面
3. 支持按项目、时间等信息筛选

### 导出功能

1. 在对话详情页面点击导出按钮
2. 选择导出格式：HTML、JSON 或 Markdown
3. 系统会生成包含完整对话内容的文件供下载

### 设置配置

1. 点击页面右上角的设置图标进入设置页面
2. 为每个数据源配置自定义路径（可选）
3. 系统会自动验证路径的有效性并提供反馈
4. 支持重置为默认路径或保存自定义配置

## 🎨 功能特性

### 智能项目识别

- 自动从文件路径中提取项目名称
- 支持 Git 仓库信息识别
- 智能过滤用户目录和系统目录

### 现代化 UI 设计

- 深色主题设计，护眼舒适
- 响应式布局，支持多种屏幕尺寸
- 流畅的动画和交互效果

### 强大的数据处理

- 支持复杂的 SQLite 数据库解析
- 智能的 JSON 和 XML 数据转换
- 完善的错误处理和异常恢复
- 多格式数据源统一处理

### 高级配置管理

- 可视化的设置界面，支持路径自定义配置
- 实时路径验证和状态反馈
- 配置持久化存储和一键重置功能
- 智能默认路径检测和回退机制

## 🔄 项目改进

### 相比原始项目的增强功能

本项目基于 [cursor-view](https://github.com/saharmor/cursor-view) 进行二次开发，主要增强包括：

1. **多数据源支持**：从单一 Cursor 数据源扩展到五种数据源
2. **统一导出功能**：支持多种格式的标准化导出
3. **现代化界面**：全新的 Material-UI 设计和深色主题
4. **智能数据提取**：更强大的数据解析和转换能力
5. **项目识别优化**：更准确的项目名称识别算法
6. **错误处理增强**：更完善的异常处理和用户反馈
7. **设置管理系统**：可视化的配置界面和路径管理
8. **JetBrains IDE 支持**：新增 IDEA 和 PyCharm Augment 数据源支持

### 致谢

感谢 [saharmor/cursor-view](https://github.com/saharmor/cursor-view) 项目提供的基础架构和灵感。本项目在其基础上进行了大量的功能扩展和用户体验优化。

## 📁 项目结构

```
cursor-view/
├── frontend/                 # React前端应用
│   ├── src/
│   │   ├── components/      # React组件
│   │   │   ├── ChatDetail.js      # 对话详情页面
│   │   │   ├── ChatList.js        # 对话列表页面
│   │   │   ├── Header.js          # 页面头部组件
│   │   │   ├── PathConfigCard.js  # 路径配置卡片
│   │   │   └── SettingsPage.js    # 设置页面
│   │   ├── constants/       # 配置常量
│   │   │   └── dataSourceConfig.js # 数据源配置
│   │   └── ...
│   ├── build/               # 构建输出目录
│   └── package.json
├── backend/                 # Python后端服务
│   ├── server.py           # Flask主服务器
│   ├── config_manager.py   # 配置管理器
│   ├── path_validator.py   # 路径验证器
│   ├── augment_extractor.py # Augment数据提取器
│   ├── cursor_augment_extractor.py # Cursor Augment提取器
│   ├── idea_augment_extractor.py   # IDEA Augment提取器
│   ├── pycharm_augment_extractor.py # PyCharm Augment提取器
│   ├── conversation_parser.py      # 对话解析器
│   ├── output_formatter.py        # 输出格式化器
│   └── ...
├── config.json             # 应用配置文件
├── requirements.txt        # Python依赖
├── README.md              # 中文说明文档
└── README_EN.md           # 英文说明文档
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request 来改进项目！

### 代码规范

- 前端：遵循 React 和 JavaScript 最佳实践
- 后端：遵循 PEP 8 Python 代码规范
- 提交信息：使用清晰的提交信息描述更改
- **分支管理**：请将所有代码贡献提交到 `dev` 分支，而非 `main` 分支

## 📄 许可证

本项目采用 [Apache License 2.0](LICENSE) 许可证。

## ⚙️ 环境配置

### 可选环境变量

```bash
# 启用Cursor聊天诊断模式（用于调试）
export CURSOR_CHAT_DIAGNOSTICS=1

# 自定义服务器端口（默认5000）
export PORT=5000
```

### 数据存储位置

不同操作系统下的数据存储位置：

**Windows**:

- Cursor: `%APPDATA%\Cursor\User\workspaceStorage`
- VSCode: `%APPDATA%\Code\User\workspaceStorage`
- IDEA: `%APPDATA%\JetBrains\IntelliJIdea[版本]\options`
- PyCharm: `%APPDATA%\JetBrains\PyCharm[版本]\options`

**macOS**:

- Cursor: `~/Library/Application Support/Cursor/User/workspaceStorage`
- VSCode: `~/Library/Application Support/Code/User/workspaceStorage`
- IDEA: `~/Library/Application Support/JetBrains/IntelliJIdea[版本]/options`
- PyCharm: `~/Library/Application Support/JetBrains/PyCharm[版本]/options`

**Linux**:

- Cursor: `~/.config/Cursor/User/workspaceStorage`
- VSCode: `~/.config/Code/User/workspaceStorage`
- IDEA: `~/.config/JetBrains/IntelliJIdea[版本]/options`
- PyCharm: `~/.config/JetBrains/PyCharm[版本]/options`

## 🔧 故障排除

### 常见问题

**Q: 启动后无法访问 localhost:5000**
A: 请确保：

1. 后端服务器已正确启动且无错误信息
2. 端口 5000 未被其他程序占用
3. 防火墙未阻止该端口

**Q: 找不到聊天数据**
A: 请检查：

1. 对应的 IDE 是否已安装并使用过 AI 功能
2. 数据源选择是否正确
3. 相关插件是否已安装（如 Augment 插件）
4. 在设置页面检查数据源路径配置是否正确
5. 确认路径验证状态显示为有效

**Q: 导出功能不工作**
A: 请确认：

1. 浏览器允许文件下载
2. 有足够的磁盘空间
3. 对话数据不为空

**Q: 前端构建失败**
A: 尝试：

1. 删除 `node_modules`文件夹后重新 `npm install`
2. 检查 Node.js 版本是否符合要求
3. 清除 npm 缓存：`npm cache clean --force`

### 开发模式

如需进行开发，可以分别启动前后端：

```bash
# 启动前端开发服务器（端口3000）
cd frontend
npm start

# 启动后端服务器（端口5000）
cd backend
python server.py
```

---

**感谢使用 AI IDE 聊天导出工具！** 🚀

