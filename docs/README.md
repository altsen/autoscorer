# AutoScorer 技术文档

## 文档概览

本目录包含 AutoScorer 自动评分系统的完整技术文档，为开发者、用户和运维人员提供全面的指导。

## 文档结构

### 📖 基础文档
- **[概述](overview.md)** - 系统概述、架构设计和技术特性
- **[快速开始](getting-started.md)** - 安装配置、快速上手指南
- **[工作区规范](workspace-spec.md)** - 标准工作区结构和数据格式

### 🔧 开发文档
- **[CLI 使用指南](cli-guide.md)** - 命令行工具详细说明
- **[API 参考](api-reference.md)** - REST API 接口文档
- **[评分器开发](scorer-development.md)** - 自定义评分器开发指南
- **[配置管理](configuration.md)** - 配置文件和环境变量

### 🚀 运维文档
- **[部署指南](deployment.md)** - 生产环境部署和运维
- **[执行器配置](executors.md)** - Docker 和 Kubernetes 执行器
- **[错误处理](error-handling.md)** - 错误码和故障排查
- **[输出标准](output-standards.md)** - 标准化输出格式规范

### 🔌 集成文档
- **[平台集成](platform-integration.md)** - 第三方平台对接指南
- **[扩展开发](extensions.md)** - 系统扩展和插件开发

## 版本信息

- **当前版本**: v2.0.0
- **更新日期**: 2025-09-01
- **兼容性**: Python 3.10+, Docker 20.10+

## 快速导航

### 新用户入门
1. 阅读 [概述](overview.md) 了解系统整体架构
2. 按照 [快速开始](getting-started.md) 搭建开发环境
3. 学习 [工作区规范](workspace-spec.md) 准备数据
4. 使用 [CLI 指南](cli-guide.md) 执行第一个评分任务

### 开发者指南
1. 参考 [API 文档](api-reference.md) 集成系统
2. 阅读 [评分器开发](scorer-development.md) 创建自定义算法
3. 查看 [配置管理](configuration.md) 优化系统配置
4. 了解 [输出标准](output-standards.md) 确保兼容性

### 运维人员指南
1. 学习 [部署指南](deployment.md) 配置生产环境
2. 掌握 [执行器配置](executors.md) 管理计算资源
3. 熟悉 [错误处理](error-handling.md) 进行故障排查
4. 使用监控工具保证系统稳定性

### 平台集成商指南
1. 阅读 [平台集成](platform-integration.md) 了解对接方案
2. 参考 [扩展开发](extensions.md) 实现定制功能
3. 确保符合 [输出标准](output-standards.md) 要求

## 贡献指南

### 文档更新流程
1. 在 `docs/` 目录下创建或修改文档
2. 确保文档格式符合 Markdown 规范
3. 更新本 README.md 的导航链接
4. 提交 Pull Request 进行评审

### 文档规范
- 使用清晰的标题层级结构
- 提供完整的代码示例
- 包含必要的图表和流程图
- 保持文档的准确性和时效性

## 支持与反馈

- **GitHub Issues**: 报告 Bug 和功能请求
- **技术讨论**: 参与项目讨论
- **文档反馈**: 提供文档改进建议

## 许可证

本文档基于 MIT 许可证发布，详情请参见项目根目录的 LICENSE 文件。
