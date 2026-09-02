function fig = new_hidden_figure(width, height)
%NEW_HIDDEN_FIGURE  创建隐藏画布（后台出图专用）
%   窗口不弹出、无菜单栏工具栏，避免打扰用户界面；
%   图渲染完成后由 export_figure 导出并立即 close。
%
%   参数:
%       width, height  画布尺寸（像素），可省略，有默认值
%   返回:
%       fig  Figure 句柄

    if nargin < 1, width = 900; end
    if nargin < 2, height = 420; end
    fig = figure('Visible', 'off', ...
        'Color', 'w', ...
        'Position', [80 80 width height], ...
        'MenuBar', 'none', ...
        'ToolBar', 'none');
end
