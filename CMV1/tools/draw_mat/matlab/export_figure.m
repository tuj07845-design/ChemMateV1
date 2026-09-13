function export_figure(fig, fig_path, req)
%EXPORT_FIGURE  把 Figure 导出为图片文件（默认 200 DPI）
%   优先用 exportgraphics（新版本 MATLAB）；
%   失败时回退到 print，按扩展名选择 -dsvg / -dpng。
%
%   参数:
%       fig       Figure 句柄
%       fig_path  输出文件路径（.png / .svg）
%       req       绘图请求（保留参数，兼容调用接口）

    set(fig, 'Color', 'w', 'PaperPositionMode', 'auto');
    try
        exportgraphics(fig, fig_path, 'Resolution', 200);
    catch
        % 旧版 MATLAB 没有 exportgraphics 时的回退方案
        [~, ~, ext] = fileparts(fig_path);
        if strcmpi(ext, '.svg')
            print(fig, fig_path, '-dsvg');
        else
            print(fig, fig_path, '-dpng', '-r200');
        end
    end
end
