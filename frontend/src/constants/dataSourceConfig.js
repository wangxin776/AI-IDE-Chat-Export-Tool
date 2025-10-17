/**
 * 数据源配置文件
 * 集中管理所有数据源的显示配置信息
 */

export const DATA_SOURCE_CONFIG = {
  cursor: {
    displayName: "Cursor",
    historyTitle: "Cursor Chat History",
    appTitle: "AI IDE Chat Export Tool",
    description: "Cursor IDE原生对话",
  },
  augment: {
    displayName: "VSCode Augment",
    historyTitle: "VSCode Augment Chat History",
    appTitle: "AI IDE Chat Export Tool",
    description: "VSCode中的Augment插件对话",
  },
  "cursor-augment": {
    displayName: "Cursor Augment",
    historyTitle: "Cursor Augment Chat History",
    appTitle: "AI IDE Chat Export Tool",
    description: "Cursor中的Augment插件对话",
  },
  "idea-augment": {
    displayName: "IDEA Augment",
    historyTitle: "IDEA Augment Chat History",
    appTitle: "AI IDE Chat Export Tool",
    description: "JetBrains IDEA中的Augment插件对话",
  },
  "pycharm-augment": {
    displayName: "PyCharm Augment",
    historyTitle: "PyCharm Augment Chat History",
    appTitle: "AI IDE Chat Export Tool",
    description: "JetBrains PyCharm中的Augment插件对话",
  },
  warp: {
    displayName: "Warp Terminal",
    historyTitle: "Warp AI Chat History",
    appTitle: "AI IDE Chat Export Tool",
    description: "Warp Terminal中的AI助手对话",
  },
};

/**
 * 根据数据源获取配置信息
 * @param {string} dataSource - 数据源标识
 * @returns {object} 数据源配置对象
 */
export const getDataSourceConfig = (dataSource) => {
  return DATA_SOURCE_CONFIG[dataSource] || DATA_SOURCE_CONFIG.cursor;
};

/**
 * 获取所有可用的数据源列表
 * @returns {Array} 数据源配置数组
 */
export const getAllDataSources = () => {
  return Object.keys(DATA_SOURCE_CONFIG).map((key) => ({
    value: key,
    ...DATA_SOURCE_CONFIG[key],
  }));
};
