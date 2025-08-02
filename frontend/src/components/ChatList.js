import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  Container,
  Typography,
  Box,
  Card,
  CardContent,
  Grid,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Button,
  Collapse,
  IconButton,
  alpha,
  TextField,
  InputAdornment,
  CardActions,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControlLabel,
  Checkbox,
  DialogContentText,
  Radio,
  RadioGroup,
  FormControl,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import CalendarTodayIcon from "@mui/icons-material/CalendarToday";
import MessageIcon from "@mui/icons-material/Message";
import InfoIcon from "@mui/icons-material/Info";
import RefreshIcon from "@mui/icons-material/Refresh";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import WarningIcon from "@mui/icons-material/Warning";
import CheckBoxOutlineBlankIcon from "@mui/icons-material/CheckBoxOutlineBlank";
import CheckBoxIcon from "@mui/icons-material/CheckBox";
import SelectAllIcon from "@mui/icons-material/SelectAll";
import { colors } from "../App";
import BatchDownloadManager from "./BatchDownloadManager";

const ChatList = ({
  dataSource,
  historyTitle = "Chat History",
  clearDataTrigger,
}) => {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedProjects, setExpandedProjects] = useState({});
  const [searchQuery, setSearchQuery] = useState("");
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [formatDialogOpen, setFormatDialogOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState("html");
  const [dontShowExportWarning, setDontShowExportWarning] = useState(false);
  const [currentExportSession, setCurrentExportSession] = useState(null);

  // 批量选择相关状态
  const [batchMode, setBatchMode] = useState(false);
  const [selectedChats, setSelectedChats] = useState(new Set());

  const fetchChats = async (
    source = dataSource,
    signal = null,
    skipLoadingState = false
  ) => {
    if (!skipLoadingState) {
      setLoading(true);
    }
    setError(null); // 清除之前的错误状态
    try {
      // 使用传入的数据源参数进行API请求
      const response = await axios.get(`/api/chats?source=${source}`, {
        signal: signal, // 支持请求取消
      });
      const chatData = response.data;

      setChats(chatData);
      setLoading(false);
    } catch (err) {
      // 如果是请求被取消，不设置错误状态
      if (err.name !== "AbortError") {
        setError(err.message);
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    // Check if user has previously chosen to not show the export warning (只在组件挂载时执行一次)
    const warningPreference = document.cookie
      .split("; ")
      .find((row) => row.startsWith("dontShowExportWarning="));

    if (warningPreference) {
      setDontShowExportWarning(warningPreference.split("=")[1] === "true");
    }
  }, []);

  // 监听数据清空信号，立即清空当前数据并设置loading状态
  useEffect(() => {
    if (clearDataTrigger > 0) {
      setLoading(true); // 立即设置loading状态，避免显示"No chats found"
      setChats([]);
      setError(null);
      setExpandedProjects({});
    }
  }, [clearDataTrigger]);

  // Watch for changes to dataSource and refetch when it changes
  useEffect(() => {
    const controller = new AbortController();

    // 添加防抖机制，避免快速切换时的多次请求
    const timeoutId = setTimeout(() => {
      // 跳过loading状态设置，因为clearDataTrigger已经设置了loading状态
      fetchChats(dataSource, controller.signal, true);
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      controller.abort(); // 取消之前的请求
    };
  }, [dataSource]);

  const toggleProjectExpand = (projectName) => {
    setExpandedProjects((prev) => ({
      ...prev,
      [projectName]: !prev[projectName],
    }));
  };

  // Filter chats based on search query
  const filteredChatsByProject = () => {
    if (!searchQuery.trim()) {
      return chats.reduce((acc, chat) => {
        const projectName = chat.project?.name || "Unknown Project";

        if (!acc[projectName]) {
          acc[projectName] = {
            name: projectName,
            path: chat.project?.rootPath || "Unknown",
            chats: [],
          };
        }

        if (chat.project?.rootPath && acc[projectName].path === "Unknown") {
          acc[projectName].path = chat.project.rootPath;
        }

        acc[projectName].chats.push(chat);
        return acc;
      }, {});
    }

    const query = searchQuery.toLowerCase();
    return chats.reduce((acc, chat) => {
      const projectName = chat.project?.name || "Unknown Project";

      // Check if project name matches
      const projectMatches = projectName.toLowerCase().includes(query);

      // Check if any message content matches
      const contentMatches =
        Array.isArray(chat.messages) &&
        chat.messages.some(
          (msg) =>
            typeof msg.content === "string" &&
            msg.content.toLowerCase().includes(query)
        );

      if (projectMatches || contentMatches) {
        if (!acc[projectName]) {
          acc[projectName] = {
            name: projectName,
            path: chat.project?.rootPath || "Unknown",
            chats: [],
          };
        }

        if (chat.project?.rootPath && acc[projectName].path === "Unknown") {
          acc[projectName].path = chat.project.rootPath;
        }

        acc[projectName].chats.push(chat);
      }

      return acc;
    }, {});
  };

  // Clear search query
  const clearSearch = () => {
    setSearchQuery("");
  };

  // Handle search input change
  const handleSearchChange = (event) => {
    setSearchQuery(event.target.value);
  };

  // 批量选择相关函数
  const toggleBatchMode = () => {
    setBatchMode(!batchMode);
    setSelectedChats(new Set()); // 切换模式时清空选择
  };

  const handleChatSelection = (sessionId, event) => {
    event.preventDefault();
    event.stopPropagation();

    setSelectedChats(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sessionId)) {
        newSet.delete(sessionId);
      } else {
        newSet.add(sessionId);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    const allSessionIds = chats.map(chat => chat.session_id).filter(Boolean);
    setSelectedChats(prev => {
      if (prev.size === allSessionIds.length) {
        return new Set(); // 全部取消选择
      } else {
        return new Set(allSessionIds); // 全部选择
      }
    });
  };

  const clearSelection = () => {
    setSelectedChats(new Set());
  };

  // Handle format dialog selection
  const handleFormatDialogOpen = (sessionId) => {
    setCurrentExportSession(sessionId);
    setFormatDialogOpen(true);
  };

  const handleFormatDialogClose = (confirmed) => {
    setFormatDialogOpen(false);

    if (confirmed) {
      // After format selection, show warning dialog or proceed directly
      if (dontShowExportWarning) {
        proceedWithExport(currentExportSession, exportFormat);
      } else {
        setExportModalOpen(true);
      }
    }
  };

  // Handle export warning confirmation
  const handleExportWarningClose = (confirmed) => {
    setExportModalOpen(false);

    // Save preference in cookies if "Don't show again" is checked
    if (dontShowExportWarning) {
      const expiryDate = new Date();
      expiryDate.setFullYear(expiryDate.getFullYear() + 1); // Cookie lasts 1 year
      document.cookie = `dontShowExportWarning=true; expires=${expiryDate.toUTCString()}; path=/`;
    }

    // If confirmed, proceed with export
    if (confirmed && currentExportSession) {
      proceedWithExport(currentExportSession, exportFormat);
    }

    // Reset current export session
    setCurrentExportSession(null);
  };

  // Function to initiate export process
  const handleExport = (e, sessionId) => {
    // Prevent navigation to chat detail
    e.preventDefault();
    e.stopPropagation();

    // First open format selection dialog
    handleFormatDialogOpen(sessionId);
  };

  // Function to actually perform the export
  const proceedWithExport = async (sessionId, format) => {
    try {
      console.log(
        `Starting ${format.toUpperCase()} export for session:`,
        sessionId
      );
      console.log(
        `Making API request to: /api/chat/${sessionId}/export?format=${format}&source=${dataSource}`
      );

      const response = await axios.get(
        `/api/chat/${sessionId}/export?format=${format}&source=${dataSource}`,
        {
          responseType: "blob",
        }
      );

      const blob = response.data;
      console.log("Received blob size:", blob ? blob.size : 0);

      if (!blob || blob.size === 0) {
        throw new Error("Received empty or invalid content from server");
      }

      // Ensure the blob has the correct MIME type
      let mimeType = "text/html;charset=utf-8";
      let extension = "html";

      if (format === "json") {
        mimeType = "application/json;charset=utf-8";
        extension = "json";
      } else if (format === "markdown") {
        mimeType = "text/markdown;charset=utf-8";
        extension = "md";
      }

      const typedBlob = blob.type ? blob : new Blob([blob], { type: mimeType });
      console.log("Prepared typed blob, size:", typedBlob.size);

      // --- Download Logic Start ---
      const filename = `cursor-chat-${sessionId.slice(0, 8)}.${extension}`;
      const link = document.createElement("a");

      // Create an object URL for the (possibly re-typed) blob
      const url = URL.createObjectURL(typedBlob);
      link.href = url;
      link.download = filename;

      // Append link to the body (required for Firefox)
      document.body.appendChild(link);

      // Programmatically click the link to trigger the download
      link.click();

      // Clean up: remove the link and revoke the object URL
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      console.log("Download initiated and cleanup complete");
      // --- Download Logic End ---
    } catch (error) {
      // ADDED: More detailed error logging
      console.error("Detailed export error:", error);
      if (error.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        console.error("Error Response Data:", error.response.data);
        console.error("Error Response Status:", error.response.status);
        console.error("Error Response Headers:", error.response.headers);
      } else if (error.request) {
        // The request was made but no response was received
        // `error.request` is an instance of XMLHttpRequest in the browser
        console.error("Error Request:", error.request);
      } else {
        // Something happened in setting up the request that triggered an Error
        console.error("Error Message:", error.message);
      }
      console.error("Error Config:", error.config);

      const errorMessage = error.response
        ? `Server error: ${error.response.status}`
        : error.request
        ? "No response received from server"
        : error.message || "Unknown error setting up request";
      alert(`Failed to export chat: ${errorMessage}`);
    }
  };

  if (loading) {
    return (
      <Container
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "70vh",
        }}
      >
        <CircularProgress sx={{ color: colors.highlightColor }} />
      </Container>
    );
  }

  if (error) {
    return (
      <Container>
        <Typography variant="h5" color="error">
          Error: {error}
        </Typography>
      </Container>
    );
  }

  const chatsByProject = filteredChatsByProject();

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* No need to show error again since we have the conditional return above */}

      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 3,
        }}
      >
        <Typography
          variant="h4"
          component="h1"
          sx={{ color: colors.textColor }}
        >
          {historyTitle}
        </Typography>
        <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
          <Button
            variant={batchMode ? "contained" : "outlined"}
            startIcon={batchMode ? <CheckBoxIcon /> : <CheckBoxOutlineBlankIcon />}
            onClick={toggleBatchMode}
            sx={{
              color: batchMode ? "white" : colors.highlightColor,
              borderColor: alpha(colors.highlightColor, 0.5),
              backgroundColor: batchMode ? colors.highlightColor : "transparent",
              "&:hover": {
                borderColor: colors.highlightColor,
                backgroundColor: batchMode
                  ? alpha(colors.highlightColor, 0.8)
                  : alpha(colors.highlightColor, 0.1),
              },
            }}
          >
            {batchMode ? "退出批量模式" : "批量选择"}
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchChats}
            sx={{
              color: colors.highlightColor,
              borderColor: alpha(colors.highlightColor, 0.5),
              "&:hover": {
                borderColor: colors.highlightColor,
                backgroundColor: alpha(colors.highlightColor, 0.1),
              },
            }}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {/* Format Selection Dialog */}
      <Dialog
        open={formatDialogOpen}
        onClose={() => handleFormatDialogClose(false)}
        aria-labelledby="format-selection-dialog-title"
      >
        <DialogTitle
          id="format-selection-dialog-title"
          sx={{ display: "flex", alignItems: "center" }}
        >
          <FileDownloadIcon sx={{ color: colors.highlightColor, mr: 1 }} />
          Export Format
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Please select the export format for your chat:
          </DialogContentText>
          <FormControl component="fieldset" sx={{ mt: 2 }}>
            <RadioGroup
              aria-label="export-format"
              name="export-format"
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value)}
            >
              <FormControlLabel value="html" control={<Radio />} label="HTML" />
              <FormControlLabel value="json" control={<Radio />} label="JSON" />
              <FormControlLabel
                value="markdown"
                control={<Radio />}
                label="Markdown"
              />
            </RadioGroup>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => handleFormatDialogClose(false)}
            color="highlight"
          >
            Cancel
          </Button>
          <Button
            onClick={() => handleFormatDialogClose(true)}
            color="highlight"
            variant="contained"
          >
            Continue
          </Button>
        </DialogActions>
      </Dialog>

      {/* Export Warning Modal */}
      <Dialog
        open={exportModalOpen}
        onClose={() => handleExportWarningClose(false)}
        aria-labelledby="export-warning-dialog-title"
      >
        <DialogTitle
          id="export-warning-dialog-title"
          sx={{ display: "flex", alignItems: "center" }}
        >
          <WarningIcon sx={{ color: "warning.main", mr: 1 }} />
          Export Warning
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Please make sure your exported chat doesn't include sensitive data
            such as API keys and customer information.
          </DialogContentText>
          <FormControlLabel
            control={
              <Checkbox
                checked={dontShowExportWarning}
                onChange={(e) => setDontShowExportWarning(e.target.checked)}
              />
            }
            label="Don't show this warning again"
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => handleExportWarningClose(false)}
            color="primary"
            sx={{ color: "white" }}
          >
            Cancel
          </Button>
          <Button
            onClick={() => handleExportWarningClose(true)}
            color="highlight"
            variant="contained"
          >
            Continue Export
          </Button>
        </DialogActions>
      </Dialog>

      {/* Search Bar */}
      <TextField
        fullWidth
        variant="outlined"
        placeholder="Search by project name or chat content..."
        value={searchQuery}
        onChange={handleSearchChange}
        size="medium"
        sx={{ mb: 3 }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon color="action" />
            </InputAdornment>
          ),
          endAdornment: searchQuery && (
            <InputAdornment position="end">
              <IconButton
                size="small"
                aria-label="clear search"
                onClick={clearSearch}
                edge="end"
              >
                <ClearIcon />
              </IconButton>
            </InputAdornment>
          ),
          sx: { borderRadius: 2 },
        }}
      />

      {/* 批量操作工具栏 */}
      {batchMode && (
        <Paper
          sx={{
            p: 2,
            mb: 3,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            backgroundColor: alpha(colors.highlightColor, 0.05),
            border: `1px solid ${alpha(colors.highlightColor, 0.2)}`,
            borderRadius: 2,
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              已选择 {selectedChats.size} 个对话
            </Typography>
            {selectedChats.size > 0 && (
              <Button
                size="small"
                onClick={clearSelection}
                sx={{ color: colors.text.secondary }}
              >
                清空选择
              </Button>
            )}
          </Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Button
              variant="outlined"
              size="small"
              startIcon={<SelectAllIcon />}
              onClick={handleSelectAll}
              sx={{
                borderColor: alpha(colors.highlightColor, 0.5),
                color: colors.highlightColor,
                "&:hover": {
                  borderColor: colors.highlightColor,
                  backgroundColor: alpha(colors.highlightColor, 0.1),
                },
              }}
            >
              {selectedChats.size === chats.length ? "取消全选" : "全选"}
            </Button>
            {selectedChats.size > 0 && (
              <BatchDownloadManager
                selectedSessions={selectedChats}
                dataSource={dataSource}
                onSelectionChange={setSelectedChats}
                disabled={loading}
              />
            )}
          </Box>
        </Paper>
      )}

      {Object.keys(chatsByProject).length === 0 ? (
        <Paper
          sx={{
            p: 4,
            textAlign: "center",
            borderRadius: 4,
            boxShadow:
              "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
          }}
        >
          <InfoIcon sx={{ fontSize: 60, color: "primary.main", mb: 2 }} />
          <Typography variant="h5" gutterBottom fontWeight="600">
            {searchQuery ? "No Results Found" : "No Chat History Found"}
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            {searchQuery
              ? `We couldn't find any chats matching "${searchQuery}".`
              : "We couldn't find any Cursor chat data on your system. This could be because:"}
          </Typography>
          {!searchQuery && (
            <Box sx={{ textAlign: "left", maxWidth: "600px", mx: "auto" }}>
              <Typography component="ul" variant="body2" sx={{ mb: 2 }}>
                <li>You haven't used Cursor's AI Assistant yet</li>
                <li>
                  Your Cursor databases are stored in a non-standard location
                </li>
                <li>
                  There might be permission issues accessing the database files
                </li>
              </Typography>
            </Box>
          )}
          {searchQuery ? (
            <Button
              startIcon={<ClearIcon />}
              onClick={clearSearch}
              variant="contained"
              color="primary"
              size="large"
              sx={{ borderRadius: 2 }}
            >
              Clear Search
            </Button>
          ) : (
            <Button
              startIcon={<RefreshIcon />}
              onClick={() => fetchChats(dataSource)}
              variant="contained"
              color="primary"
              size="large"
              sx={{ borderRadius: 2 }}
            >
              Retry Detection
            </Button>
          )}
        </Paper>
      ) : (
        Object.entries(chatsByProject).map(([projectName, projectData]) => {
          return (
            <Box key={projectName} sx={{ mb: 4 }}>
              <Paper
                sx={{
                  p: 0,
                  mb: 2,
                  overflow: "hidden",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                  transition: "all 0.3s ease-in-out",
                  "&:hover": {
                    boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                  },
                }}
              >
                <Box
                  sx={{
                    background: colors.background.paper,
                    borderBottom: "1px solid",
                    borderColor: alpha(colors.text.secondary, 0.1),
                    color: colors.text.primary,
                    p: 2,
                    cursor: "pointer",
                    "&:hover": {
                      backgroundColor: alpha(colors.highlightColor, 0.02),
                    },
                  }}
                  onClick={() => toggleProjectExpand(projectName)}
                >
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center" }}>
                      <FolderIcon
                        sx={{
                          mr: 1.5,
                          fontSize: 28,
                          color: colors.text.secondary,
                        }}
                      />
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {projectData.name}
                      </Typography>
                      <Chip
                        label={`${projectData.chats.length} ${
                          projectData.chats.length === 1 ? "chat" : "chats"
                        }`}
                        size="small"
                        sx={{
                          ml: 2,
                          fontWeight: 500,
                          backgroundColor: colors.highlightColor,
                          color: colors.text.primary,
                          "& .MuiChip-label": {
                            px: 1.5,
                          },
                        }}
                      />
                    </Box>
                    <IconButton
                      aria-expanded={expandedProjects[projectName]}
                      aria-label="show more"
                      sx={{
                        color: colors.text.primary,
                        bgcolor: colors.highlightColor,
                        "&:hover": {
                          bgcolor: alpha(colors.highlightColor, 0.8),
                        },
                      }}
                      onClick={(e) => {
                        // Prevent the click from reaching the parent Box
                        e.stopPropagation();
                        toggleProjectExpand(projectName);
                      }}
                    >
                      {expandedProjects[projectName] ? (
                        <ExpandLessIcon />
                      ) : (
                        <ExpandMoreIcon />
                      )}
                    </IconButton>
                  </Box>
                  <Typography
                    variant="body2"
                    sx={{ color: colors.text.secondary, mt: 0.5 }}
                  >
                    {projectData.path}
                  </Typography>
                </Box>
              </Paper>

              <Collapse in={expandedProjects[projectName] || false}>
                <Grid container spacing={3}>
                  {projectData.chats.map((chat, index) => {
                    // Format the date safely
                    let dateDisplay = "Unknown date";
                    try {
                      if (chat.date) {
                        // Check if timestamp is in seconds or milliseconds
                        // Timestamps > 10^10 are likely in milliseconds
                        // Timestamps < 10^10 are likely in seconds
                        let timestamp = chat.date;
                        if (timestamp < 10000000000) {
                          // Timestamp is in seconds, convert to milliseconds
                          timestamp = timestamp * 1000;
                        }

                        const dateObj = new Date(timestamp);
                        // Check if date is valid
                        if (!isNaN(dateObj.getTime())) {
                          dateDisplay = dateObj.toLocaleString();
                        }
                      }
                    } catch (err) {
                      console.error("Error formatting date:", err);
                    }

                    return (
                      <Grid
                        item
                        xs={12}
                        sm={6}
                        md={4}
                        key={chat.session_id || `chat-${index}`}
                      >
                        <Card
                          component={batchMode ? "div" : Link}
                          to={batchMode ? undefined : `/chat/${chat.session_id}`}
                          sx={{
                            height: "100%",
                            display: "flex",
                            flexDirection: "column",
                            transition:
                              "all 0.3s cubic-bezier(.17,.67,.83,.67)",
                            textDecoration: "none",
                            borderTop: "1px solid",
                            borderColor: selectedChats.has(chat.session_id)
                              ? colors.highlightColor
                              : alpha(colors.text.secondary, 0.1),
                            border: selectedChats.has(chat.session_id)
                              ? `2px solid ${colors.highlightColor}`
                              : undefined,
                            backgroundColor: selectedChats.has(chat.session_id)
                              ? alpha(colors.highlightColor, 0.05)
                              : undefined,
                            cursor: batchMode ? "pointer" : undefined,
                            "&:hover": {
                              transform: batchMode ? "none" : "translateY(-8px)",
                              boxShadow: batchMode
                                ? "0 4px 12px rgba(0,0,0,0.1)"
                                : "0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)",
                            },
                          }}
                          onClick={batchMode ? (e) => handleChatSelection(chat.session_id, e) : undefined}
                        >
                          <CardContent>
                            {/* 批量选择复选框 */}
                            {batchMode && (
                              <Box
                                sx={{
                                  display: "flex",
                                  justifyContent: "flex-end",
                                  mb: 1,
                                }}
                              >
                                <Checkbox
                                  checked={selectedChats.has(chat.session_id)}
                                  onChange={(e) => handleChatSelection(chat.session_id, e)}
                                  sx={{
                                    color: colors.highlightColor,
                                    "&.Mui-checked": {
                                      color: colors.highlightColor,
                                    },
                                  }}
                                  onClick={(e) => e.stopPropagation()}
                                />
                              </Box>
                            )}

                            <Box
                              sx={{
                                display: "flex",
                                alignItems: "center",
                                mb: 1.5,
                                justifyContent: "space-between",
                              }}
                            >
                              <Box
                                sx={{ display: "flex", alignItems: "center" }}
                              >
                                <CalendarTodayIcon
                                  fontSize="small"
                                  sx={{ mr: 1, color: "text.secondary" }}
                                />
                                <Typography
                                  variant="body2"
                                  color="text.secondary"
                                >
                                  {dateDisplay}
                                </Typography>
                              </Box>
                            </Box>

                            <Divider sx={{ my: 1.5 }} />

                            <Box
                              sx={{
                                display: "flex",
                                alignItems: "center",
                                mb: 1.5,
                              }}
                            >
                              <MessageIcon
                                fontSize="small"
                                sx={{ mr: 1, color: colors.text.secondary }}
                              />
                              <Typography variant="body2" fontWeight="500">
                                {Array.isArray(chat.messages)
                                  ? chat.messages.length
                                  : 0}{" "}
                                messages
                              </Typography>
                            </Box>

                            {chat.db_path && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{
                                  display: "block",
                                  mb: 1.5,
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                DB:{" "}
                                {chat.db_path.split("/").slice(-2).join("/")}
                              </Typography>
                            )}

                            {Array.isArray(chat.messages) &&
                              chat.messages[0] &&
                              chat.messages[0].content && (
                                <Box
                                  sx={{
                                    mt: 2,
                                    p: 1.5,
                                    backgroundColor: alpha(
                                      colors.highlightColor,
                                      0.1
                                    ),
                                    borderRadius: 2,
                                    border: "1px solid",
                                    borderColor: alpha(
                                      colors.text.secondary,
                                      0.05
                                    ),
                                  }}
                                >
                                  <Typography
                                    variant="body2"
                                    sx={{
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      display: "-webkit-box",
                                      WebkitLineClamp: 2,
                                      WebkitBoxOrient: "vertical",
                                      color: "text.primary",
                                      fontWeight: 400,
                                    }}
                                  >
                                    {typeof chat.messages[0].content ===
                                    "string"
                                      ? chat.messages[0].content.substring(
                                          0,
                                          100
                                        ) +
                                        (chat.messages[0].content.length > 100
                                          ? "..."
                                          : "")
                                      : "Content unavailable"}
                                  </Typography>
                                </Box>
                              )}
                          </CardContent>
                          <CardActions sx={{ mt: "auto", pt: 0 }}>
                            {!batchMode && (
                              <Tooltip title="Export Chat (Warning: Check for sensitive data)">
                                <IconButton
                                  size="small"
                                  onClick={(e) =>
                                    handleExport(e, chat.session_id)
                                  }
                                  sx={{
                                    ml: "auto",
                                    position: "relative",
                                  "&::after": dontShowExportWarning
                                    ? null
                                    : {
                                        content: '""',
                                        position: "absolute",
                                        width: "6px",
                                        height: "6px",
                                        backgroundColor: "warning.main",
                                        borderRadius: "50%",
                                        top: "2px",
                                        right: "2px",
                                      },
                                }}
                              >
                                <FileDownloadIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            )}
                          </CardActions>
                        </Card>
                      </Grid>
                    );
                  })}
                </Grid>
              </Collapse>
            </Box>
          );
        })
      )}
    </Container>
  );
};

export default ChatList;
