function must_have_columns(tbl, names)
%MUST_HAVE_COLUMNS  校验 data.csv 表格包含指定列
%   缺列时直接 error，identifier 带 spec_invalid，
%   上层 draw_dispatch 会据此把失败归类为"参数错误"。
%
%   参数:
%       tbl     readtable 读出的表格
%       names   必须存在的列名（cell 数组）

    have = string(tbl.Properties.VariableNames);
    for i = 1:numel(names)
        if ~any(have == string(names{i}))
            error('spec_invalid: missing column "%s" in data.csv', names{i});
        end
    end
end
