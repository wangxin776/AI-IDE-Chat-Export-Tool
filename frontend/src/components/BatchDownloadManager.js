/**
 * 批量下载管理组件
 * 提供批量下载的主要界面和控制逻辑
 */

import React, { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  FormControlLabel,
  RadioGroup,
  Radio,
  Typography,
  Alert,
  Chip,
  Divider
} from '@mui/material';
import {
  Download as DownloadIcon,
  GetApp as GetAppIcon
} from '@mui/icons-material';
import { useSimpleBatchDownload } from '../hooks/useBatchDownload';
import ProgressDialog from './ProgressDialog';
import { validateSelectionCount } from '../utils/downloadUtils';

/**
 * 批量下载管理器组件
 */
const BatchDownloadManager = ({
  selectedSessions,
  dataSource,
  onSelectionChange,
  disabled = false
}) => {
  // 状态管理
  const [formatDialogOpen, setFormatDialogOpen] = useState(false);
  const [progressDialogOpen, setProgressDialogOpen] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState('html');

  // 批量下载Hook
  const batchDownload = useSimpleBatchDownload();

  // 验证选择
  const validation = validateSelectionCount(selectedSessions.size);
  const canDownload = validation.isValid && !disabled;

  /**
   * 处理批量下载按钮点击
   */
  const handleBatchDownloadClick = () => {
    if (!canDownload) {
      return;
    }
    setFormatDialogOpen(true);
  };

  /**
   * 处理格式选择确认
   */
  const handleFormatConfirm = async () => {
    try {
      setFormatDialogOpen(false);
      setProgressDialogOpen(true);

      const sessionIds = Array.from(selectedSessions);
      await batchDownload.createBatchDownload(sessionIds, selectedFormat, dataSource);
      
    } catch (error) {
      console.error('启动批量下载失败:', error);
      setProgressDialogOpen(false);
    }
  };

  /**
   * 处理取消任务
   */
  const handleCancelTask = async () => {
    try {
      await batchDownload.cancelCurrentTask();
    } catch (error) {
      console.error('取消任务失败:', error);
    }
  };

  /**
   * 处理文件下载
   */
  const handleDownloadFile = async (taskId) => {
    try {
      await batchDownload.downloadFile(taskId);
      setProgressDialogOpen(false);
    } catch (error) {
      console.error('下载文件失败:', error);
    }
  };

  /**
   * 处理进度对话框关闭
   */
  const handleProgressDialogClose = () => {
    // 只有在任务完成、失败或取消时才允许关闭
    if (batchDownload.canStartNewTask()) {
      setProgressDialogOpen(false);
      batchDownload.reset();
    }
  };

  return (
    <>
      {/* 批量下载按钮 */}
      <Button
        variant="contained"
        color="primary"
        startIcon={<DownloadIcon />}
        onClick={handleBatchDownloadClick}
        disabled={!canDownload || batchDownload.isLoading}
        sx={{
          borderRadius: 2,
          textTransform: 'none',
          fontWeight: 600
        }}
      >
        批量下载 ({selectedSessions.size})
      </Button>

      {/* 格式选择对话框 */}
      <Dialog
        open={formatDialogOpen}
        onClose={() => setFormatDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <GetAppIcon color="primary" />
          选择导出格式
        </DialogTitle>
        
        <DialogContent>
          {/* 选择信息 */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="body1" gutterBottom>
              您已选择 <Chip label={`${selectedSessions.size} 个对话`} color="primary" size="small" /> 进行批量下载
            </Typography>
            <Typography variant="body2" color="text.secondary">
              请选择导出格式，所有对话将被打包为一个ZIP文件
            </Typography>
          </Box>

          <Divider sx={{ mb: 3 }} />

          {/* 格式选择 */}
          <FormControl component="fieldset" fullWidth>
            <Typography variant="subtitle1" gutterBottom>
              导出格式
            </Typography>
            <RadioGroup
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value)}
            >
              <FormControlLabel
                value="html"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1">HTML</Typography>
                    <Typography variant="body2" color="text.secondary">
                      网页格式，支持样式和交互，适合在浏览器中查看
                    </Typography>
                  </Box>
                }
              />
              <FormControlLabel
                value="json"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1">JSON</Typography>
                    <Typography variant="body2" color="text.secondary">
                      结构化数据格式，适合程序处理和数据分析
                    </Typography>
                  </Box>
                }
              />
              <FormControlLabel
                value="markdown"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1">Markdown</Typography>
                    <Typography variant="body2" color="text.secondary">
                      纯文本格式，支持基本格式化，适合文档编辑
                    </Typography>
                  </Box>
                }
              />
            </RadioGroup>
          </FormControl>

          {/* 注意事项 */}
          <Alert severity="info" sx={{ mt: 3 }}>
            <Typography variant="body2">
              <strong>注意事项：</strong>
              <br />
              • 批量下载可能需要较长时间，请耐心等待
              <br />
              • 下载过程中请不要关闭浏览器
              <br />
              • 如果某些对话导出失败，其他成功的对话仍会被包含在ZIP文件中
            </Typography>
          </Alert>

          {/* 验证错误 */}
          {!validation.isValid && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {validation.message}
            </Alert>
          )}
        </DialogContent>

        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={() => setFormatDialogOpen(false)}
            color="inherit"
          >
            取消
          </Button>
          <Button
            onClick={handleFormatConfirm}
            variant="contained"
            color="primary"
            startIcon={<DownloadIcon />}
            disabled={!validation.isValid}
          >
            开始下载
          </Button>
        </DialogActions>
      </Dialog>

      {/* 进度对话框 */}
      <ProgressDialog
        open={progressDialogOpen}
        onClose={handleProgressDialogClose}
        taskInfo={batchDownload.currentTask}
        progress={batchDownload.progress}
        onCancel={handleCancelTask}
        onDownload={handleDownloadFile}
        isLoading={batchDownload.isLoading}
      />
    </>
  );
};

export default BatchDownloadManager;
