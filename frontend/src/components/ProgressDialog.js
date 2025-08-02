/**
 * 进度显示对话框组件
 * 显示批量下载的实时进度、状态和操作按钮
 */

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  LinearProgress,
  Typography,
  Box,
  Chip,
  Alert,
  List,
  ListItem,
  ListItemText,
  Divider,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  Download as DownloadIcon,
  Cancel as CancelIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { 
  getStatusText, 
  getStatusColor, 
  formatDuration, 
  estimateRemainingTime,
  TaskStatus 
} from '../utils/downloadUtils';

/**
 * 进度对话框组件
 */
const ProgressDialog = ({
  open,
  onClose,
  taskInfo,
  progress,
  onCancel,
  onDownload,
  onRetry,
  isLoading = false
}) => {
  if (!taskInfo) {
    return null;
  }

  const {
    task_id,
    status,
    completed_count = 0,
    total_count = 0,
    failed_sessions = [],
    error_message,
    created_at,
    started_at,
    completed_at
  } = taskInfo;

  // 计算时间信息
  const getTimeInfo = () => {
    const now = new Date();
    const createdTime = new Date(created_at);
    const startedTime = started_at ? new Date(started_at) : null;
    const completedTime = completed_at ? new Date(completed_at) : null;

    let elapsedTime = 0;
    if (startedTime) {
      elapsedTime = (completedTime || now).getTime() - startedTime.getTime();
      elapsedTime = Math.max(0, elapsedTime / 1000); // 转换为秒
    }

    return {
      elapsedTime,
      estimatedRemaining: status === TaskStatus.PROCESSING 
        ? estimateRemainingTime(progress, elapsedTime)
        : null
    };
  };

  const timeInfo = getTimeInfo();

  // 获取状态图标
  const getStatusIcon = () => {
    switch (status) {
      case TaskStatus.COMPLETED:
        return <CheckCircleIcon color="success" />;
      case TaskStatus.FAILED:
        return <ErrorIcon color="error" />;
      case TaskStatus.CANCELLED:
        return <CancelIcon color="warning" />;
      case TaskStatus.PROCESSING:
        return <InfoIcon color="primary" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  // 是否显示取消按钮
  const showCancelButton = [TaskStatus.PENDING, TaskStatus.PROCESSING].includes(status);
  
  // 是否显示下载按钮
  const showDownloadButton = status === TaskStatus.COMPLETED;
  
  // 是否显示重试按钮
  const showRetryButton = status === TaskStatus.FAILED;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      disableEscapeKeyDown={showCancelButton} // 处理中时禁用ESC关闭
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {getStatusIcon()}
          <Typography variant="h6">
            批量下载进度
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip 
            label={getStatusText(status)} 
            color={getStatusColor(status)}
            size="small"
          />
          {!showCancelButton && (
            <Tooltip title="关闭">
              <IconButton onClick={onClose} size="small">
                <CloseIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </DialogTitle>

      <DialogContent>
        {/* 错误信息 */}
        {error_message && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error_message}
          </Alert>
        )}

        {/* 进度条 */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              进度
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {Math.round(progress * 100)}%
            </Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={progress * 100}
            sx={{ height: 8, borderRadius: 4 }}
          />
        </Box>

        {/* 统计信息 */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            任务统计
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <Box>
              <Typography variant="body2" color="text.secondary">
                已完成
              </Typography>
              <Typography variant="h6" color="success.main">
                {completed_count} / {total_count}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                失败数量
              </Typography>
              <Typography variant="h6" color={failed_sessions.length > 0 ? "error.main" : "text.primary"}>
                {failed_sessions.length}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* 时间信息 */}
        {timeInfo.elapsedTime > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              时间信息
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  已用时间
                </Typography>
                <Typography variant="body1">
                  {formatDuration(timeInfo.elapsedTime)}
                </Typography>
              </Box>
              {timeInfo.estimatedRemaining && (
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    预计剩余
                  </Typography>
                  <Typography variant="body1">
                    {timeInfo.estimatedRemaining}
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
        )}

        {/* 失败的会话列表 */}
        {failed_sessions.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom color="error">
              失败的对话 ({failed_sessions.length})
            </Typography>
            <List dense sx={{ maxHeight: 150, overflow: 'auto', bgcolor: 'grey.50', borderRadius: 1 }}>
              {failed_sessions.map((sessionId, index) => (
                <React.Fragment key={sessionId}>
                  <ListItem>
                    <ListItemText
                      primary={`对话 ${sessionId.slice(0, 8)}...`}
                      secondary="导出失败"
                    />
                  </ListItem>
                  {index < failed_sessions.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          </Box>
        )}

        {/* 任务详情 */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            任务详情
          </Typography>
          <Typography variant="body2" color="text.secondary">
            任务ID: {task_id.slice(0, 8)}...
          </Typography>
          <Typography variant="body2" color="text.secondary">
            创建时间: {new Date(created_at).toLocaleString()}
          </Typography>
          {started_at && (
            <Typography variant="body2" color="text.secondary">
              开始时间: {new Date(started_at).toLocaleString()}
            </Typography>
          )}
          {completed_at && (
            <Typography variant="body2" color="text.secondary">
              完成时间: {new Date(completed_at).toLocaleString()}
            </Typography>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        {/* 取消按钮 */}
        {showCancelButton && (
          <Button
            onClick={onCancel}
            color="warning"
            variant="outlined"
            startIcon={<CancelIcon />}
            disabled={isLoading}
          >
            取消任务
          </Button>
        )}

        {/* 重试按钮 */}
        {showRetryButton && onRetry && (
          <Button
            onClick={onRetry}
            color="primary"
            variant="outlined"
            disabled={isLoading}
          >
            重试
          </Button>
        )}

        {/* 下载按钮 */}
        {showDownloadButton && (
          <Button
            onClick={() => onDownload(task_id)}
            color="success"
            variant="contained"
            startIcon={<DownloadIcon />}
            disabled={isLoading}
          >
            下载文件
          </Button>
        )}

        {/* 关闭按钮 */}
        {!showCancelButton && (
          <Button
            onClick={onClose}
            color="primary"
            variant="outlined"
          >
            关闭
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ProgressDialog;
