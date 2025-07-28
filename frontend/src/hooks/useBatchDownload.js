/**
 * 批量下载自定义Hook
 * 管理批量下载的状态、API调用和错误处理
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { 
  BatchDownloadAPI, 
  TaskStatus, 
  validateSelectionCount 
} from '../utils/downloadUtils';

/**
 * 批量下载Hook
 * @param {Object} options - 配置选项
 * @returns {Object} Hook返回的状态和方法
 */
export function useBatchDownload(options = {}) {
  const {
    pollingInterval = 2000, // 轮询间隔（毫秒）
    maxRetries = 3, // 最大重试次数
    onSuccess = () => {}, // 成功回调
    onError = () => {}, // 错误回调
    onProgress = () => {} // 进度回调
  } = options;

  // 状态管理
  const [isLoading, setIsLoading] = useState(false);
  const [currentTask, setCurrentTask] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [taskHistory, setTaskHistory] = useState([]);

  // 引用管理
  const pollingRef = useRef(null);
  const retryCountRef = useRef(0);
  const startTimeRef = useRef(null);

  /**
   * 清理轮询
   */
  const clearPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  /**
   * 开始轮询任务状态
   */
  const startPolling = useCallback((taskId) => {
    clearPolling();
    
    pollingRef.current = setInterval(async () => {
      try {
        const status = await BatchDownloadAPI.getTaskStatus(taskId);
        
        setCurrentTask(status);
        setProgress(status.progress || 0);
        
        // 调用进度回调
        onProgress(status);
        
        // 检查任务是否完成
        if ([TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED].includes(status.status)) {
          clearPolling();
          setIsLoading(false);
          
          if (status.status === TaskStatus.COMPLETED) {
            onSuccess(status);
          } else if (status.status === TaskStatus.FAILED) {
            setError(status.error_message || '任务执行失败');
            onError(new Error(status.error_message || '任务执行失败'));
          }
          
          // 添加到历史记录
          setTaskHistory(prev => [status, ...prev.slice(0, 9)]); // 保留最近10条记录
        }
        
        retryCountRef.current = 0; // 重置重试计数
        
      } catch (err) {
        console.error('轮询任务状态失败:', err);
        retryCountRef.current++;
        
        if (retryCountRef.current >= maxRetries) {
          clearPolling();
          setIsLoading(false);
          setError('获取任务状态失败，请刷新页面重试');
          onError(err);
        }
      }
    }, pollingInterval);
  }, [clearPolling, pollingInterval, maxRetries, onSuccess, onError, onProgress]);

  /**
   * 创建批量下载任务
   */
  const createBatchDownload = useCallback(async (sessionIds, format, source) => {
    try {
      // 验证选择数量
      const validation = validateSelectionCount(sessionIds.length);
      if (!validation.isValid) {
        throw new Error(validation.message);
      }

      setIsLoading(true);
      setError(null);
      setProgress(0);
      startTimeRef.current = Date.now();

      // 创建任务
      const taskInfo = await BatchDownloadAPI.createBatchExportTask(sessionIds, format, source);
      
      setCurrentTask({
        ...taskInfo,
        session_ids: sessionIds,
        format_type: format,
        source: source,
        created_at: new Date().toISOString()
      });

      // 开始轮询状态
      startPolling(taskInfo.task_id);

      return taskInfo;
      
    } catch (err) {
      setIsLoading(false);
      setError(err.message);
      onError(err);
      throw err;
    }
  }, [startPolling, onError]);

  /**
   * 取消当前任务
   */
  const cancelCurrentTask = useCallback(async () => {
    if (!currentTask?.task_id) {
      return;
    }

    try {
      await BatchDownloadAPI.cancelTask(currentTask.task_id);
      clearPolling();
      setIsLoading(false);
      setCurrentTask(prev => prev ? { ...prev, status: TaskStatus.CANCELLED } : null);
      
    } catch (err) {
      console.error('取消任务失败:', err);
      setError('取消任务失败');
      onError(err);
    }
  }, [currentTask?.task_id, clearPolling, onError]);

  /**
   * 下载完成的文件
   */
  const downloadFile = useCallback(async (taskId, filename) => {
    try {
      await BatchDownloadAPI.downloadFile(taskId, filename);
    } catch (err) {
      setError('下载文件失败');
      onError(err);
      throw err;
    }
  }, [onError]);

  /**
   * 重置状态
   */
  const reset = useCallback(() => {
    clearPolling();
    setIsLoading(false);
    setCurrentTask(null);
    setError(null);
    setProgress(0);
    retryCountRef.current = 0;
    startTimeRef.current = null;
  }, [clearPolling]);

  /**
   * 清除错误
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * 获取任务统计信息
   */
  const getTaskStats = useCallback(() => {
    if (!currentTask) {
      return null;
    }

    const elapsedTime = startTimeRef.current 
      ? (Date.now() - startTimeRef.current) / 1000 
      : 0;

    return {
      elapsedTime,
      completedCount: currentTask.completed_count || 0,
      totalCount: currentTask.total_count || 0,
      failedCount: currentTask.failed_sessions?.length || 0,
      progress: progress,
      status: currentTask.status
    };
  }, [currentTask, progress]);

  /**
   * 检查是否可以开始新任务
   */
  const canStartNewTask = useCallback(() => {
    return !isLoading && (!currentTask || 
      [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED].includes(currentTask.status));
  }, [isLoading, currentTask]);

  // 清理副作用
  useEffect(() => {
    return () => {
      clearPolling();
    };
  }, [clearPolling]);

  return {
    // 状态
    isLoading,
    currentTask,
    error,
    progress,
    taskHistory,
    
    // 方法
    createBatchDownload,
    cancelCurrentTask,
    downloadFile,
    reset,
    clearError,
    
    // 工具方法
    getTaskStats,
    canStartNewTask
  };
}

/**
 * 简化版批量下载Hook，用于快速集成
 */
export function useSimpleBatchDownload() {
  const [selectedSessions, setSelectedSessions] = useState(new Set());
  const [batchMode, setBatchMode] = useState(false);

  const batchDownload = useBatchDownload({
    onSuccess: (taskInfo) => {
      console.log('批量下载完成:', taskInfo);
    },
    onError: (error) => {
      console.error('批量下载失败:', error);
    }
  });

  /**
   * 切换会话选择状态
   */
  const toggleSessionSelection = useCallback((sessionId) => {
    setSelectedSessions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sessionId)) {
        newSet.delete(sessionId);
      } else {
        newSet.add(sessionId);
      }
      return newSet;
    });
  }, []);

  /**
   * 全选/反选
   */
  const toggleSelectAll = useCallback((allSessionIds) => {
    setSelectedSessions(prev => {
      if (prev.size === allSessionIds.length) {
        return new Set(); // 全部取消选择
      } else {
        return new Set(allSessionIds); // 全部选择
      }
    });
  }, []);

  /**
   * 清除选择
   */
  const clearSelection = useCallback(() => {
    setSelectedSessions(new Set());
  }, []);

  /**
   * 开始批量下载
   */
  const startBatchDownload = useCallback(async (format, source) => {
    const sessionIds = Array.from(selectedSessions);
    return await batchDownload.createBatchDownload(sessionIds, format, source);
  }, [selectedSessions, batchDownload]);

  return {
    // 选择状态
    selectedSessions,
    batchMode,
    setBatchMode,
    
    // 选择方法
    toggleSessionSelection,
    toggleSelectAll,
    clearSelection,
    startBatchDownload,
    
    // 批量下载状态和方法
    ...batchDownload
  };
}
