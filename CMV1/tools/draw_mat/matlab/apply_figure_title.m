function apply_figure_title(req)
%APPLY_FIGURE_TITLE  设置单图标题（ChemMate 统一风格）
%   如果 request.json 里提供了非空 title，
%   就以粗体 Arial 13pt 深灰色的统一风格给当前图加标题。
%
%   参数:
%       req  绘图请求结构体（jsondecode 后的 request.json）

    if isfield(req, 'title') && strlength(strtrim(string(req.title))) > 0
        % 标题非空才设置，避免空白标题覆盖图形
        title(strtrim(string(req.title)), 'FontWeight', 'bold', 'FontSize', 13, ...
            'FontName', 'Arial', 'Color', [0.1 0.1 0.1]);
    end
end
