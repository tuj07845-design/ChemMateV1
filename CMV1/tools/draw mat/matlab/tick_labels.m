function labels = tick_labels(vals)
%TICK_LABELS  把任意值转成坐标轴刻度标签
%   统一把流股名 / 组分名等转成 cellstr，
%   供 set(ax, 'XTickLabel', labels) 使用。
%
%   参数:
%       vals    字符串数组 / cell / 其它可转 string 的值
%   返回:
%       labels  cellstr 刻度标签

    labels = cellstr(string(vals));
end
