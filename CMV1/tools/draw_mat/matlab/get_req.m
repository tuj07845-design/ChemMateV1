function v = get_req(req, name, default)
%GET_REQ  从绘图请求里取一个字符串参数，带默认值
%   用法：get_req(req, 'ylabel', 'Flow')
%   —— 请求里没写 ylabel（或写了空白）时返回 'Flow'。
%
%   参数:
%       req      请求结构体
%       name     参数字段名
%       default  参数缺失/为空时返回的默认值
%   返回:
%       v        参数值（string 类型）

    v = string(default);
    if isfield(req, name)
        raw = req.(name);
        if ~isempty(raw)
            s = strtrim(string(raw));
            if strlength(s) > 0
                v = s;   % 只接受非空白值，空白视为未提供
            end
        end
    end
end
