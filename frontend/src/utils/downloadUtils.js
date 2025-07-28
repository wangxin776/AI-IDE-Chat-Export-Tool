/**
 * 下载工具函数
 * 提供批量下载相关的工具函数和API调用
 */

import axios from 'axios';

/**
 * 批量下载API类
 */
export class BatchDownloadAPI {
  /**
   * 创建批量导出任务
   * @param {Array} sessionIds - 会话ID列表
   * @param {string} format - 导出格式 ('html', 'json', 'markdown')
   * @param {string} source - 数据源
   * @returns {Promise<Object>} 任务信息
   */
  static async createBatchExportTask(sessionIds, format, source) {
    try {
      const response = await axios.post('/api/chats/batch-export', {
        session_ids: sessionIds,
        format: format,
        source: source
      });
      return response.data;
    } catch (error) {
      console.error('创建批量导出任务失败:', error);
      throw new Error(
        error.response?.data?.error || '创建批量导出任务失败'
      );
    }
  }

  /**
   * 获取任务状态
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 任务状态信息
   */
  static async getTaskStatus(taskId) {
    try {
      const response = await axios.get(`/api/batch-download/${taskId}/status`);
      return response.data;
    } catch (error) {
      console.error('获取任务状态失败:', error);
      throw new Error(
        error.response?.data?.error || '获取任务状态失败'
      );
    }
  }

  /**
   * 取消任务
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 取消结果
   */
  static async cancelTask(taskId) {
    try {
      const response = await axios.post(`/api/batch-download/${taskId}/cancel`);
      return response.data;
    } catch (error) {
      console.error('取消任务失败:', error);
      throw new Error(
        error.response?.data?.error || '取消任务失败'
      );
    }
  }

  /**
   * 下载完成的文件
   * @param {string} taskId - 任务ID
   * @param {string} filename - 文件名（可选）
   * @returns {Promise<void>}
   */
  static async downloadFile(taskId, filename) {
    try {
      const response = await axios.get(`/api/batch-download/${taskId}/file`, {
        responseType: 'blob'
      });

      const blob = response.data;
      if (!blob || blob.size === 0) {
        throw new Error('下载的文件为空');
      }

      // 从响应头获取文件名，如果没有则使用默认名称
      const contentDisposition = response.headers['content-disposition'];
      let downloadFilename = filename;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          downloadFilename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      if (!downloadFilename) {
        downloadFilename = `batch_export_${taskId.slice(0, 8)}.zip`;
      }

      // 创建下载链接
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = downloadFilename;
      
      // 触发下载
      document.body.appendChild(link);
      link.click();
      
      // 清理
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error('下载文件失败:', error);
      throw new Error(
        error.response?.data?.error || '下载文件失败'
      );
    }
  }
}

/**
 * 任务状态枚举
 */
export const TaskStatus = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled'
};

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} 格式化的文件大小
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 格式化持续时间
 * @param {number} seconds - 秒数
 * @returns {string} 格式化的时间字符串
 */
export function formatDuration(seconds) {
  if (seconds < 60) {
    return `${Math.round(seconds)}秒`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}分${remainingSeconds}秒`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}小时${minutes}分`;
  }
}

/**
 * 估算剩余时间
 * @param {number} progress - 进度 (0-1)
 * @param {number} elapsedTime - 已用时间（秒）
 * @returns {string} 估算的剩余时间
 */
export function estimateRemainingTime(progress, elapsedTime) {
  if (progress <= 0 || progress >= 1) {
    return '计算中...';
  }
  
  const totalEstimatedTime = elapsedTime / progress;
  const remainingTime = totalEstimatedTime - elapsedTime;
  
  return formatDuration(remainingTime);
}

/**
 * 获取任务状态的显示文本
 * @param {string} status - 任务状态
 * @returns {string} 显示文本
 */
export function getStatusText(status) {
  const statusMap = {
    [TaskStatus.PENDING]: '等待中',
    [TaskStatus.PROCESSING]: '处理中',
    [TaskStatus.COMPLETED]: '已完成',
    [TaskStatus.FAILED]: '失败',
    [TaskStatus.CANCELLED]: '已取消'
  };
  
  return statusMap[status] || '未知状态';
}

/**
 * 获取任务状态的颜色
 * @param {string} status - 任务状态
 * @returns {string} Material-UI颜色名称
 */
export function getStatusColor(status) {
  const colorMap = {
    [TaskStatus.PENDING]: 'info',
    [TaskStatus.PROCESSING]: 'primary',
    [TaskStatus.COMPLETED]: 'success',
    [TaskStatus.FAILED]: 'error',
    [TaskStatus.CANCELLED]: 'warning'
  };
  
  return colorMap[status] || 'default';
}

/**
 * 验证选择的会话数量
 * @param {number} count - 选择的数量
 * @returns {Object} 验证结果 {isValid, message}
 */
export function validateSelectionCount(count) {
  if (count === 0) {
    return {
      isValid: false,
      message: '请至少选择一个对话'
    };
  }
  
  if (count > 100) {
    return {
      isValid: false,
      message: '单次最多只能选择100个对话'
    };
  }
  
  return {
    isValid: true,
    message: ''
  };
}

/**
 * 生成唯一的临时ID
 * @returns {string} 唯一ID
 */
export function generateTempId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * 防抖函数
 * @param {Function} func - 要防抖的函数
 * @param {number} wait - 等待时间（毫秒）
 * @returns {Function} 防抖后的函数
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * 节流函数
 * @param {Function} func - 要节流的函数
 * @param {number} limit - 限制时间（毫秒）
 * @returns {Function} 节流后的函数
 */
export function throttle(func, limit) {
  let inThrottle;
  return function executedFunction(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}
