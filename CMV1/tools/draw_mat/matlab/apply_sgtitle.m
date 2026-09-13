function apply_sgtitle(req)
%APPLY_SGTITLE  设置多子图总标题（sgtitle）
%   用于 balance_check 这种 1x2 双子图布局：
%   子图各自有 title，总标题用 sgtitle 统一放在图顶部。
%
%   参数:
%       req  绘图请求结构体（jsondecode 后的 request.json）

    if isfield(req, 'title') && strlength(strtrim(string(req.title))) > 0
        % 标题非空才设置
        sgtitle(strtrim(string(req.title)), 'FontWeight', 'bold', 'FontSize', 13, ...
            'FontName', 'Arial');
    end
end
